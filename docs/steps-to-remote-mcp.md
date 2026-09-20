# How to host your MCP server remotely

Prefect Horizon (FastMCP Cloud). Sign in at [https://horizon.prefect.io](https://horizon.prefect.io/).
Build rules: [Horizon build system](https://docs.horizon.prefect.io/platform/build-system).

Source slide: [assets/steps-to-remote-mcp.png](../assets/steps-to-remote-mcp.png).

![How to host your MCP server remotely](../assets/steps-to-remote-mcp.png)

---

## Keep learning files in *this* git

This repo is the course project. **Do not delete** `docs/`, `assets/`, `static/`, or `main_to_understand.py` to make Horizon happy. They stay committed.

Horizon checks out the GitHub commit, then **installs one dependency file** and **imports one entrypoint**. Unused markdown and PNGs sit in the checkout; they are not the running server.

---

## Horizon form — Deploy Your Server

Sign in at [https://horizon.prefect.io](https://horizon.prefect.io/), connect GitHub, select
`mayankchugh-learning/time-track-mcp-server-application` on branch `main`.

### Required fields

| Form field | Value to type |
|---|---|
| Server name | `time-track-mcp-app-server` |
| Description | `TimeTrack MCP: log hours, list projects, timesheets, and project summaries from SQLite.` |
| Entrypoint | `mcp_server.py:mcp` |

Public URL (name + `.fastmcp.app/mcp`):

```text
https://time-track-mcp-app-server.fastmcp.app/mcp
```

Do **not** set Entrypoint to `main.py` or `main.py:mcp`. Importing `main.py` builds the website, mounts `StaticFiles`, and needs FastAPI.

### Advanced Configuration — can stay empty

You can leave **Requirements** and **Environment Variables** blank and click **Deploy Server**. That is a valid class deploy.

| Advanced field | If empty | If you fill it |
|---|---|---|
| Requirements | Horizon walks from the entrypoint folder and picks the first of `requirements.txt` → `uv.lock`+`pyproject.toml` → `pyproject.toml`. This repo hits root `requirements.txt`, so it installs `fastmcp` **and** FastAPI + uvicorn (unused at runtime). | `requirements-horizon.txt` — `fastmcp` only |
| Environment Variables | SQLite uses `timetrack.db` next to the code (`database.py` default). | `TIMETRACK_DB_PATH=/tmp/timetrack.db` — still ephemeral on Horizon; seed rows can vanish when the instance is replaced |

No API keys are required. One variable per line, `KEY=value`, if you add any.

Click **Deploy Server**. After the build succeeds, paste the public `/mcp` URL into Cursor or Claude Desktop. That door is MCP only. The website stays on local `uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000`.

---

## Slide steps (same idea)

1. This learning repo is fine as the GitHub source. Horizon only *runs* `mcp_server.py` + `database.py`.
2. Push `mcp_server.py` to GitHub **before** you deploy (Horizon builds the remote commit, not your unsaved laptop).
3. Sign in at [https://horizon.prefect.io](https://horizon.prefect.io/) with that GitHub account.
4. Select this repository, branch `main`.
5. Fill the form as in the table above. Advanced may stay empty.
6. Deploy. Horizon handles HTTPS, `/mcp`, and the public URL.

---

## What Horizon actually packages

From the [build system](https://docs.horizon.prefect.io/platform/build-system):

- It inspects the entrypoint with FastMCP. Import-time side effects fail the build.
- `main.py` mounts `./static` at import time — that is why it is not the entrypoint.
- Large unused files only slow the clone. They do not become tools.

What Horizon **runs**:

```text
mcp_server.py  →  database.py  →  SQLite
```

What stays in git for you, not for the public MCP process:

```text
docs/   assets/   static/   main.py   main_to_understand.py
mcp_http_connector/   LEARNING_*.md
```

---

## Optional later: a second tiny GitHub repo

The slide’s “clean separate repository” is only needed if you want Horizon’s clone itself to be four files. You can `git subtree` or copy:

- `mcp_server.py` (rename to `main.py` if you like, then entrypoint `main.py:mcp`)
- `database.py`
- `requirements-horizon.txt` (or a slim `pyproject.toml` + `uv.lock`)

This learning repo stays the place with notes and diagrams. Do that split only if clone size or “exactly what’s in the repo” becomes a problem. Same-repo + the table above is enough for class.

For a calculator-only smoke test with no database, a smaller entrypoint would be a dedicated `dummy.py:mcp`. Walkthrough: [DUMMY.md](DUMMY.md) · [dummy.html](dummy.html). Also [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md) Phase 9–10 and [ARCHITECTURE.md](ARCHITECTURE.md) (Prefect Horizon).
