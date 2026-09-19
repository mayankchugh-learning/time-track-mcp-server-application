# `main_to_understand.py` — Self-learning walkthrough

Open this guide beside [`main_to_understand.py`](../main_to_understand.py). Read a section, then look at the matching lines. Do not merge this file into production `main.py`.

Study HTML (same content, nicer to browse): [main-to-understand.html](main-to-understand.html).

Architecture map for the whole product: [ARCHITECTURE.md](ARCHITECTURE.md). Rebuild the app from empty: [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md).

---

## What you will be able to explain

- Why this file builds **REST first**, then wraps it as MCP.
- What `FastMCP.from_fastapi(app=app)` actually creates (a **second object**, not a new route on `/docs`).
- Why `uvicorn …:app` and `python main_to_understand.py` are **two different doors**.
- Why the first `if __name__ == "__main__"` sits in a dangerous place.
- Why `execute_query_dynamically` plus `timesheet://schema` is a teaching hazard.
- Why the commented `@mcp.tool` / resource / prompt block is the **production pattern**.

Estimated time: 45–90 minutes with the file open. Typing the REST routes yourself first makes it stick.

---

## What this file is (and is not)

TimeTrack is one idea: **billable hours in SQLite**, readable by a person (HTTP) and by an assistant (MCP).

This file is the **walkthrough style**:

1. Write a normal FastAPI API.
2. Convert that API into an MCP server in one line.
3. Optionally add MCP-only pieces (a raw SQL tool, a schema resource).
4. Leave the safer, hand-curated tools **commented** so you can compare.

It is **not** the mounted production shape (`FastMCP("TimeTrack")` first, then `http_app` + `app.mount("/mcp")`). That lives in production [`main.py`](../main.py). Walk through it in [MAIN.md](MAIN.md) or [main.html](main.html).

| | This file | Production `main.py` |
|---|---|---|
| Order | FastAPI routes, then MCP | MCP tools first, then FastAPI with lifespan |
| How tools appear | Auto-wrap every route | You name each `@mcp.tool` |
| Extra surface | Raw SQL tool + schema resource | Prompt + `timesheet://projects` |
| HTTP `/mcp` | Not mounted | Mounted at `/mcp` |
| Run as script | `mcp.run()` (STDIO) | Usually unused; uvicorn serves `app` |

Official FastMCP docs make the same split: **generate an MCP server FROM FastAPI**, versus **mount an MCP server INTO FastAPI**. This file is the first path only.

---

## Before you run it

The module does `import database as db` and `db.init_db()`. You need a sibling `database.py` with at least:

- `init_db()`
- `list_all_entries()`
- `list_projects()`
- `get_project_summary(project)`
- `get_timesheet(employee_name, start_date=None, end_date=None)`
- `log_time(...)`
- `execute_query(query, params)` — used only by this learning file

If `database.py` is missing in this folder, copy it from the complete TimeTrack project (or rebuild it from [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md) Phase 2) before running.

On Windows, point SQLite at a real path if your `database.py` defaults to `/tmp`:

```powershell
$env:TIMETRACK_DB_PATH = ".\timetrack.db"
```

---

## The file in four blocks

Read top to bottom. Python executes top to bottom at **import** time.

```
Lines ~1–45     Block A — REST API (FastAPI + Pydantic)
Lines ~48–67    Block B — Convert + first mcp.run()
Lines ~70–92    Block C — Extra MCP tool + schema resource
Lines ~94–138   Block D — Commented production primitives
Lines ~142–143  Duplicate mcp.run()  (dead if the first one already ran)
```

Unused leftover: `from fastapi.staticfiles import StaticFiles` is imported and never used. The production app mounts `./static`. This learning file never serves a website.

---

## Block A — REST first (lines 1–45)

### Imports and startup

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles   # unused here
import database as db
from pydantic import BaseModel

db.init_db()  # CREATE TABLE IF NOT EXISTS + seed if empty
```

`init_db()` runs when the **module is imported**, not on the first request. Uvicorn imports `main_to_understand:app`, so the table exists before Swagger loads. That is simple and fine for this size. It is not a migration system.

### The app object

```python
app = FastAPI(
    title="TimeTrack",
    description="A simple time tracking app with REST and MCP endpoints.",
    version="1.0.0",
)
```

`title` / `description` / `version` show up on `http://127.0.0.1:9998/docs`. They also feed the **OpenAPI spec**. `from_fastapi` reads that spec to invent MCP tools. Thin or missing docstrings become thin tool descriptions for the model.

### Five routes, one shared database

Every handler is a one-liner into `database.py`. REST does not own SQL.

| Method | Path | Function | Database call |
|---|---|---|---|
| `GET` | `/api/entries` | `api_list_all_entries` | `list_all_entries()` |
| `GET` | `/api/projects` | `api_list_projects` | `list_projects()` |
| `GET` | `/api/projects/{project}/summary` | `api_project_summary` | `get_project_summary(project)` |
| `GET` | `/api/timesheet/{employee_name}` | `api_get_timesheet` | `get_timesheet(...)` |
| `POST` | `/api/entries` | `api_log_entry` | `log_time(...)` |

Only `api_list_all_entries` has a docstring. After `from_fastapi`, that docstring becomes the tool description. The other four inherit names like `api_list_projects` and almost no help text. That is one reason auto-wrap is a weak long-term API: **HTTP names leak into the model’s tool list**.

### `NewEntry` sits in the middle on purpose

`class NewEntry(BaseModel)` is defined **after** the GET routes and **before** `POST /api/entries`. That is legal: Python only needs the class to exist when `@app.post` runs. Pydantic fields:

- `employee_name: str`
- `project: str`
- `entry_date: str`
- `hours: float`
- `description: str = ""`

FastAPI uses this model to validate JSON and to draw the Swagger “Try it out” form. The MCP auto-tool for POST will ask the model for the same fields.

### Comments at the bottom of Block A

```text
uvicorn main_to_understand:app --port 9998
uv run uvicorn main_to_understand:app --port 9998 --reload
http://127.0.0.1:9998/docs
```

The comment in the file says `-reload` (one dash). The real flag is `--reload`. Port **9998** keeps this learning server off production **8000**.

**Run the REST door:**

```bash
uv run uvicorn main_to_understand:app --port 9998 --reload
```

Open `http://127.0.0.1:9998/docs`. This process serves **`app`**. It does **not** start `mcp.run()`.

**Checkpoint (you confirm after running)**

- [ ] `GET /api/projects` returns project names
- [ ] `GET /api/projects/Website%20Redesign/summary` returns a total and `by_employee`
- [ ] `POST /api/entries` creates a row that then appears in `GET /api/entries`
- [ ] You noticed `/docs` lists REST routes only — there is no `/mcp` in Swagger

---

## Block B — `from_fastapi` (lines 54–67)

```python
from fastmcp import FastMCP

mcp = FastMCP.from_fastapi(app=app)

if __name__ == "__main__":
    mcp.run()
```

### What `from_fastapi` does

It does **not** add routes to `app`. It builds a **new** FastMCP server whose tools are generated from `app.openapi()`. Default mapping: **every HTTP endpoint becomes an MCP tool**.

Two objects now exist in memory:

```
app  →  FastAPI   →  uvicorn serves this   →  browser / Swagger / curl
mcp  →  FastMCP   →  mcp.run() serves this →  STDIO MCP client (Inspector, Desktop)
```

They share `database.py` only because the FastAPI handlers (and any extra MCP tools you add later) call `db.*`. There is still **no** `app.mount("/mcp")` in this file. A GET to `http://127.0.0.1:9998/mcp` is a FastAPI 404.

FastMCP docs: you can still decorate extra tools/resources on the converted `mcp`. This file does that in Block C — **after** the first `mcp.run()`.

### Two ways to start, two different programs

| Command | `__name__` | What starts | What the client sees |
|---|---|---|---|
| `uv run uvicorn main_to_understand:app --port 9998` | `main_to_understand` | FastAPI ASGI | REST + `/docs` |
| `python main_to_understand.py` | `"__main__"` | `mcp.run()` (STDIO by default) | MCP tools over a pipe |

Uvicorn **imports** the module, so both `if __name__ == "__main__"` blocks are skipped. Block C still runs at import time, so the in-memory `mcp` object **does** get the extra tool and resource — they are just unused unless something calls `mcp.run()` or you mount `mcp`.

`python main_to_understand.py` is the opposite: it hits the **first** `mcp.run()` immediately.

### The trap: `mcp.run()` before extra tools

`mcp.run()` is a **blocking** server loop. It does not return.

When you start the file as a script:

```
1. Build FastAPI routes
2. mcp = from_fastapi(app)
3. mcp.run()          ← process sits here forever
4. execute_query_…    ← never registered
5. timesheet://schema ← never registered
6. second mcp.run()   ← dead code
```

So the extra SQL tool and schema resource **only exist** if the module is imported without hitting that first `if __name__` (uvicorn, `fastmcp run`, a test import) **or** if you move `mcp.run()` to the **bottom** of the file.

That first `if __name__` is the lesson, not a style to copy. Keep one `mcp.run()` at the end.

---

## Block C — Extra MCP-only surface (lines 70–92)

These are not REST routes. They exist only on `mcp`.

### Tool: `execute_query_dynamically`

```python
@mcp.tool()
def execute_query_dynamically(query: str, params: list = []) -> list[dict]:
    """Execute a custom SQL query with optional parameters.
    Access the resource for schema so that you know the tables etc."""
    return db.execute_query(query, params)
```

`@mcp.tool()` and `@mcp.tool` are both accepted. Production TimeTrack uses `@mcp.tool` (no parens). Stay consistent.

This tool is **text-to-SQL**: the model invents a query string. Combined with `db.execute_query`, that is:

- Powerful for a 10-minute demo (“show me Asha’s hours last week”).
- Unsafe to ship: `DROP TABLE`, `UPDATE … hours = 999`, reading anything the connection can see.
- Easy to break: `database.execute_query` typically maps rows through `_row_to_dict`, which expects `time_entries` columns. `SELECT COUNT(*)` or a join can crash instead of returning a useful result.

Least privilege: expose `log_time` / `get_timesheet` / `get_project_summary` / `list_projects`. Do not expose a generic SQL interpreter.

### Resource: `timesheet://schema`

```python
@mcp.resource("timesheet://schema")
def get_schema() -> dict:
    """Return the database schema for reference."""
    return { "tables": { "time_entries": { "columns": { ... } } } }
```

A **resource** is pullable context, not an action. The docstring even tells the model to read it before writing SQL.

The dict is a **hand-written snapshot**, not `PRAGMA table_info`. If you add a column in `database.py` and forget this resource, the model’s map is stale. Production TimeTrack uses `timesheet://projects` (live `list_projects()`) so spelling stays consistent — a better use of a resource than duplicating DDL.

MCP primitives in one sentence each:

| Primitive | Job in this file |
|---|---|
| Tool | Do something (`execute_query_dynamically`, plus auto-wrapped routes) |
| Resource | Read context (`timesheet://schema`) |
| Prompt | Guide the next tool calls (commented out in Block D) |

---

## Block D — The commented production pattern (lines 94–138)

Uncomment these in your **head**, not in this file. They are what production `main.py` actually ships.

| Kind | Name | Why it exists |
|---|---|---|
| Tool | `log_time` | Insert; docstring tells the model `YYYY-MM-DD` |
| Tool | `get_timesheet` | `start_date=""` then `or None` — clients send strings more easily than `null` |
| Tool | `get_project_summary` | `GROUP BY` employee, already shaped for speech |
| Tool | `list_projects` | Distinct names |
| Resource | `timesheet://projects` | Same list, as **context** so the model reuses “Website Redesign” |
| Prompt | `generate_weekly_report` | Recipe: call `get_timesheet`, group, do not invent hours |

A prompt **does not query SQLite**. It returns text that tells the host which tool to call and how to format the answer. That is how you stop an empty week from becoming a hallucinated timesheet.

Notice `list_projects` (tool) and `known_projects` (resource) share `db.list_projects()`. Two primitives, one query. Auto-wrap cannot express “this GET is also a resource” unless you pass `route_maps`.

`from_fastapi` also cannot invent `generate_weekly_report`. Prompts are MCP-only. That is the interview line: **auto-wrap copies HTTP; curated tools add behavior HTTP never had.**

---

## What the model actually sees after auto-wrap

Approximate tool list if Block B runs (names follow FastAPI function names / OpenAPI operation ids):

| MCP tool (typical) | Came from |
|---|---|
| `api_list_all_entries` | `GET /api/entries` |
| `api_list_projects` | `GET /api/projects` |
| `api_project_summary` | `GET /api/projects/{project}/summary` |
| `api_get_timesheet` | `GET /api/timesheet/{employee_name}` |
| `api_log_entry` | `POST /api/entries` |
| `execute_query_dynamically` | Block C (if registered) |

A person in Swagger thinks in **paths**. A model thinks in **tool names**. `api_get_timesheet` is worse than `get_timesheet`. You did not choose the MCP names; OpenAPI did.

One tool may call two backends. Auto-wrap cannot say that. Curated `log_time` can call SQLite **or** `httpx.post("https://your-api/entries")` without changing the tool name the host already knows.

---

## Mental model

```
Person ──HTTP──► FastAPI `app` ──┐
                                 ├── database.py ── SQLite
Assistant ─MCP─► FastMCP `mcp` ──┘
```

Preferred production habit: **APIs (or `database.py`) first, MCP second.** Do not mutate a working OpenAPI description just to get nicer tool docs. Write tools that call the functions you already trust.

FastAPI and FastMCP are **different products** that happen to compose. `/docs` is the FastAPI inspector. MCP Inspector / Claude Desktop is the MCP inspector.

---

## Why this file is not what you ship

1. **Control** — route names and HTTP details leak; you cannot combine two APIs into one tool.
2. **Privilege** — `execute_query_dynamically` is a database root shell for the model (and for prompt injection).
3. **Mounting** — assistants that speak Streamable HTTP need `/mcp` on the same process as the website. This file never mounts.
4. **Startup order** — `mcp.run()` in the middle of the module drops later primitives when run as a script.
5. **Prompts** — weekly report guidance cannot be generated from REST.

After you understand it, close this file and keep shipping curated tools.

---

## Practice (do these on a copy)

Do **not** tick these until you have actually done them.

1. Move the first `if __name__ == "__main__": mcp.run()` to the bottom. Predict whether Inspector then lists `execute_query_dynamically`. Check.
2. Add a one-line docstring to `api_list_projects`. Restart uvicorn, open `/docs`, then inspect the generated MCP tool description (Inspector or `uv run fastmcp inspect main_to_understand.py:mcp`).
3. Sketch two columns: REST `POST /api/entries` vs curated MCP `log_time`. Same `db.log_time`, different names.
4. Write the URL you get if you later `mcp.http_app(path="/mcp")` **and** `app.mount("/mcp", …)` (answer: `/mcp/mcp`).
5. Without running SQL through the model: add a curated `list_projects` and leave `execute_query_dynamically` commented. Which tool would you rather an assistant call?

---

## Quiz (answers below — cover them)

**Q1.** `from_fastapi` adds `/mcp` to the FastAPI app. True or false?

**Q2.** You run `uvicorn main_to_understand:app --port 9998`. Does `execute_query_dynamically` get defined on the `mcp` object? Can a browser call it?

**Q3.** You run `python main_to_understand.py` with the file as committed. Does the schema resource register?

**Q4.** Why might a model invent a project named `website redesign` when using auto-wrapped tools but not when using `timesheet://projects`?

**Q5.** A prompt is a SQL query. True or false?

<details>
<summary>Answers</summary>

**A1. False.** `from_fastapi` builds a separate FastMCP instance. `/mcp` appears only if you mount `mcp.http_app(...)`.

**A2.** Yes, it is defined: uvicorn imports the whole module and skips `mcp.run()`. No, the browser cannot call it: uvicorn serves `app`, not `mcp`. There is no HTTP route for that tool.

**A3. No.** The first `mcp.run()` blocks before `@mcp.resource` runs.

**A4.** Auto-wrap does not give the model a live list of canonical names. A resource that returns `list_projects()` does. Without it, the model guesses spelling.

**A5. False.** A prompt returns instructions. Tools (or REST) touch the database.

</details>

---

## Common failures while studying this file

| What you see | Likely cause |
|---|---|
| `ModuleNotFoundError: database` | No sibling `database.py` |
| `/docs` works, `/mcp` 404 | Expected in this file — nothing is mounted |
| Inspector missing `execute_query_dynamically` | You started `python main_to_understand.py` and hit the first `mcp.run()` |
| Swagger `Try it out` fails on summary | Project string must match seed spelling (`Website Redesign`) |
| Model writes `DROP TABLE` or odd SQL | You left the generic SQL tool enabled |
| `-reload` does nothing | Flag is `--reload` |

---

## When you are done

You can say, without looking:

1. This file teaches **generate MCP from OpenAPI**.
2. Production TimeTrack **mounts** a curated FastMCP app onto FastAPI.
3. `mcp` and `app` are two objects; sharing data means sharing `database.py`.
4. Raw SQL tools violate least privilege.
5. Prompts and resources are why MCP is more than “REST with extra steps.”

Then go rebuild the mounted shape: [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md) Phases 5–7. Production file walkthrough: [MAIN.md](MAIN.md).

---

## Learner sign-off

Leave these unchecked until **you** have done them.

- [ ] I ran Swagger on port 9998 and exercised every REST route
- [ ] I can draw `app` vs `mcp` and say which command starts which
- [ ] I can explain the first `if __name__` trap in one sentence
- [ ] I can explain why `execute_query_dynamically` should not ship
- [ ] I can contrast this file with curated `@mcp.tool` + `timesheet://projects` + weekly-report prompt
