# TimeTrack — Application Architecture

TimeTrack is one running Python process with **two front doors onto the same SQLite database**:

1. A **browser website** at `/` (people log and review hours).
2. An **MCP server** at `/mcp` (AI assistants log and review the same hours).

Nothing is duplicated between those doors. Both call the same functions in `database.py`. If an assistant logs 3 hours via MCP, the website table shows it on the next refresh. If a person logs time in the browser, `get_timesheet` on the MCP side returns it.

```
┌──────────────────────────┐     ┌──────────────────────────┐
│  Person in a browser     │     │  AI assistant            │
│  http://127.0.0.1:8000   │     │  Claude Desktop, etc.    │
└────────────┬─────────────┘     └────────────┬─────────────┘
             │ GET/POST /api/*                │ Streamable HTTP
             │ + static HTML/JS/CSS           │ POST /mcp
             ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI process (uvicorn)               │
│                                                             │
│   REST routes in main.py          FastMCP http_app          │
│   /api/entries                    mounted at /mcp           │
│   /api/projects                   tools / resource / prompt │
│   /api/timesheet/{name}                                     │
│   /  and  /static                                           │
└─────────────────────────────┬───────────────────────────────┘
                              │ import database as db
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  database.py                                                │
│  SQLite file (TIMETRACK_DB_PATH or /tmp/timetrack.db)       │
│  table: time_entries                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Why this shape exists

The teaching goal is a **real shared system of record**, not a toy that only the model can see.

| Design choice | Why it matters |
|---|---|
| One SQLite file | Persistence survives process restart. Both doors read/write the same rows. |
| Thin `database.py` | REST and MCP never own SQL. Adding a third client later is one import. |
| Hand-curated MCP tools | The model can only do the four safe operations you expose — not arbitrary SQL. |
| FastAPI + mounted MCP | One port, one process, one lifespan. The website and the assistant share uptime. |
| Static frontend | The UI is just `fetch('/api/...')`. No framework required to understand the contract. |

`main_to_understand.py` is a **learning contrast**, not the production entrypoint. It auto-wraps FastAPI routes into MCP and also exposes a raw SQL tool. Walk through it line by line in [MAIN_TO_UNDERSTAND.md](MAIN_TO_UNDERSTAND.md) or the study page [main-to-understand.html](main-to-understand.html). Rebuild context: [Learning and rebuild guide](LEARNING_AND_REBUILD.md#phase-8-understand-the-alternate-learning-file).

---

## Repository map

```
time-track-mcp-server/
├── main.py                 Production app: MCP first, then FastAPI, then mounts
├── database.py             SQLite persistence and queries
├── dummy.py                Minimal MCP-only calculator (Horizon deploy example)
├── main_to_understand.py   Learning file: REST first, then FastMCP.from_fastapi
├── static/
│   ├── index.html          Three-tab UI
│   ├── app.js              Talks only to /api/*
│   └── style.css           Layout and theme
├── pyproject.toml          Project metadata and dependencies
├── uv.lock                 Locked dependency versions
├── .python-version         3.13
└── docs/
    ├── ARCHITECTURE.md            This file
    ├── LEARNING_AND_REBUILD.md    Rebuild from empty
    ├── MAIN_TO_UNDERSTAND.md      Walkthrough of the learning file
    └── main-to-understand.html    Same walkthrough, browser study page
```

The README mentions `timetrack_notebook.ipynb`. That notebook is **not in this repo**. The rebuild guide replaces it.

---

## Runtime stack

| Layer | Library | Role |
|---|---|---|
| Process | `uvicorn` | ASGI server. `uv run uvicorn main:app --reload` |
| Web framework | `FastAPI` | REST routes, static files, lifespan |
| MCP framework | `FastMCP` | Tools, resource, prompt, Streamable HTTP app |
| Validation | `Pydantic` `BaseModel` | JSON body for `POST /api/entries` |
| Persistence | `sqlite3` stdlib | File-backed SQL |
| Frontend | Vanilla HTML/JS/CSS | No build step |

From `pyproject.toml`:

- Python `>=3.13`
- `fastapi`
- `fastmcp`
- `uvicorn[standard]`

Package manager is **uv**. `uv.lock` pins the exact versions used to run the app.

---

## Process startup sequence

Order in `main.py` is intentional. Do not reverse it.

```
1. import database as db
2. db.init_db()
      CREATE TABLE IF NOT EXISTS time_entries
      if empty → insert 5 seed rows
3. mcp = FastMCP("TimeTrack")
4. decorate tools / resource / prompt
5. mcp_app = mcp.http_app(path="/")
6. app = FastAPI(..., lifespan=mcp_app.lifespan)
7. register REST routes and FileResponse("/")
8. app.mount("/static", StaticFiles(...))
9. app.mount("/mcp", mcp_app)
10. uvicorn serves `app`
```

Two rules that break the MCP door if you get them wrong (verified against FastMCP docs, also noted in the README):

1. **`mcp.http_app(path="/")` — not `"/mcp"`.**  
   `app.mount("/mcp", mcp_app)` already adds the prefix. Setting both produces `/mcp/mcp`.

2. **`FastAPI(lifespan=mcp_app.lifespan)` at construction.**  
   Assigning `app.router.lifespan_context` later is too late. The MCP session manager never starts, and `/mcp` fails in a silent, confusing way.

`db.init_db()` runs at import time so the first request never hits a missing table. That is simple and fine for this app size. It is not a substitute for Alembic-style migrations.

---

## Persistence layer (`database.py`)

### Database file

```python
DB_PATH = Path(os.environ.get("TIMETRACK_DB_PATH", "/tmp/timetrack.db"))
```

| Environment | Default file | Note |
|---|---|---|
| Linux / macOS / many containers | `/tmp/timetrack.db` | Matches the default |
| Windows local | still `/tmp/timetrack.db` unless you override | Set `TIMETRACK_DB_PATH` to a real path such as `.\timetrack.db` |
| Tests / throwaway runs | any path you set | Lets you isolate data |

`.gitignore` ignores `*.db`, so the live database is never committed.

### Connection helper

`get_connection()` opens a new connection per call and sets `row_factory = sqlite3.Row` so columns are accessed by name (`row["hours"]`), not by index.

Each public function opens, uses, and closes its own connection. That is easy to follow. It is not a connection pool. For this single-user teaching app that is enough.

### Schema

One table. Projects and employees are **not** separate tables — they are strings on each row. A project “exists” only because at least one entry named it.

```
time_entries
├── id              INTEGER PRIMARY KEY AUTOINCREMENT
├── employee_name   TEXT NOT NULL
├── project         TEXT NOT NULL
├── entry_date      TEXT NOT NULL          -- ISO date YYYY-MM-DD
├── hours           REAL NOT NULL
└── description     TEXT NOT NULL DEFAULT ''
```

Seed data (inserted only when the table is empty):

| Employee | Project | Date | Hours | Description |
|---|---|---|---|---|
| Asha Patel | Website Redesign | 2026-09-08 | 6.5 | Homepage layout |
| Asha Patel | Website Redesign | 2026-09-09 | 7.0 | Mobile responsive fixes |
| Asha Patel | Client Onboarding | 2026-09-10 | 3.0 | Kickoff call + notes |
| Rahul Mehta | Website Redesign | 2026-09-08 | 5.5 | API integration |
| Rahul Mehta | Internal Tools | 2026-09-09 | 8.0 | Dashboard bug fixes |

### Public functions

Every function returns plain Python dicts/lists (or raises `ValueError`). No FastAPI and no FastMCP types leak into this module.

| Function | SQL idea | Used by |
|---|---|---|
| `init_db()` | `CREATE TABLE IF NOT EXISTS` + optional seed | import of `main.py` |
| `list_all_entries()` | `SELECT * ... ORDER BY entry_date DESC, id DESC` | `GET /api/entries` |
| `log_time(...)` | `INSERT` then `SELECT` the new row | `POST /api/entries`, MCP `log_time` |
| `get_timesheet(name, start, end)` | `WHERE employee_name = ?` plus optional date bounds | `GET /api/timesheet/{name}`, MCP `get_timesheet` |
| `list_projects()` | `SELECT DISTINCT project` | `GET /api/projects`, MCP `list_projects`, MCP resource |
| `get_project_summary(project)` | `SUM(hours) GROUP BY employee_name` | `GET /api/projects/{project}/summary`, MCP `get_project_summary` |
| `execute_query(query, params)` | caller-supplied SQL | **only** `main_to_understand.py` |

`log_time` rejects `hours <= 0`. `get_project_summary` raises if the project has no rows.

`execute_query` is a teaching hazard: it runs whatever SQL the caller sends. The production app (`main.py`) does **not** expose it.

### Row shape

`_row_to_dict` is the single serialization point:

```json
{
  "id": 1,
  "employee_name": "Asha Patel",
  "project": "Website Redesign",
  "entry_date": "2026-09-08",
  "hours": 6.5,
  "description": "Homepage layout"
}
```

`get_project_summary` returns a different shape:

```json
{
  "project": "Website Redesign",
  "total_hours": 19.0,
  "by_employee": {
    "Asha Patel": 13.5,
    "Rahul Mehta": 5.5
  }
}
```

---

## REST API (human / website door)

Defined on the FastAPI `app` in `main.py`. The browser never talks to MCP.

| Method | Path | Body / query | Database call |
|---|---|---|---|
| `GET` | `/api/entries` | — | `list_all_entries()` |
| `POST` | `/api/entries` | `NewEntry` JSON | `log_time(...)` |
| `GET` | `/api/projects` | — | `list_projects()` |
| `GET` | `/api/projects/{project}/summary` | path | `get_project_summary(project)` |
| `GET` | `/api/timesheet/{employee_name}` | optional `start_date`, `end_date` | `get_timesheet(...)` |
| `GET` | `/` | — | `FileResponse("static/index.html")` |
| static | `/static/*` | — | `StaticFiles(directory="static")` |

`NewEntry` fields: `employee_name`, `project`, `entry_date`, `hours`, `description=""`.

Interactive docs while the server is running: `http://127.0.0.1:8000/docs`.

There is no auth, no pagination, and no delete/update. That is deliberate for a learning app. Adding those later belongs in `database.py` first, then both doors.

---

## MCP server (assistant door)

Built with `FastMCP("TimeTrack")` **before** the FastAPI app exists, then converted:

```python
mcp_app = mcp.http_app(path="/")
app.mount("/mcp", mcp_app)
```

Transport is **Streamable HTTP** at `http://127.0.0.1:8000/mcp`.

MCP has three primitive types. This app uses all three.

### Tools (the model *does* something)

| Tool | Arguments | Returns | Same as REST |
|---|---|---|---|
| `log_time` | employee_name, project, entry_date, hours, description="" | new entry dict | `POST /api/entries` |
| `get_timesheet` | employee_name, start_date="", end_date="" | list of entries | `GET /api/timesheet/{name}` |
| `get_project_summary` | project | summary dict | `GET /api/projects/{project}/summary` |
| `list_projects` | — | list of names | `GET /api/projects` |

Empty strings on `get_timesheet` are converted to `None` so the SQL date filters stay optional (`start_date or None`).

Docstrings on these functions are **part of the API**. The model reads them to decide when to call a tool. Write them as instructions, not as comments for humans only.

### Resource (the model *reads* context)

| URI | Function | Purpose |
|---|---|---|
| `timesheet://projects` | `known_projects()` → `db.list_projects()` | Current project names so the model reuses existing spelling instead of inventing “website redesign” vs “Website Redesign” |

A resource is pullable context, not an action. It is the right primitive for “here is the current list of names.”

### Prompt (the model is *guided*)

| Prompt | Arguments | Purpose |
|---|---|---|
| `generate_weekly_report` | employee_name, week_start | Returns a text recipe: call `get_timesheet`, group by project, print a fixed report shape, do not invent hours |

A prompt is not a tool and does not touch the database. It is a reusable instruction the client can attach. That is how you keep the model from hallucinating a timesheet when the week is empty.

---

## Frontend (`static/`)

Three tabs, one HTML file, no bundler.

```
index.html
  ├── All Entries      table filled by GET /api/entries
  ├── Project Summary  select from GET /api/projects
  │                    button → GET /api/projects/{name}/summary
  └── Log Time         form → POST /api/entries
                       then reload entries + project list
```

`app.js` rules:

- Tab buttons toggle `.active` on `.tab` and `.view`.
- `escapeHtml` writes user text through a detached `div.textContent` so names and descriptions cannot inject HTML.
- After a successful log, it resets the form and refreshes both lists. That is how a browser user sees an MCP-logged row: refresh the Entries tab (or reload the page). There is no websocket.

The CSS is a single-file theme: slate background, white cards, blue accent, 900px main column.

---

## Request flows

### A. Person logs time in the browser

```
form submit
  → POST /api/entries  {employee_name, project, entry_date, hours, description}
  → NewEntry validated by Pydantic
  → db.log_time(...) INSERT
  → JSON of the new row
  → JS resets form, GET /api/entries, GET /api/projects
```

### B. Assistant logs time over MCP

```
user asks Claude: "Log 2 hours for Asha Patel on Website Redesign today"
  → client POSTs to /mcp
  → FastMCP dispatches tool log_time
  → db.log_time(...) INSERT   ← same function as A
  → tool result returned to the model
  → model replies in natural language
```

Open `/` and the new row is in the table.

### C. Project summary (either door)

```
SQL: SELECT employee_name, SUM(hours)
     FROM time_entries
     WHERE project = ?
     GROUP BY employee_name
```

REST wraps that in JSON for the Summary tab. MCP returns the same dict to the model so it can say “Website Redesign is 19 hours: Asha 13.5, Rahul 5.5.”

---

## Alternate files (not the production path)

### `dummy.py` — MCP-only, no website

A five-function calculator (`add`, `subtract`, `multiply`, `divide`, `power`). No FastAPI, no SQLite.

Purpose: the smallest possible Horizon / FastMCP Cloud deploy. Entrypoint is `dummy.py:mcp`. Useful when you want to learn “what is an MCP server” before “how do I mount it inside FastAPI.”

### `main_to_understand.py` — REST first, then auto-MCP

Written as a study file:

1. Build FastAPI + REST exactly like a normal API tutorial.
2. `mcp = FastMCP.from_fastapi(app=app)` so every route becomes a tool.
3. Extra: `execute_query_dynamically` + resource `timesheet://schema`.

Full walkthrough (blocks, `mcp.run()` trap, quiz): **[MAIN_TO_UNDERSTAND.md](MAIN_TO_UNDERSTAND.md)** · **[main-to-understand.html](main-to-understand.html)**.

Run it separately:

```bash
uv run uvicorn main_to_understand:app --port 9998 --reload
```

Swagger: `http://127.0.0.1:9998/docs`.

**Do not treat this as the production design.** Auto-wrapping REST is convenient for exploration. A raw SQL tool lets a model (or a prompt injection) `DROP TABLE` or read anything. `main.py` is the safer pattern: a short, named allow-list of tools.

---

## Deployment architecture

### Local

```
uv run uvicorn main:app --reload
```

| URL | Door |
|---|---|
| `http://127.0.0.1:8000` | Website |
| `http://127.0.0.1:8000/docs` | Swagger for REST |
| `http://127.0.0.1:8000/mcp` | MCP Streamable HTTP |

Claude Desktop config:

```json
{
  "mcpServers": {
    "timetrack": { "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

### Prefect Horizon (MCP-focused)

Formerly FastMCP Cloud. Connect the GitHub repo; dependencies come from `pyproject.toml`. Typical public URL: `https://your-project-name.fastmcp.app/mcp`.

Horizon is built for the MCP process. Static website routes may not ship with that deploy. If you need both doors on the public internet, deploy the whole uvicorn app to a general host (Railway, Render, a VM) instead.

For a Horizon-only smoke test, `dummy.py:mcp` is the smaller entrypoint.

---

## What this architecture deliberately leaves out

These are not missing by accident. They are the next layer after you can rebuild the current app.

- Authentication / multi-tenant isolation
- Update or delete of entries
- Separate `employees` and `projects` tables
- Migrations
- Connection pooling or an async DB driver
- WebSockets / live UI updates
- Tests (the original README claimed restart-and-recover proofs; there is no `tests/` tree in this repo)
- Input date-format validation beyond “whatever SQLite stores as TEXT”

---

## Mental model to keep

```
UI  ──REST──┐
            ├──  database.py  ──  SQLite
MCP ─tools──┘
```

If you remember only one sentence: **the website and the assistant are clients; `database.py` is the application.**
