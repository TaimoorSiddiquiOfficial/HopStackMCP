# Deploy and Host HopStackMCP For Unreal Engine on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/i7I5Gr?referralCode=R7omnS&utm_medium=integration&utm_source=template&utm_campaign=generic)

HopStackMCP is a cloud MCP schema-discovery server that exposes **638 Unreal Engine 5 tool definitions** over the [Model Context Protocol](https://modelcontextprotocol.io/). It lets AI agents like Claude, GitHub Copilot, and Cursor discover the full UE5 editor API and parameter schemas — enabling intelligent AI-assisted Unreal Engine development through a live, self-hosted MCP endpoint.

## About Hosting HopStackMCP For Unreal Engine

Hosting HopStackMCP on Railway deploys a FastMCP Python server that publishes 638 Unreal Engine tool schemas as a live MCP endpoint. Railway builds the included Dockerfile (Python 3.12-slim, non-root container), injects the `PORT` environment variable, and provides a public HTTPS URL automatically. The server is entirely stateless — it loads tool definitions once from bundled JSON files, caches them in memory, and serves them to any MCP-compatible client. No database, storage volume, or external service is required. One Railway service instance handles production traffic comfortably. Updating tool definitions is as simple as pushing new JSON to the repository; Railway redeploys within seconds.

## Common Use Cases

- **AI-assisted UE5 development** — Connect Claude, GitHub Copilot, or Cursor to your MCP endpoint so they can discover all 638 Unreal Engine tool schemas and intelligently guide editor operations.
- **Headless / CI pipelines** — Provide AI automation scripts with a stable MCP endpoint to query tool signatures and parameter schemas during automated build or testing pipelines, where no local editor is available.
- **Custom tool integrations** — Fetch `/tools.json` from any client to receive the full machine-readable tool definition array for downstream processing or registry population.

## Dependencies for HopStackMCP For Unreal Engine Hosting

- **Python 3.12** — Runtime for the FastMCP server
- **fastmcp[http] ≥ 3.0** — MCP server framework providing the `/mcp` Streamable HTTP transport
- **uvicorn ≥ 0.30 + wsproto ≥ 1.2** — ASGI production server (wsproto replaces the deprecated websockets legacy backend)

### Deployment Dependencies

- [FastMCP](https://github.com/jlowin/fastmcp) — Python MCP server framework
- [Railway Dockerfile deployments](https://docs.railway.com/guides/dockerfiles) — Railway builds and runs the included `Dockerfile` automatically
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification) — Protocol this server implements (spec version `2025-03-26`)

### Implementation Details

The server dynamically registers each tool from JSON at startup using FastMCP's `mcp.tool()` decorator, building a proper Python function signature and type annotations so MCP clients receive full schema introspection:

```python
# Each tool from JSON becomes a live MCP-registered handler
async def handler(**kwargs) -> dict:
    return {
        "tool": name,
        "status": "dispatched",
        "note": "Tool schema served. Execution is handled by your local integration."
    }

mcp.tool(name="chaos.create_field")(handler)
```

Three endpoints are served from a single ASGI app:

```
POST/GET  /mcp         # MCP protocol (Streamable HTTP, spec 2025-03-26)
GET       /tools.json  # Raw JSON array of all tool definitions
GET       /health      # {"status":"ok","tools":638}
```

## Why Deploy HopStackMCP For Unreal Engine on Railway?

Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying HopStackMCP For Unreal Engine on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.

---

# HopStackMCP — Full Documentation

## Table of Contents

- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Endpoints](#endpoints)
- [Quickstart — Connect an AI Agent](#quickstart--connect-an-ai-agent)
  - [Claude Desktop](#claude-desktop)
  - [GitHub Copilot (VS Code)](#github-copilot-vs-code)
  - [Cursor](#cursor)
  - [Codex CLI](#codex-cli)
- [Deploy Your Own Instance](#deploy-your-own-instance)
  - [One-click Railway](#one-click-railway)
  - [Manual Railway (CLI)](#manual-railway-cli)
  - [Docker](#docker)
  - [Local development](#local-development)
- [Environment Variables](#environment-variables)
- [Tool Categories](#tool-categories)
- [Adding or Updating Tools](#adding-or-updating-tools)
- [FAQ](#faq)

---

## How It Works

HopStackMCP is a **schema-discovery** server — it tells AI agents *what* tools exist and *what parameters they accept*. After deploying on Railway you get a personal public HTTPS URL. Point any MCP-compatible client at `/mcp` and the full 638-tool schema is immediately available for AI-assisted development workflows.

```
AI Agent (Claude / Copilot / Cursor)
        │
        │  MCP over HTTP  (schema discovery + tool descriptions)
        ▼
  YOUR_RAILWAY_APP.up.railway.app   ← your deployed instance
        │
        │  /tools.json  (machine-readable tool definitions)
        ▼
  Any downstream integration or local execution environment
```

When an agent calls a tool, this server responds with:

```json
{
  "tool": "chaos.create_field",
  "status": "dispatched",
  "note": "Tool schema served. Execution is handled by your local integration."
}
```

---

## Architecture

| Component | Location | Purpose |
|---|---|---|
| `server.py` | This repo (Railway) | FastMCP HTTP server — schema discovery, `/tools.json`, `/health` |
| `data/*.json` | This repo | 638 tool definitions with full JSON input schemas |

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` / `GET` | `/mcp` | MCP protocol endpoint (Streamable HTTP, spec 2025-03-26) |
| `GET` | `/tools.json` | Raw JSON array of all 638 tool definitions |
| `GET` | `/health` | Lightweight health check, returns `{"status":"ok","tools":638}` |

### MCP Protocol Details

- **Spec version:** `2025-03-26` (Streamable HTTP)
- **Transport:** HTTP POST for requests, HTTP GET for SSE notification stream
- **Authentication:** None (tool definitions are public)

---

## Quickstart — Connect an AI Agent

After deploying, your server URL will be:

```
https://YOUR_RAILWAY_APP.up.railway.app
```

Replace `YOUR_RAILWAY_APP` with the subdomain Railway assigns to your deployment.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "HopStackMCP": {
      "url": "https://YOUR_RAILWAY_APP.up.railway.app/mcp",
      "transport": "http"
    }
  }
}
```

Restart Claude Desktop. The 638 UE5 tools will appear in Claude's tool list.

---

### GitHub Copilot (VS Code)

Add to your workspace `.vscode/mcp.json` (or user-level `settings.json`):

```json
{
  "servers": {
    "HopStackMCP": {
      "type": "http",
      "url": "https://YOUR_RAILWAY_APP.up.railway.app/mcp"
    }
  }
}
```

Open the Copilot Chat panel in agent mode. The tools appear automatically.

---

### Cursor

Open **Cursor Settings → MCP** and add a new server:

| Field | Value |
|---|---|
| Name | `HopStackMCP` |
| Type | `HTTP` |
| URL | `https://YOUR_RAILWAY_APP.up.railway.app/mcp` |

Or add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "HopStackMCP": {
      "url": "https://YOUR_RAILWAY_APP.up.railway.app/mcp",
      "transport": "streamable-http"
    }
  }
}
```

---

### Codex CLI

```bash
codex --mcp-server "https://YOUR_RAILWAY_APP.up.railway.app/mcp"
```

Or add to `~/.codex/config.toml`:

```toml
[[mcp_servers]]
name = "HopStackMCP"
url  = "https://YOUR_RAILWAY_APP.up.railway.app/mcp"
```

---

## Deploy Your Own Instance

### One-click Railway

Click the button at the top of this README. Railway will:

1. Clone this repo into your Railway account
2. Build the Docker image
3. Inject a `PORT` env var and start the server
4. Give you a public HTTPS URL

Use that URL wherever the examples above show `YOUR_RAILWAY_APP.up.railway.app`.

---

### Manual Railway (CLI)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create a new project and link it
railway init

# Deploy
railway up
```

---

### Docker

Build and run locally with Docker:

```bash
# Clone the repo
git clone https://github.com/TaimoorSiddiquiOfficial/HopStackMCP.git
cd HopStackMCP

# Build
docker build -t hopstackmcp .

# Run on port 8080
docker run -p 8080:8000 -e PORT=8000 hopstackmcp
```

Server available at `http://localhost:8080`.

---

### Local development

No Docker required:

```bash
git clone https://github.com/TaimoorSiddiquiOfficial/HopStackMCP.git
cd HopStackMCP

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run
python server.py
```

Server available at `http://localhost:8000`.

Health check:
```bash
curl http://localhost:8000/health
# {"status":"ok","tools":638}
```

List all tools (raw JSON):
```bash
curl http://localhost:8000/tools.json | python -m json.tool | head -60
```

Test MCP initialize:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

List first 5 tools via MCP:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Port the server listens on. Railway sets this automatically. |

---

## Tool Categories

The 638 tools span 149 category prefixes across the full Unreal Engine 5 C++ API surface:

| Category prefix | Example tools | Domain |
|---|---|---|
| `chaos` | `chaos.create_field`, `chaos.fracture` | Chaos Destruction |
| `cloth` | `cloth.configure_sim`, `cloth.set_wind` | Cloth Simulation |
| `sequencer` | `sequencer.add_track`, `sequencer.add_keyframe` | Cinematic Sequencer |
| `gas` | `gas.create_ability`, `gas.add_modifier` | Gameplay Ability System |
| `navsystem` | `navsystem.query_path`, `navsystem.rebuild` | Navigation |
| `livelink` | `livelink.add_source`, `livelink.list_subjects` | Live Link / MoCap |
| `commonui` | `commonui.list_widget_classes` | CommonUI Framework |
| `water` | `water.set_wave_settings` | Water System |
| `ikrig` | `ikrig.add_solver`, `ikrig.add_goal` | IK Rig |
| `massai` | `massai.list_processors` | Mass AI / ECS |
| `gamefeatures` | `gamefeatures.activate` | Game Features |
| `usd` | `usd.import_stage`, `usd.export` | USD Pipeline |
| `datasmith` | `datasmith.import` | Datasmith |
| `levelsnapshot` | `levelsnapshot.capture` | Level Snapshots |
| `composure` | `composure.add_layer` | Composure |
| *(+ 134 more)* | | |

Every tool includes a full **JSON Schema** (`inputSchema`) describing its parameters, types, required fields, and descriptions — making them explorable by any MCP client.

---

## Adding or Updating Tools

Tool definitions live in `data/`:

```
data/
  ue_cpp_api_tools_with_schema.json       # 398 tools
  ue_cpp_api_tools_with_schema_more.json  # 240 tools
```

Each entry follows this structure:

```json
{
  "name": "chaos.create_field",
  "description": "Create a Chaos physics field at a world location.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "field_type": {
        "type": "string",
        "description": "Field type: RadialFalloff, UniformVector, etc.",
        "enum": ["RadialFalloff", "UniformVector", "RadialVector"]
      },
      "radius": {
        "type": "number",
        "description": "Field influence radius in Unreal units."
      },
      "location": {
        "type": "object",
        "description": "World location {x, y, z}."
      }
    },
    "required": ["field_type"]
  }
}
```

**Tool name rules:**
- Max 128 characters
- Only `A-Z`, `a-z`, `0-9`, `_`, `-`, `.`
- Use `category.operation` convention (e.g. `chaos.create_field`)

After editing, redeploy to Railway:

```bash
git add data/
git commit -m "feat: add my_category tools"
git push
```

Railway auto-deploys on push to `main`.

---

## FAQ

**Q: Does this server execute code in my Unreal project?**  
No. All tool calls to this cloud server return `"status": "dispatched"`. This server provides schema discovery only. Actual execution is handled by whatever local integration you configure on your machine.

**Q: How do I update the tool definitions?**  
Edit the JSON files in `data/`, commit, and push to `main`. Railway deploys automatically within ~1 minute.

**Q: Can I run this on a self-hosted server instead of Railway?**  
Yes — see the [Docker](#docker) section. Any host that can run a Docker container works (Fly.io, Render, AWS ECS, etc.).

**Q: The `/tools.json` response is slow on first request — why?**  
The tools are cached in memory after the first load. Subsequent requests are instant. Railway containers cold-start on the first request after sleeping; this takes 1-3 seconds.

**Q: How do I add authentication?**  
Add an API key check in `server.py` before the `combined_app` dispatcher, or use Railway's built-in private networking to restrict access to trusted origins.

---

## Stack

| | |
|---|---|
| Runtime | Python 3.12 |
| MCP framework | [FastMCP](https://github.com/jlowin/fastmcp) ≥ 3.0 |
| HTTP server | [Uvicorn](https://www.uvicorn.org/) + wsproto |
| Deployment | [Railway](https://railway.com) |
| Container | Docker (python:3.12-slim, non-root) |

---

*HopStackMCP — Unreal Engine 5 tool schema server by Hop Trendy*
