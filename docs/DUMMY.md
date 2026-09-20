# `dummy.py` — Self-learning walkthrough

Open this guide beside [`dummy.py`](../dummy.py). Read a section, then look at the matching lines. This is the **smallest MCP server in the repo**: a calculator with no website and no database.

Study HTML (same content, nicer to browse): [dummy.html](dummy.html).

Horizon form values for TimeTrack itself: [steps-to-remote-mcp.md](steps-to-remote-mcp.md) (`mcp_server.py:mcp`). Production walkthrough: [MAIN.md](MAIN.md). Contrast file: [MAIN_TO_UNDERSTAND.md](MAIN_TO_UNDERSTAND.md).

---

## What you will be able to explain

- Why Horizon only needs an **importable module that exposes a `FastMCP` instance** — not FastAPI, not uvicorn, not a website.
- What the entrypoint string `dummy.py:mcp` actually means (`module` : `object`).
- Why `@mcp.tool` plus a type-hinted function plus a docstring is the whole public API.
- Why `divide` raises `ValueError` instead of returning a string, and what the client sees.
- Why `if __name__ == "__main__": mcp.run()` is STDIO, and why Horizon never uses that line.
- Why this file exists *next to* TimeTrack, not *instead of* it.

Estimated time: 20–40 minutes with the file open. Typing the five tools yourself first makes it stick.

---

## What this file is (and is not)

`dummy.py` answers one question: **what is the least you can ship as an MCP server?**

1. Import `FastMCP`.
2. Create `mcp = FastMCP("Calculator")`.
3. Decorate five functions.
4. Stop. Horizon imports `mcp`. A local CLI can `mcp.run()`.

It is **not** TimeTrack. It does not log hours, open SQLite, or serve HTML. The class Horizon entrypoint for this repo is still [`mcp_server.py:mcp`](../mcp_server.py). Use `dummy.py` when you want to prove “Horizon can import a FastMCP object” before you debug a database path.

| | This file (`dummy.py`) | TimeTrack MCP (`mcp_server.py`) | Production app (`main.py`) |
|---|---|---|---|
| Domain | Arithmetic | Billable hours | Hours + website + REST |
| FastAPI / uvicorn | None | None | Mounts `mcp` at `/mcp` |
| SQLite | None | `database.py` | Same, plus `/` and `/api` |
| Horizon entrypoint | `dummy.py:mcp` (smoke test) | `mcp_server.py:mcp` (class deploy) | Never — importing `main` builds the website |
| `mcp.run()` | Yes, STDIO when run as a script | Unused | Unused |

Official FastMCP docs make a split: **generate** MCP from FastAPI, versus **mount** MCP into FastAPI, versus **run MCP alone**. This file is the third path — the one Horizon is built for.

---

## Before you run it

You need `fastmcp` on the path. From this repo:

```bash
uv sync
uv run fastmcp inspect dummy.py:mcp
```

You should see five tools: `add`, `subtract`, `multiply`, `divide`, `power`. No resources. No prompts. No `timesheet://` URIs.

Local Inspector (browser UI over a STDIO child process):

```bash
uv run fastmcp dev dummy.py
```

Run as a script (same STDIO door, no Inspector):

```bash
uv run python dummy.py
```

There is **no** `http://127.0.0.1:8000` unless you add `--transport http` yourself. That is the point: this file has no website to forget.

Optional HTTP-only listen (still no FastAPI):

```bash
uv run fastmcp run dummy.py --transport http --port 8001
```

Then a client URL is `http://127.0.0.1:8001/mcp`.

---

## The file in three blocks

Read top to bottom. Python executes top to bottom at **import** time. Horizon and `fastmcp inspect` both **import** the module; they do not execute the `if __name__` block.

```
Lines ~1–19     Block A — Module docstring (the Horizon recipe)
Lines ~20–54    Block B — FastMCP instance + five tools
Lines ~57–58    Block C — mcp.run() (STDIO only when you run this file)
```

---

## Block A — The docstring is the deploy card (lines 1–19)

The triple-quoted string at the top is not decoration. It is the 30-second map for the next person who opens the file:

- Horizon wants `dummy.py:mcp`, not `dummy.py` and not `dummy.py:app`.
- Local test is `uv run fastmcp dev dummy.py`.
- A clean-repo deploy is this file plus a `fastmcp` dependency — no `static/`, no `database.py`.

`Entrypoint: dummy.py:mcp` is Python import syntax written as a form field:

```
dummy.py   →  the module Horizon imports
mcp        →  the FastMCP object that module must leave in its global namespace
```

If you renamed the instance to `server`, the form would be `dummy.py:server`. If you moved the file into a package `calc/server.py`, it would be `calc.server:mcp` or `calc/server.py:mcp` depending on how Horizon resolves the path. The idea does not change: **import this module, grab this object.**

Horizon inspects that object at import time. Side effects that need a running event loop, a missing `./static` folder, or a FastAPI mount will fail the build. That is why `main.py` is the wrong entrypoint and this file has none of those things.

---

## Block B — The whole server (lines 20–54)

```python
from fastmcp import FastMCP

mcp = FastMCP("Calculator")
```

`"Calculator"` is the **server name** the client shows. It is not a filename and not a URL. On Horizon you also type a **Server name** in the form (`calculator`); those two strings can differ. The form name becomes the public hostname (`calculator.fastmcp.app`). The constructor name is what Inspector / the host UI labels the tool list.

### Tools (the model *does* something)

| Tool | Arguments | Returns | Failure mode |
|---|---|---|---|
| `add` | `a: float`, `b: float` | `a + b` | None |
| `subtract` | `a: float`, `b: float` | `a - b` | None |
| `multiply` | `a: float`, `b: float` | `a * b` | None |
| `divide` | `a: float`, `b: float` | `a / b` | `ValueError` if `b == 0` |
| `power` | `base: float`, `exponent: float` | `base ** exponent` | None in this file |

Notes you should feel in your fingers:

- The decorator is `@mcp.tool` (no parentheses). FastMCP accepts `@mcp.tool()` too; stay consistent with this file.
- Tool **names** default to the function names. Clients call `add`, not `calculator_add`.
- Type hints become the JSON schema the host shows the model. `float` here is enough. You do not write an OpenAPI spec.
- The docstring is **part of the API**. The model reads it to decide when to call the tool. `divide` says it raises if `b` is 0 so the model can avoid that call, or recover when it happens.
- There is no resource and no prompt. Arithmetic does not need a vocabulary URI or a weekly-report recipe. Those appear in TimeTrack because hours have *names* that must stay consistent.

### Why `divide` raises instead of returning `"error"`

```python
if b == 0:
    raise ValueError("Cannot divide by zero.")
return a / b
```

A string return looks like success: the tool “worked,” the model might forward `"Cannot divide by zero."` as if it were a quotient, or retry with the same arguments. An exception is a **tool error**. FastMCP turns it into an error result. The host can show it and the model can change `b`.

Same idea as TimeTrack: `database.log_time` rejects `hours <= 0` by raising (or returning a structured failure). Do not paper over bad input with a happy-path string.

`power` does not special-case anything. `0 ** -1` and huge exponents can still blow up at runtime. That is fine for a smoke test. You would add a guard only if this were a product.

---

## Block C — `mcp.run()` is a local door (lines 57–58)

```python
if __name__ == "__main__":
    mcp.run()
```

This runs **only** when you execute the file (`python dummy.py` / `uv run python dummy.py`). Importing the module — Horizon, `fastmcp inspect`, `fastmcp dev`, `from dummy import mcp` — does **not** call `mcp.run()`.

Default `mcp.run()` is **STDIO**: the process reads JSON-RPC on stdin and writes on stdout. That is the local-subprocess door from the README table. Inspector uses it. Claude Desktop can use it with a `command` + `args` config.

Horizon never attaches to stdin. It imports `mcp` and serves Streamable HTTP for you. Leaving this `if __name__` block in the file does not hurt the deploy. Putting `mcp.run()` at **module top level** (no `if __name__`) *would* hang the import. That trap is why [`main_to_understand.py`](../main_to_understand.py) is careful about where the first `mcp.run()` sits.

| How you start it | Transport | Who speaks MCP |
|---|---|---|
| `uv run python dummy.py` | STDIO | Parent process (Inspector, `fastmcp run` default) |
| `uv run fastmcp dev dummy.py` | STDIO + Inspector UI | Browser Inspector |
| `uv run fastmcp run dummy.py --transport http` | Streamable HTTP | Any client with a URL |
| Horizon `dummy.py:mcp` | Streamable HTTP on a public URL | Cursor / Claude Desktop over the internet |

---

## What the model actually sees

People in Swagger think in **paths**. This file has no Swagger. The model sees **tool names**.

| MCP surface | Kind | Why the name is this |
|---|---|---|
| `add` | tool | You named the function |
| `subtract` | tool | You named the function |
| `multiply` | tool | You named the function |
| `divide` | tool | You named the function |
| `power` | tool | You named the function |

There is no `timesheet://projects`. There is no `generate_weekly_report`. If you `uv run fastmcp inspect dummy.py:mcp` and see extra tools, you pointed inspect at the wrong file.

Ask a connected client: “What is 12 divided by 4, then raise that to the power of 3?” It should call `divide` then `power` — two tools, not one clever local calculation it invents. That is the same discipline TimeTrack wants: **use the server, do not invent hours.**

---

## Horizon: calculator smoke test vs TimeTrack deploy

This learning repo can stay the GitHub source. Horizon only *runs* the entrypoint you type.

| Goal | Entrypoint | What gets imported |
|---|---|---|
| Prove Horizon works | `dummy.py:mcp` | Calculator. No SQLite. |
| Ship the class product | `mcp_server.py:mcp` | TimeTrack tools + `database.py` |
| Do not type this | `main.py:mcp` or `main.py` | Builds FastAPI, mounts `./static`, needs a website |

Form sketch for a calculator-only deploy (optional, usually a **separate** tiny repo):

| Form field | Value |
|---|---|
| Server name | `calculator` |
| Entrypoint | `dummy.py:mcp` |

Public URL shape: `https://calculator.fastmcp.app/mcp`.

The slide’s “clean separate repository” is for when you want Horizon’s clone to be four files. Copy `dummy.py` plus a slim `pyproject.toml` / `requirements.txt` that lists `fastmcp`. Do **not** delete `docs/` from *this* git to make that clone pretty. Same-repo + `mcp_server.py:mcp` is the class deploy; `dummy.py` is the isolation drill. Full form: [steps-to-remote-mcp.md](steps-to-remote-mcp.md).

---

## How this file teaches the other two

```
dummy.py            MCP alone. Decorator, docstring, entrypoint.
mcp_server.py       Same decorator shape, but each body calls database.py.
main.py             Imports that mcp object, wraps http_app, mounts /mcp next to a website.
main_to_understand  Opposite order: REST first, then FastMCP.from_fastapi.
```

After this file you should be able to say:

1. An MCP server is a **named object with decorated functions**, not a folder of HTTP routes.
2. Horizon’s job is **import + HTTP**, not “run my FastAPI app.”
3. TimeTrack is this file **plus a database and a second door** — not a different framework.

Then open [MAIN.md](MAIN.md) and watch the same `@mcp.tool` pattern grow a product.

---

## Practice (do these on a copy)

Do **not** tick these until you have actually done them.

1. Run `uv run fastmcp inspect dummy.py:mcp`. Write down the five tool names from the output, not from memory.
2. Change the `add` docstring. Re-run inspect. Find your text. That is why docstrings are the API.
3. Call `divide` with `b=0` from Inspector. Confirm you get an error, not a numeric result.
4. Temporarily rename `mcp = FastMCP("Calculator")` to `server = FastMCP("Calculator")` and update every `@mcp.tool` to `@server.tool`. Predict what the Horizon entrypoint must become. Then put `mcp` back.
5. Sketch one sentence: why `main.py` is the wrong Horizon entrypoint and `dummy.py` is a valid smoke test.

---

## Quiz (answers below — cover them)

**Q1.** Horizon runs `if __name__ == "__main__": mcp.run()`. True or false?

**Q2.** The entrypoint is `dummy.py`. True or false?

**Q3.** Why does `divide` raise `ValueError` instead of `return "Cannot divide by zero."`?

**Q4.** You run `uv run python dummy.py`. Can a browser open `/docs` and try `add`?

**Q5.** Why might you deploy `dummy.py` before `mcp_server.py` on a new Horizon account?

**Q6.** `FastMCP("Calculator")` must match the Horizon **Server name** field. True or false?

<details>
<summary>Answers</summary>

**A1. False.** Horizon imports the module and takes the `mcp` object. The `if __name__` block is for local STDIO only.

**A2. False.** The form is `dummy.py:mcp` — module plus the FastMCP instance name. `dummy.py` alone is a file, not an object.

**A3.** A string return looks like success. An exception is a tool error the host can surface so the model changes `b`.

**A4. No.** Default `mcp.run()` is STDIO. There is no FastAPI app and no Swagger. Use Inspector, `fastmcp run --transport http`, or Horizon for HTTP.

**A5.** If the calculator comes up, Horizon, GitHub, and the entrypoint syntax work. A later TimeTrack failure is then about SQLite or `database.py`, not “can Horizon import FastMCP.”

**A6. False.** The constructor string is the in-process server label. The form **Server name** becomes the public hostname. They can differ.

</details>

---

## Common failures while studying this file

| What you see | Likely cause |
|---|---|
| `ModuleNotFoundError: fastmcp` | Forgot `uv sync` / not using `uv run` |
| Inspect shows TimeTrack tools | You pointed at `mcp_server.py` or `main.py` |
| Horizon build fails on `static` or FastAPI | Entrypoint is `main.py`, not `dummy.py:mcp` |
| Import hangs | `mcp.run()` at module top level (no `if __name__`) |
| Client connects then sees no tools | Wrong URL, or you ran `python dummy.py` and pointed an HTTP client at it |
| `divide` “succeeds” with a sentence | You changed it to return a string; put the `ValueError` back |

---

## When you are done

You can say, without looking:

1. This file **is** an MCP server: one `FastMCP` object, five tools.
2. Horizon imports `dummy.py:mcp`. It does not run the file as `__main__`.
3. Docstrings and type hints are the schema. There is no OpenAPI here.
4. `mcp.run()` is the local STDIO door. HTTP is a different transport.
5. TimeTrack is this shape plus `database.py` (and, locally, a website mounted in `main.py`).

Then rebuild it from memory: [LEARNING_AND_REBUILD.md](LEARNING_AND_REBUILD.md) Phase 9. Then deploy TimeTrack: [steps-to-remote-mcp.md](steps-to-remote-mcp.md).

---

## Learner sign-off

Leave these unchecked until **you** have done them.

- [ ] I ran `uv run fastmcp inspect dummy.py:mcp` and saw exactly five tools
- [ ] I can explain `dummy.py:mcp` as module + object in one sentence
- [ ] I can say why Horizon does not execute `mcp.run()`
- [ ] I can say why this file has no FastAPI and why `main.py` is the wrong remote entrypoint
- [ ] I can contrast this calculator with `mcp_server.py` (same decorator, real product)
