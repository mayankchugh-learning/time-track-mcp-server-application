# `main.py` — Self-learning walkthrough

Open this guide beside [`main.py`](../main.py). Read a section, then look at the matching lines. This is the **production file**: the one you run, mount, and ship.

Study HTML (same content, nicer to browse): [main.html](main.html).

Contrast file (REST first, then auto-wrap): [MAIN_TO_UNDERSTAND.md](MAIN_TO_UNDERSTAND.md). Architecture map: [ARCHITECTURE.md](ARCHITECTURE.md). Rebuild from empty: [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md).

---

## What you will be able to explain

- Why this file builds **MCP first**, then FastAPI, then mounts.
- Why every `@mcp.tool` is a one-liner into `database.py` — and why that is the whole architecture.
- What `mcp.http_app(path="/")` plus `app.mount("/mcp", mcp_app)` actually produces (one URL, not `/mcp/mcp`).
- Why `lifespan=mcp_app.lifespan` must be passed into `FastAPI(...)` **at construction**.
- Why a **resource** (`timesheet://projects`) and a **prompt** (`generate_weekly_report`) exist even though REST already lists projects.
- Why this file never exposes `execute_query` and never calls `FastMCP.from_fastapi`.

Estimated time: 45–90 minutes with the file open. Typing the tools yourself first makes it stick.

---

## What this file is (and is not)

TimeTrack is one idea: **billable hours in SQLite**, readable by a person (HTTP) and by an assistant (MCP).

This file is the **mounted production shape**:

1. Initialize SQLite once at import.
2. Declare a short, named allow-list of MCP tools, one resource, one prompt.
3. Turn that MCP server into an ASGI app with `http_app(path="/")`.
4. Build FastAPI **with the MCP lifespan wired in**.
5. Add REST + the website, then mount `/static` and `/mcp`.

It is **not** the walkthrough style (`FastAPI` first, then `FastMCP.from_fastapi`). That lives in [`main_to_understand.py`](../main_to_understand.py).

| | This file (`main.py`) | Learning file (`main_to_understand.py`) |
|---|---|---|
| Order | MCP tools first, then FastAPI with lifespan | FastAPI routes, then MCP |
| How tools appear | You name each `@mcp.tool` | Auto-wrap every route |
| Extra surface | Prompt + `timesheet://projects` | Raw SQL tool + `timesheet://schema` |
| HTTP `/mcp` | Mounted at `/mcp` | Not mounted |
| Run as script | Unused; uvicorn serves `app` | `mcp.run()` (STDIO) |
| Website | `FileResponse` + `/static` | None |

Official FastMCP docs make the same split: **generate an MCP server FROM FastAPI**, versus **mount an MCP server INTO FastAPI**. This file is the second path — the one you ship.

---

## Before you run it

The module does `import database as db` and `db.init_db()`. You need a sibling `database.py` with at least:

- `init_db()`
- `list_all_entries()`
- `list_projects()`
- `get_project_summary(project)`
- `get_timesheet(employee_name, start_date=None, end_date=None)`
- `log_time(...)`

You do **not** need `execute_query`. Production never calls it.

`database.py` defaults the SQLite file to a sibling `timetrack.db` (next to the code). Override with `TIMETRACK_DB_PATH` if you want a throwaway file.

```powershell
$env:TIMETRACK_DB_PATH = ".\timetrack.db"
```

---

## The file in four blocks

Read top to bottom. Python executes top to bottom at **import** time. Uvicorn imports `main:app`, so every decorator and `init_db()` has already run before the first request.

```
Lines ~1–27     Block A — Imports + init_db()
Lines ~29–78    Block B — Curated MCP (tools, resource, prompt)
Lines ~81–89    Block C — http_app + FastAPI lifespan
Lines ~92–131   Block D — REST, website, mounts
```

There is no `if __name__ == "__main__"`. The process is `uvicorn main:app`. That is a design choice, not an omission.

---

## Block A — Imports and startup (lines 1–27)

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastmcp import FastMCP

import database as db

db.init_db()
```

`init_db()` runs when the **module is imported**, not on the first request. Uvicorn imports `main:app`, so the table exists before the website or `/docs` loads. That is simple and fine for this size. It is not a migration system.

`StaticFiles` and `FileResponse` are used here (unlike the learning file, which imports `StaticFiles` and never uses it). This process serves a real website.

The module docstring at the top is the 30-second map: two front doors, one database, `uv run uvicorn main:app --reload`.

---

## Block B — Curated MCP first (lines 29–78)

```python
mcp = FastMCP("TimeTrack")
```

`"TimeTrack"` is the server name the client shows. Tools are **not** generated from OpenAPI. You write each one.

Hand-curated tools are the production pattern. Each decorator is a one-liner into `database.py`. Nothing is duplicated between the two doors.

### Tools (the model *does* something)

| Tool | Arguments | Returns | Same `db.*` as REST |
|---|---|---|---|
| `log_time` | employee_name, project, entry_date, hours, description="" | new entry dict | `POST /api/entries` |
| `get_timesheet` | employee_name, start_date="", end_date="" | list of entries | `GET /api/timesheet/{name}` |
| `get_project_summary` | project | summary dict | `GET /api/projects/{project}/summary` |
| `list_projects` | — | list of names | `GET /api/projects` |

Notes you should feel in your fingers:

- The decorator is `@mcp.tool` (no parentheses). FastMCP accepts `@mcp.tool()` too; stay consistent with this file.
- Tool **names** default to the function names. Clients call `log_time`, not `api_log_entry`.
- `start_date: str = ""` then `start_date or None` — MCP clients send strings more happily than `null`. `database.get_timesheet` treats a missing date as “no bound.”
- The docstring is **part of the API**. The model reads it to decide when to call the tool. Write it like a user-facing help line (`entry_date must be YYYY-MM-DD`), not a comment for humans only.

`log_time` rejects `hours <= 0` inside `database.py`. The MCP tool does not re-validate. One rule, two doors.

There is no `list_all_entries` tool. The website needs a dump of every row. The assistant does not — it asks for one employee or one project. That is least privilege in a small file: **REST can be wider than MCP**.

### Resource (the model *reads* context)

```python
@mcp.resource("timesheet://projects")
def known_projects() -> list[str]:
    """The current set of projects with logged time, for consistent naming."""
    return db.list_projects()
```

A **resource** is pullable context, not an action. `list_projects` (tool) and `known_projects` (resource) share `db.list_projects()`. Two primitives, one query.

Why both: a tool is “go fetch names now.” A resource is “here is the current vocabulary — reuse `Website Redesign`, do not invent `website redesign`.” Auto-wrap cannot express “this GET is also a resource” unless you pass `route_maps`.

The URI scheme `timesheet://` is yours. It is not an HTTP URL. Clients request it as an MCP resource.

### Prompt (the model is *guided*)

```python
@mcp.prompt
def generate_weekly_report(employee_name: str, week_start: str) -> str:
    """Guides the AI to build a structured weekly hours report from this server's own tools."""
    return f"""Build a weekly report for {employee_name}, starting {week_start}.
    ...
    If no entries are found for that week, say so plainly instead of inventing data.
    """
```

A prompt **does not query SQLite**. It returns text that tells the host which tool to call (`get_timesheet`) and how to format the answer. That is how you stop an empty week from becoming a hallucinated timesheet.

`from_fastapi` cannot invent this. Prompts are MCP-only. Interview line: **auto-wrap copies HTTP; curated tools add behavior HTTP never had.**

The f-string uses `{{employee_name}}` (doubled braces) so the template braces survive `.format`-style interpolation and reach the model as literal `{employee_name}` instructions.

---

## Block C — Turn MCP into ASGI, then build FastAPI (lines 81–89)

```python
mcp_app = mcp.http_app(path="/")

app = FastAPI(title="TimeTrack", lifespan=mcp_app.lifespan)
```

This is the block people get wrong. Two rules, verified against FastMCP’s own documentation (also in the file comments):

### Rule 1 — `path="/"` not `path="/mcp"`

`app.mount("/mcp", mcp_app)` (Block D) already adds the prefix. Setting both doubles up:

```
http_app(path="/mcp")  +  mount("/mcp")  →  /mcp/mcp
http_app(path="/")     +  mount("/mcp")  →  /mcp     ← correct
```

The comment in the file exists because this bug is easy, silent, and looks like “the client is misconfigured.”

### Rule 2 — lifespan at construction

FastMCP’s HTTP app owns a **session manager**. It must start and stop with the process. Passing `lifespan=mcp_app.lifespan` into `FastAPI(...)` is how uvicorn learns that.

Assigning `app.router.lifespan_context = mcp_app.lifespan` **after** `app` exists is too late. `/mcp` then fails in a silent, confusing way: the website works, the client connects and immediately dies.

Order in this block is intentional. Do not reverse it:

```
1. Decorate tools / resource / prompt on mcp
2. mcp_app = mcp.http_app(path="/")
3. app = FastAPI(..., lifespan=mcp_app.lifespan)
4. Then REST routes and mounts
```

You cannot mount `mcp_app` before it exists. You cannot pass `lifespan=` before `mcp_app` exists. MCP first is not ideology — it is a construction-order constraint.

---

## Block D — REST, website, mounts (lines 92–131)

### `NewEntry` and five API routes

`class NewEntry(BaseModel)` is the JSON body for `POST /api/entries`. Fields match `log_time` / the MCP tool:

- `employee_name: str`
- `project: str`
- `entry_date: str`
- `hours: float`
- `description: str = ""`

FastAPI uses this model to validate JSON and to draw the Swagger “Try it out” form. The MCP tool does **not** use `NewEntry`. The model talks MCP arguments, not HTTP bodies. Same fields, two schemas, one `db.log_time`.

| Method | Path | Function | Database call |
|---|---|---|---|
| `GET` | `/api/entries` | `api_list_entries` | `list_all_entries()` |
| `POST` | `/api/entries` | `api_log_entry` | `log_time(...)` |
| `GET` | `/api/projects` | `api_list_projects` | `list_projects()` |
| `GET` | `/api/projects/{project}/summary` | `api_project_summary` | `get_project_summary(project)` |
| `GET` | `/api/timesheet/{employee_name}` | `api_get_timesheet` | `get_timesheet(...)` |

REST `get_timesheet` takes `start_date: str = None` (query params). MCP `get_timesheet` takes `start_date: str = ""` then `or None`. Same database function, different empty-value conventions for each protocol.

The browser never talks to MCP. `static/app.js` only `fetch`es `/api/*`.

### Website door

```python
@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/mcp", mcp_app)
```

Declare `GET /` **before** the mounts. Mounts are prefix catch-alls. `/static` must exist so `index.html` can load `app.js` and `style.css`. `/mcp` is the assistant door.

Mount `/static` after the `/` route so a catch-all cannot shadow it. Mount `/mcp` last among these three so you can see the pairing `http_app(path="/")` + `mount("/mcp")` in one glance.

**Run the production process:**

```bash
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

| URL | Door |
|---|---|
| http://127.0.0.1:8000 | Website |
| http://127.0.0.1:8000/docs | Swagger for REST |
| http://127.0.0.1:8000/mcp | MCP Streamable HTTP |

**Checkpoint (you confirm after running)**

- [ ] `GET /api/projects` returns project names
- [ ] `GET /api/projects/Website%20Redesign/summary` returns a total and `by_employee`
- [ ] `POST /api/entries` creates a row that then appears in `GET /api/entries`
- [ ] `/` shows the three-tab website
- [ ] `/docs` lists REST routes only — tools do not appear as Swagger operations
- [ ] A GET to `/mcp` is **not** a FastAPI 404 (the handshake body is protocol-specific; “Not Found” means the two-path bug)

Optional inspect:

```bash
uv run fastmcp inspect main.py:mcp
```

You should see four tools, `timesheet://projects`, and `generate_weekly_report`.

---

## Two objects, one database

```
app      →  FastAPI   →  uvicorn serves this
mcp_app  →  FastMCP HTTP ASGI, mounted at /mcp
mcp      →  the tool/resource/prompt registry

Both doors ──► database.py ──► SQLite
```

`app` and `mcp` share data only because both call `db.*`. There is no hidden bus. If you add a third client later (CLI, Slack), you import `database` again.

```
Person ──HTTP──► FastAPI `app`  ──┐
                                   ├── database.py ── SQLite
Assistant ─MCP─► FastMCP `mcp` ──┘
```

Preferred habit: **`database.py` first, doors second.** Do not put SQL in a tool body. Do not put SQL in a route body. The website and the assistant are clients; `database.py` is the application.

---

## What the model actually sees

People in Swagger think in **paths**. Models think in **tool names**.

| MCP surface | Kind | Why the name is this |
|---|---|---|
| `log_time` | tool | You named the function |
| `get_timesheet` | tool | You named the function |
| `get_project_summary` | tool | You named the function |
| `list_projects` | tool | You named the function |
| `timesheet://projects` | resource | You chose the URI |
| `generate_weekly_report` | prompt | You named the function |

Compare to the learning file after `from_fastapi`: the model typically sees `api_list_projects`, `api_log_entry`, `api_get_timesheet` — HTTP names leaking into the tool list. You did not choose those; OpenAPI did.

Curated `log_time` can later call SQLite **or** `httpx.post("https://your-api/entries")` without changing the name the host already knows. Auto-wrap cannot say “this one tool hits two backends.”

---

## Request flows (same row, two doors)

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
user: "Log 2 hours for Asha Patel on Website Redesign today"
  → client POSTs to /mcp
  → FastMCP dispatches tool log_time
  → db.log_time(...) INSERT   ← same function as A
  → tool result returned to the model
  → model replies in natural language
```

Open `/` and the new row is in the table. No websocket. Refresh (or the form’s own reload of the table) is enough.

### C. Weekly report prompt

```
client attaches generate_weekly_report(employee_name, week_start)
  → model receives the recipe text
  → model calls get_timesheet
  → model groups by project and prints the fixed shape
  → empty week: "no entries" — the prompt said not to invent data
```

The prompt never opened SQLite. If the model skips the tool and invents hours, that is a host/model failure, not a missing SQL tool. Do not “fix” it by exposing `execute_query`.

---

## Connect a client

Claude Desktop / Cursor config for the running HTTP server:

```json
{
  "mcpServers": {
    "timetrack": { "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

Restart the client after saving. Then:

1. Ask it to list projects — it should call `list_projects` (or read `timesheet://projects`).
2. Log hours through the assistant, then refresh the website **All Entries** tab.
3. Log hours in the browser, then ask for that employee’s timesheet.
4. Ask for a weekly report starting `2026-09-08` — it should use the prompt + `get_timesheet`.

Both doors must see the same rows. That is the point of the project.

---

## Why this file is what you ship

1. **Control** — you choose tool names and docstrings. HTTP details stay on `/docs`.
2. **Privilege** — four tools. No generic SQL interpreter. REST may list all entries; MCP does not have to.
3. **Mounting** — Streamable HTTP at `/mcp` on the same process as the website. One port, one lifespan, one SQLite file.
4. **Startup order** — tools exist before `http_app`; lifespan is set at construction. No `mcp.run()` in the middle of the module.
5. **Prompts and resources** — weekly-report guidance and live project names cannot be generated from REST.

After you understand it, you can rebuild it from an empty folder: [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md) Phases 5–7.

---

## Practice (do these on a copy)

Do **not** tick these until you have actually done them.

1. Temporarily set `mcp.http_app(path="/mcp")` and restart. Predict the URL the client must hit. Check. Then put `path="/"` back.
2. Sketch two columns: REST `POST /api/entries` vs MCP `log_time`. Same `db.log_time`, different names, different empty-value conventions.
3. Add a one-line docstring change to `list_projects`. Restart, then `uv run fastmcp inspect main.py:mcp` and find your text.
4. Without adding SQL: add an MCP tool `get_entry(id)` **and** `GET /api/entries/{id}`. Change `database.py` first.
5. Compare this file to `main_to_understand.py`. Write one sentence: generate vs mount.

---

## Quiz (answers below — cover them)

**Q1.** `mcp.http_app(path="/")` means the MCP endpoint is `/`. True or false?

**Q2.** You run `uvicorn main:app --port 8000`. Can a browser call `log_time`? Can Swagger list it?

**Q3.** Why does `get_timesheet` take `start_date: str = ""` on MCP but `start_date: str = None` on REST?

**Q4.** A prompt is a SQL query. True or false?

**Q5.** You assign `app.router.lifespan_context = mcp_app.lifespan` after `app = FastAPI(title="TimeTrack")`. What breaks?

**Q6.** Why might a model invent a project named `website redesign` if you delete the resource but keep the `list_projects` tool?

<details>
<summary>Answers</summary>

**A1. False.** `path="/"` is the path *inside* the mounted sub-app. `app.mount("/mcp", mcp_app)` puts that sub-app at `/mcp`. The public URL is `/mcp`.

**A2.** The browser can hit `/mcp` with the MCP handshake, but the three-tab website never does — it only calls `/api/*`. Swagger lists REST routes only. `log_time` is an MCP tool, not a FastAPI path.

**A3.** Query params and JSON can be omitted (`null` / missing). Many MCP clients send empty strings more easily than `null`. `"" or None` is `None`, so `database.get_timesheet` skips the date bound.

**A4. False.** A prompt returns instructions. Tools (or REST) touch the database.

**A5.** The MCP session manager never starts with the process. `/mcp` fails quietly; the website still works. Pass `lifespan=` into the `FastAPI(...)` constructor.

**A6.** A tool is an action the model may forget to call. A resource is advertised as current context — the vocabulary sitting in front of the next `log_time`. Without it, the model guesses spelling. (It can still call `list_projects` if it thinks to. The resource makes the names hard to miss.)

</details>

---

## Common failures while studying this file

| What you see | Likely cause |
|---|---|
| `ModuleNotFoundError: database` | No sibling `database.py` |
| `/mcp` 404 or tools live under `/mcp/mcp` | `http_app(path="/mcp")` **and** `mount("/mcp")` |
| MCP client connects then immediately dies | Lifespan not passed into `FastAPI(...)` |
| Website works, `/docs` works, assistant sees nothing | Client URL is wrong, or you are running `main_to_understand` on 9998 |
| Seed rows missing on Windows | Old docs mentioned `/tmp/timetrack.db`; this repo defaults beside the code. Check `TIMETRACK_DB_PATH` if you overrode it |
| Summary `ValueError` | Project string must match seed spelling (`Website Redesign`) |
| Model invents hours | Prompt not used; do not “fix” by adding a SQL tool |
| `/` is 404 but `/docs` works | Missing `static/index.html` or `FileResponse` path is wrong |

---

## When you are done

You can say, without looking:

1. This file **mounts** a curated FastMCP app onto FastAPI.
2. The learning file **generates** MCP from OpenAPI and never mounts.
3. `app` and `mcp` are two objects; sharing data means sharing `database.py`.
4. `http_app(path="/")` + `mount("/mcp")` + `lifespan=` at construction.
5. Prompts and resources are why MCP is more than “REST with extra steps.”

Then rebuild it without looking: [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md) Phases 5–7. Then study the contrast file: [MAIN_TO_UNDERSTAND.md](MAIN_TO_UNDERSTAND.md).

---

## Learner sign-off

Leave these unchecked until **you** have done them.

- [ ] I ran the website on port 8000 and exercised every REST route plus the three tabs
- [ ] I can draw `app` vs `mcp` vs `mcp_app` and say which URL hits which
- [ ] I can explain the `/mcp/mcp` bug and the lifespan-at-construction rule in one sentence each
- [ ] I can explain why `timesheet://projects` and `generate_weekly_report` are not REST routes
- [ ] I can contrast this file with `FastMCP.from_fastapi` + `execute_query_dynamically`
