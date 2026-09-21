"""
TimeTrack -- one running application, two front doors onto the same
SQLite database of logged time entries:

  1. A real website (served from ./static) -- for people, in a browser
  2. An MCP server, mounted at /mcp -- for AI assistants, over HTTP

Both talk to the exact same database.py functions.

The FastMCP object itself lives in mcp_server.py so Horizon can load
mcp_server.py:mcp without importing FastAPI or ./static.

Setup:
    uv init .
    uv add fastmcp fastapi "uvicorn[standard]"
    uv run uvicorn main:app --reload

Then visit http://127.0.0.1:8000 for the website,
and http://127.0.0.1:8000/mcp is the MCP endpoint (Streamable HTTP).

Walkthrough: docs/MAIN.md  |  docs/main.html
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database as db
from mcp_server import mcp

STATIC_DIR = Path(__file__).resolve().parent / "static"

# path="/" here, NOT "/mcp" -- app.mount() below adds that prefix.
# Setting both would double up into /mcp/mcp -- a real, easy-to-miss bug,
# verified against FastMCP's own documentation.
# Vercel runs each request in a short-lived function, so Streamable HTTP
# must not keep an in-memory session across invocations.

mcp_app = mcp.http_app(
    path="/",
    stateless_http=os.environ.get("VERCEL") == "1",
)


# ---------- FastAPI app, lifespan wired in AT CONSTRUCTION ----------
app = FastAPI(title="TimeTrack", lifespan=mcp_app.lifespan)


class NewEntry(BaseModel):
    employee_name: str
    project: str
    entry_date: str
    hours: float
    description: str = ""


@app.get("/api/entries")
def api_list_entries():
    return db.list_all_entries()


@app.post("/api/entries")
def api_log_entry(entry: NewEntry):
    return db.log_time(entry.employee_name, entry.project, entry.entry_date, entry.hours, entry.description)


@app.get("/api/projects")
def api_list_projects():
    return db.list_projects()


@app.get("/api/projects/{project}/summary")
def api_project_summary(project: str):
    return db.get_project_summary(project)


@app.get("/api/timesheet/{employee_name}")
def api_get_timesheet(employee_name: str, start_date: str = None, end_date: str = None):
    return db.get_timesheet(employee_name, start_date, end_date)


@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/mcp", mcp_app)
