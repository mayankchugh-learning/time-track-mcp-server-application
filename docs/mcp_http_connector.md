# MCP HTTP connector — curl tests

This file is a raw-protocol client for the **MCP-only HTTP** process:

```powershell
uv run fastmcp run .\main.py --transport http --port 8000
```

That command serves **only** `mcp = FastMCP("TimeTrack")` at
`http://127.0.0.1:8000/mcp`. It does **not** serve the FastAPI `app`
(website, Swagger, `/api/*`).

On Windows PowerShell, use `curl.exe` (plain `curl` is often
`Invoke-WebRequest`). Write JSON to a file and pass `--data-binary @file`
— inline `-d "{...}"` breaks on nested braces.

Verified against FastMCP 4.0.5 on this repo.

---

## What a browser GET will show (expected)

These are **not** bugs for `fastmcp run --transport http`.

```powershell
curl.exe -i http://127.0.0.1:8000/
curl.exe -i http://127.0.0.1:8000/docs
curl.exe -i http://127.0.0.1:8000/api/projects
curl.exe -i http://127.0.0.1:8000/mcp
```

| Request | Status | Meaning |
|---|---|---|
| `GET /` | 404 | Website lives on FastAPI `app` |
| `GET /docs` | 404 | Swagger lives on FastAPI `app` |
| `GET /api/projects` | 404 | REST lives on FastAPI `app` |
| `GET /mcp` | **400** (not 404) | MCP door is up. Browser GET has no session / wrong protocol |

Need `/`, `/docs`, and `/api`? Stop this process and run:

```powershell
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The MCP handshake below is the same on either process. The URL stays
`http://127.0.0.1:8000/mcp`.

---

## Handshake (required before any tool)

Streamable HTTP needs three things on every real call:

1. `Accept: application/json, text/event-stream` (both)
2. `initialize` → copy the `mcp-session-id` response header
3. `notifications/initialized` with that session id

Skip step 3 and later `tools/list` / `tools/call` fail with
“Invalid request parameters” or “before initialization was complete”.

Create these two files in the project root, then run the curls.

`init.json`

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}
```

`initialized.json`

```json
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
```

```powershell
# 1. Start a session. Copy mcp-session-id from the response headers.
curl.exe -i -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  --data-binary "@init.json"
```

Expected: `200`, `content-type: text/event-stream`, SSE `event: message`
with `serverInfo.name` = `TimeTrack`, and a header like:

```text
mcp-session-id: 139cce29b6d8432390396dc5cb28f9ac
```

```powershell
# 2. Paste the id. This returns 202 Accepted and an empty body.
$sid = "PASTE_SESSION_ID"

curl.exe -i -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@initialized.json"
```

Reuse `$sid` on every request below until you restart the server.

---

## List surface

`tools_list.json`

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

```powershell
curl.exe -i -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@tools_list.json"
```

Expected tools: `log_time`, `get_timesheet`, `get_project_summary`,
`list_projects`.

`resources_list.json`

```json
{"jsonrpc":"2.0","id":7,"method":"resources/list","params":{}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@resources_list.json"
```

Expected: `timesheet://projects`.

`prompts_list.json`

```json
{"jsonrpc":"2.0","id":9,"method":"prompts/list","params":{}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@prompts_list.json"
```

Expected: `generate_weekly_report`.

---

## Call every tool

`list_projects.json`

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_projects","arguments":{}}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@list_projects.json"
```

`get_timesheet.json`

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_timesheet","arguments":{"employee_name":"Asha Patel","start_date":"","end_date":""}}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@get_timesheet.json"
```

`get_project_summary.json`

```json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"get_project_summary","arguments":{"project":"Website Redesign"}}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@get_project_summary.json"
```

`log_time.json` — this **writes** a row. Change the date/name if you
do not want a smoke-test entry in SQLite.

```json
{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"log_time","arguments":{"employee_name":"Curl Tester","project":"Website Redesign","entry_date":"2026-09-20","hours":1.5,"description":"HTTP connector smoke test"}}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@log_time.json"
```

---

## Resource and prompt

`resources_read.json`

```json
{"jsonrpc":"2.0","id":8,"method":"resources/read","params":{"uri":"timesheet://projects"}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@resources_read.json"
```

`prompts_get.json`

```json
{"jsonrpc":"2.0","id":10,"method":"prompts/get","params":{"name":"generate_weekly_report","arguments":{"employee_name":"Asha Patel","week_start":"2026-09-14"}}}
```

```powershell
curl.exe -sS -X POST http://127.0.0.1:8000/mcp `
  -H "Content-Type: application/json" `
  -H "Accept: application/json, text/event-stream" `
  -H "Mcp-Session-Id: $sid" `
  --data-binary "@prompts_get.json"
```

A successful MCP reply is SSE, not pretty JSON:

```text
event: message
data: {"jsonrpc":"2.0","id":3,"result":{...}}
```

`isError: false` on `tools/call` means the tool ran.

---

## Other ways to test (easier than curl)

Curl proves you speak the protocol. For day-to-day checks, use a real
MCP client — it does the handshake for you.

### 1. FastMCP CLI (best next step)

Talks to the **already running** HTTP server:

```powershell
uv run fastmcp list http://127.0.0.1:8000/mcp --transport http --auth none --resources --prompts

uv run fastmcp call http://127.0.0.1:8000/mcp --transport http --auth none list_projects

uv run fastmcp call http://127.0.0.1:8000/mcp --transport http --auth none get_timesheet employee_name="Asha Patel"

uv run fastmcp call http://127.0.0.1:8000/mcp --transport http --auth none get_project_summary project="Website Redesign"

uv run fastmcp call http://127.0.0.1:8000/mcp --transport http --auth none --json timesheet://projects
```

`--auth none` skips the HTTP-client OAuth prompt. This server has no auth.

Inspect the **module** without connecting over HTTP (does not prove the
port is up):

```powershell
uv run fastmcp inspect main.py:mcp
```

### 2. FastMCP Python client

```python
import asyncio
from fastmcp import Client


async def main() -> None:
    async with Client("http://127.0.0.1:8000/mcp") as client:
        print(await client.list_tools())
        print(await client.call_tool("list_projects", {}))
        print(await client.read_resource("timesheet://projects"))


asyncio.run(main())
```

### 3. MCP Inspector

```powershell
uv run fastmcp dev .\main.py
```

Opens a browser UI. That path is **stdio** (Inspector launches the
server as a child process). To inspect the HTTP server you already
started, point Inspector at `http://127.0.0.1:8000/mcp` as a Streamable
HTTP URL instead of launching a new process.

### 4. Cursor / Claude Desktop

```json
{
  "mcpServers": {
    "timetrack": { "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

Restart the client, then ask it to list projects. That is the product
test: an assistant using the same door curl just opened.

### 5. Whole app (website + REST + MCP)

If you need to see the row appear on the website after `log_time`:

```powershell
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Then curl `/mcp` as above, **or** use Swagger at
`http://127.0.0.1:8000/docs` for the REST door. Both doors must see
the same SQLite rows.
