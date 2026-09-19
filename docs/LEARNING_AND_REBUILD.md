# TimeTrack — Learn It, Then Build It Again

This guide is a rebuild of the repository from an empty folder. Each phase ends with a **checkpoint** you can compare against this repo. If a checkpoint fails, fix that phase before moving on.

Read [ARCHITECTURE.md](ARCHITECTURE.md) once before you start, then keep it open as a map.

---

## What you will be able to do when you finish

- Persist billable hours in SQLite and query them with filters and `GROUP BY`.
- Expose the same data as a REST API and as an MCP server.
- Mount FastMCP inside FastAPI without the `/mcp/mcp` bug or a dead lifespan.
- Build a three-tab vanilla frontend that talks only to `/api/*`.
- Connect Claude Desktop (or any Streamable HTTP MCP client) and watch both doors share rows.
- Explain why hand-curated tools are safer than `FastMCP.from_fastapi` plus raw SQL.

Estimated time if you type everything: one focused afternoon. Skimming and copying is faster; typing is how it sticks.

---

## Prerequisites

Install these first.

| Tool | Why | Check |
|---|---|---|
| Python 3.13+ | Matches `.python-version` | `python --version` |
| [uv](https://docs.astral.sh/uv/) | Project + dependency manager used by this repo | `uv --version` |
| A browser | Website door | — |
| An MCP client (optional but recommended) | Assistant door | Claude Desktop, Cursor, or `uv run fastmcp dev` |

On Windows, PowerShell is fine. Commands below are the same on all platforms unless noted.

---

## Phase 0 — The idea, in one paragraph

You are building a **timesheet**. People type hours in a browser. An AI assistant can log and summarize those hours too. Both must hit the **same file-backed database**. If they do not, you built two apps that happen to share a folder.

Work in this order every time you recreate it:

```
database  →  REST  →  website  →  MCP tools  →  mount MCP on FastAPI  →  connect a client
```

Do not start with MCP. Tools with nothing behind them teach the decorator, not the system.

---

## Phase 1 — Empty project

```bash
mkdir timetrack
cd timetrack
uv init .
uv add fastmcp fastapi "uvicorn[standard]"
uv run fastmcp version
```

`uv init .` writes `pyproject.toml`, `.python-version`, and a stub `main.py`. `uv add` records dependencies and creates `uv.lock`.

**Checkpoint**

- [ ] `pyproject.toml` lists `fastapi`, `fastmcp`, and `uvicorn[standard]`
- [ ] `uv run fastmcp version` prints a version, not an import error
- [ ] Requires-python is `>=3.13` (or whatever you actually installed — stay consistent)

Create a `.gitignore` that at least includes:

```
.venv
__pycache__/
*.db
```

---

## Phase 2 — Persistence (`database.py`)

Create `database.py`. This module must not import FastAPI or FastMCP.

### 2.1 Path and connection

```python
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("TIMETRACK_DB_PATH", "/tmp/timetrack.db"))


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

On Windows, `/tmp/timetrack.db` may not be where you think. For local learning, either create that folder or set:

```powershell
$env:TIMETRACK_DB_PATH = ".\timetrack.db"
```

`sqlite3.Row` lets you write `row["project"]` instead of `row[2]`. Use it.

### 2.2 Schema and seed

```python
def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            project TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            hours REAL NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        )
    """)
    count = conn.execute("SELECT COUNT(*) FROM time_entries").fetchone()[0]
    if count == 0:
        seed = [
            ("Asha Patel", "Website Redesign", "2026-09-08", 6.5, "Homepage layout"),
            ("Asha Patel", "Website Redesign", "2026-09-09", 7.0, "Mobile responsive fixes"),
            ("Asha Patel", "Client Onboarding", "2026-09-10", 3.0, "Kickoff call + notes"),
            ("Rahul Mehta", "Website Redesign", "2026-09-08", 5.5, "API integration"),
            ("Rahul Mehta", "Internal Tools", "2026-09-09", 8.0, "Dashboard bug fixes"),
        ]
        conn.executemany(
            "INSERT INTO time_entries (employee_name, project, entry_date, hours, description) "
            "VALUES (?, ?, ?, ?, ?)",
            seed,
        )
        conn.commit()
    conn.close()
```

Why seed: the website is empty and depressing without rows, and `GROUP BY` is hard to trust until you can predict the totals.

Expected totals after seed:

- Website Redesign = **19.0** hours (Asha 13.5 + Rahul 5.5)
- Client Onboarding = **3.0**
- Internal Tools = **8.0**

### 2.3 Serialize rows once

```python
def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "employee_name": row["employee_name"],
        "project": row["project"],
        "entry_date": row["entry_date"],
        "hours": row["hours"],
        "description": row["description"],
    }
```

Every `SELECT` that returns entries should go through this. If you later add a column, you change one function.

### 2.4 The five operations the product needs

Implement these exactly — names, arguments, and return shapes. The rest of the app is just two wrappers around them.

1. **`list_all_entries()`** → `SELECT * FROM time_entries ORDER BY entry_date DESC, id DESC`
2. **`log_time(employee_name, project, entry_date, hours, description="")`**
   - Reject `hours <= 0` with `ValueError`
   - `INSERT`, `commit`, then `SELECT` the new id and return `_row_to_dict`
3. **`get_timesheet(employee_name, start_date=None, end_date=None)`**
   - Always filter `employee_name = ?`
   - If `start_date`: `AND entry_date >= ?`
   - If `end_date`: `AND entry_date <= ?`
   - `ORDER BY entry_date`
4. **`list_projects()`** → `SELECT DISTINCT project ... ORDER BY project`
5. **`get_project_summary(project)`**
   - `SELECT employee_name, SUM(hours) as total_hours ... GROUP BY employee_name`
   - Raise `ValueError` if no rows
   - Return `{"project", "total_hours", "by_employee"}`

Use `?` placeholders. Never interpolate user strings into SQL.

You can skip `execute_query` on the rebuild. It exists in this repo only for the learning file.

### 2.5 Prove the database without any server

```bash
uv run python -c "import database as db; db.init_db(); print(db.list_projects()); print(db.get_project_summary('Website Redesign'))"
```

**Checkpoint**

- [ ] Prints `['Client Onboarding', 'Internal Tools', 'Website Redesign']` (alphabetical)
- [ ] Summary total is `19.0` and `by_employee` has both Asha and Rahul
- [ ] Run the same command again — still 5 rows, not 10. Seed must be “if empty,” not “every import”
- [ ] `db.log_time("Asha Patel", "Website Redesign", "2026-09-11", 2, "Docs")` returns a dict with an `id`
- [ ] Delete the `.db` file and re-run `init_db` — seed comes back. That is the restart-and-recover proof.

---

## Phase 3 — REST API only

Replace the stub `main.py` with a FastAPI app that does **not** mention MCP yet.

```python
from fastapi import FastAPI
from pydantic import BaseModel

import database as db

db.init_db()

app = FastAPI(title="TimeTrack")


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
    return db.log_time(
        entry.employee_name,
        entry.project,
        entry.entry_date,
        entry.hours,
        entry.description,
    )


@app.get("/api/projects")
def api_list_projects():
    return db.list_projects()


@app.get("/api/projects/{project}/summary")
def api_project_summary(project: str):
    return db.get_project_summary(project)


@app.get("/api/timesheet/{employee_name}")
def api_get_timesheet(employee_name: str, start_date: str | None = None, end_date: str | None = None):
    return db.get_timesheet(employee_name, start_date, end_date)
```

Run:

```bash
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

**Checkpoint** (use Swagger or curl)

- [ ] `GET /api/entries` returns 5 seed rows (plus any you added)
- [ ] `GET /api/projects` matches Phase 2
- [ ] `GET /api/projects/Website%20Redesign/summary` returns `total_hours: 19.0` (or more if you logged extra)
- [ ] `GET /api/timesheet/Asha%20Patel?start_date=2026-09-09` omits the Sep 8 row
- [ ] `POST /api/entries` with JSON creates a row that then appears in `GET /api/entries`

You now have a normal API tutorial app. MCP has not entered the picture. That is the point.

---

## Phase 4 — Website (`static/`)

### 4.1 Serve files

Add to `main.py`:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
```

Mount `/static` **after** the `/` route. If you mount a catch-all too early you can shadow routes.

### 4.2 `static/index.html`

Build three views, one visible at a time:

| `data-view` | Section id | Contents |
|---|---|---|
| `entries` | `view-entries` | Table: Date, Employee, Project, Hours, Description |
| `summary` | `view-summary` | `<select id="projectSelect">`, Load button, `#summaryResult` |
| `log` | `view-log` | Form: employee, project, date, hours (step 0.25), description |

Link `/static/style.css` in `<head>` and `/static/app.js` at the bottom of `<body>`.

Copy layout and CSS from this repo if you want the same look. Functionally you only need: tabs, a table, a select, a form.

### 4.3 `static/app.js`

Implement four behaviors:

1. **Tabs** — clicking a `.tab` sets `.active` on that tab and on `#view-{data-view}`.
2. **`loadEntries()`** — `GET /api/entries`, render `<tr>` rows. Escape text fields.
3. **`loadProjectOptions()`** — `GET /api/projects`, fill the `<select>`.
4. **Form submit** — `preventDefault`, `POST /api/entries` with JSON, reset the form, call both loaders.

`escapeHtml`:

```javascript
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
```

Call `loadEntries()` and `loadProjectOptions()` once at the bottom of the file.

**Checkpoint**

- [ ] `http://127.0.0.1:8000` shows the seed table
- [ ] Project Summary dropdown lists three projects; Load shows a total and per-person hours
- [ ] Log Time adds a row; All Entries shows it without a full page reload
- [ ] A name like `Asha <b>Patel</b>` appears as literal text, not bold HTML

---

## Phase 5 — MCP tools, still not mounted

In `main.py`, **above** the FastAPI constructor, create the MCP server and point every tool at `database.py`.

```python
from fastmcp import FastMCP

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
```

Notes you should feel in your fingers:

- The decorator is `@mcp.tool` (no `()` in the production file). FastMCP accepts both; stay consistent with this repo.
- Tool **names** default to the function names. Clients call `log_time`, not `api_log_entry`.
- `start_date: str = ""` then `start_date or None` — MCP clients send strings more happily than `null`.
- The docstring is what the model reads. Write it like a user-facing help line.

### Resource

```python
@mcp.resource("timesheet://projects")
def known_projects() -> list[str]:
    """The current set of projects with logged time, for consistent naming."""
    return db.list_projects()
```

### Prompt

```python
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
```

The prompt does not query SQLite. It tells the model **which tool to call** and **how to format** the answer. That is the whole primitive.

**Checkpoint**

- [ ] You did not copy-paste SQL into the tool bodies
- [ ] Four tools, one resource, one prompt
- [ ] `list_projects` and `known_projects` share `db.list_projects` — two MCP primitives, one query

---

## Phase 6 — Mount MCP on FastAPI (the part people get wrong)

Still in `main.py`, after the MCP primitives and **when constructing FastAPI**:

```python
mcp_app = mcp.http_app(path="/")

app = FastAPI(title="TimeTrack", lifespan=mcp_app.lifespan)

# ... all REST routes and FileResponse("/") ...

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/mcp", mcp_app)
```

Memorize this pair:

| Piece | Correct value | Wrong value | Symptom |
|---|---|---|---|
| `mcp.http_app(...)` | `path="/"` | `path="/mcp"` | Client hits `/mcp/mcp` |
| FastAPI lifespan | `FastAPI(lifespan=mcp_app.lifespan)` | set after `app` exists | `/mcp` never initializes |

Restart uvicorn. Website still works. MCP is now at `http://127.0.0.1:8000/mcp`.

**Checkpoint**

- [ ] `http://127.0.0.1:8000` still loads
- [ ] `http://127.0.0.1:8000/docs` still lists `/api/*`
- [ ] A GET/POST to `/mcp` is no longer a FastAPI 404 (the exact body depends on the MCP handshake; “not found” means the two-path bug)

Optional inspect:

```bash
uv run fastmcp inspect main.py:mcp
```

---

## Phase 7 — Connect a client and prove the two doors

### Claude Desktop

Config snippet:

```json
{
  "mcpServers": {
    "timetrack": { "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

Restart Claude Desktop after saving.

### What to say to the assistant

1. “List the projects in TimeTrack.” → should call `list_projects` (or read `timesheet://projects`).
2. “Log 1.5 hours for Asha Patel on Website Redesign for today, description MCP test.”
3. Switch to the browser, open All Entries — the MCP row is there.
4. In the browser, log another row. Ask the assistant for Asha’s timesheet — both rows appear.
5. “Generate a weekly report for Asha Patel starting 2026-09-08.” → should use the prompt + `get_timesheet`, not invent hours.

**Checkpoint (the whole point of the project)**

- [ ] Browser-created row visible to the assistant
- [ ] Assistant-created row visible in the browser
- [ ] Empty week: assistant says there are no entries, instead of making some up

---

## Phase 8 — Understand the alternate learning file

Do **not** merge this into `main.py`. Read `main_to_understand.py` and run it on another port:

```bash
uv run uvicorn main_to_understand:app --port 9998 --reload
```

Notice three differences:

| Topic | `main.py` (production) | `main_to_understand.py` (study) |
|---|---|---|
| Order | MCP first, then FastAPI with lifespan | FastAPI first |
| How tools appear | You declare each `@mcp.tool` | `FastMCP.from_fastapi(app=app)` |
| Extra surface | None | `execute_query_dynamically` + `timesheet://schema` |
| `if __name__` | unused | `mcp.run()` (stdio-style) |

`from_fastapi` is a shortcut: every REST route becomes a tool. That is useful for 10 minutes of “does wrapping work?” It is a weak long-term API because:

- Route names and HTTP details leak into the model’s tool list.
- You cannot attach a prompt or a `timesheet://` resource by thinking only in REST.
- A generic SQL tool (`execute_query`) violates least privilege.

After you understand it, close that file and keep shipping `main.py`.

---

## Phase 9 — Optional: smallest possible MCP server

`dummy.py` is a calculator with no website and no database.

```bash
uv run fastmcp dev dummy.py
```

Rebuild it yourself if you want the Horizon path in isolation:

- `mcp = FastMCP("Calculator")`
- Five `@mcp.tool` functions
- `if __name__ == "__main__": mcp.run()`
- Horizon entrypoint: `dummy.py:mcp`

Then go back to TimeTrack. The calculator teaches the decorator. TimeTrack teaches a product.

---

## Phase 10 — Deploy (only after local two-door proof)

### MCP-only public URL (Prefect Horizon)

1. Push the repo to GitHub.
2. Sign in at [Prefect Horizon / FastMCP Cloud](https://gofastmcp.com/v2/deployment/fastmcp-cloud).
3. Connect the repo. Dependencies come from `pyproject.toml`.
4. Entrypoint for the full app’s MCP object: `main.py:mcp`.
5. Confirm whether static routes are included. If the website is missing, that host is MCP-only.

### Whole app (website + MCP)

Run `uvicorn main:app` on any host that can keep a writable disk for the SQLite file. Set `TIMETRACK_DB_PATH` to a persistent volume. `/tmp` on a container is deleted when the instance is replaced.

---

## Suggested practice after the rebuild

Do these on **your** copy, not by editing this guide’s text.

1. Add `GET /api/entries/{id}` and an MCP tool `get_entry(id)`.
2. Add an `employees` distinct list, same pattern as `list_projects`.
3. Reject `hours > 24` in `log_time`.
4. Add a fourth tab: “My week” that calls `/api/timesheet/{name}`.
5. Write three pytest functions that call `database.py` only — no FastAPI test client required for the first pass.

Each exercise forces you to change `database.py` first, then both doors. If you only change REST, you will feel the architecture working against you. That feeling is the lesson.

---

## Common failures and the actual cause

| What you see | Likely cause |
|---|---|
| `/mcp` 404 or tools live under `/mcp/mcp` | `http_app(path="/mcp")` **and** `mount("/mcp")` |
| MCP client connects then immediately dies | Lifespan not passed into `FastAPI(...)` |
| Website works, new MCP logs vanish after restart | SQLite path is `/tmp` on a host that wipes tmp, or you are looking at a different `TIMETRACK_DB_PATH` |
| Seed rows double | You insert seed without checking `COUNT(*)` |
| Summary 404 / `ValueError` | Project string does not match stored spelling (`Website Redesign` vs `website redesign`) |
| Model invents hours | Prompt not used, or you gave it a SQL tool and it “helped” |
| Form does nothing | Forgot `e.preventDefault()` or uvicorn is not serving `static/app.js` |
| Bold / broken HTML in the table | Skipped `escapeHtml` |

---

## Rebuild checklist (print this)

Copy this list into a note. Tick it on a **new** folder, without looking at this repo except when stuck.

- [ ] `uv init` + `uv add fastmcp fastapi "uvicorn[standard]"`
- [ ] `database.py`: schema, seed-if-empty, five functions, parameterized SQL
- [ ] CLI proof of `list_projects` and `get_project_summary`
- [ ] FastAPI REST only; Swagger exercises every route
- [ ] `static/` three tabs; log from the form
- [ ] Four tools, one resource, one prompt — all call `db.*`
- [ ] `http_app(path="/")` + `FastAPI(lifespan=...)` + `mount("/mcp")`
- [ ] Browser row visible to MCP; MCP row visible in browser
- [ ] You can explain why `main_to_understand.py` is not the production file

When every box is ticked, you did not just read TimeTrack. You can write it again.
