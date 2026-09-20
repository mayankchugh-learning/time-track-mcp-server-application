"""
TimeTrack MCP object — the only module Horizon should load.

Local website + REST still live in main.py, which imports `mcp` from here
and mounts it at /mcp. Horizon entrypoint: mcp_server.py:mcp

That split keeps docs/, assets/, static/, and main_to_understand.py in git
without importing FastAPI or serving the website on the public MCP URL.
"""
from fastmcp import FastMCP

import database as db

db.init_db()

mcp = FastMCP("TimeTrack")


@mcp.tool
def log_time(employee_name: str, project: str, entry_date: str, hours: float, description: str = "") -> dict:
    """Log a time entry. entry_date must be YYYY-MM-DD. Shows up on the website immediately."""
    return db.log_time(employee_name, project, entry_date, hours, description)


@mcp.tool
def get_timesheet(employee_name: str, start_date: str = "", end_date: str = "") -> list[dict]:
    """Get one employee's logged entries, optionally filtered to a date range (YYYY-MM-DD)."""
    return db.get_timesheet(employee_name, start_date or None, end_date or None)


@mcp.tool
def get_project_summary(project: str) -> dict:
    """Get total hours logged against a project, broken down by employee."""
    return db.get_project_summary(project)


@mcp.tool
def list_projects() -> list[str]:
    """List every project that has at least one logged time entry."""
    return db.list_projects()


@mcp.resource("timesheet://projects")
def known_projects() -> list[str]:
    """The current set of projects with logged time, for consistent naming."""
    return db.list_projects()


@mcp.prompt
def generate_weekly_report(employee_name: str, week_start: str) -> str:
    """Guides the AI to build a structured weekly hours report from this server's own tools."""
    return f"""Build a weekly report for {employee_name}, starting {week_start}.

1. Call get_timesheet with employee_name='{employee_name}', start_date='{week_start}'
2. Group the results by project
3. Present it as:
   {{employee_name}} -- Week of {week_start}
   [Project]: {{total hours for that project}}h
   Total: {{sum of all hours}}h

If no entries are found for that week, say so plainly instead of inventing data.
"""
