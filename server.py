"""
HopStack UE Tools — FastMCP Server
Publishes ~684 Unreal Engine tools from JSON definitions via MCP over HTTP.
Designed for Railway deployment.
"""

import inspect
import json
import keyword
import os
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Resolve JSON tool-definition files
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# In the container the JSON files are copied next to server.py under data/
DATA_DIR = BASE_DIR / "data"
JSON_FILES = [
    DATA_DIR / "ue_cpp_api_tools_with_schema.json",
    DATA_DIR / "ue_cpp_api_tools_with_schema_more.json",
]

# ---------------------------------------------------------------------------
# Load & filter tool definitions
# ---------------------------------------------------------------------------

def load_tools() -> list[dict]:
    """Load all valid tool entries from both JSON files."""
    tools: list[dict] = []
    for path in JSON_FILES:
        if not path.exists():
            print(f"[WARN] Tool file not found: {path}", file=sys.stderr)
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            # Skip comment-only entries (no 'name' key)
            if "name" not in entry:
                continue
            tools.append(entry)
    return tools


# ---------------------------------------------------------------------------
# Build the FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "HopStackMCP",
    instructions=(
        "MCP server exposing Unreal Engine 5 tool definitions from the "
        "HopStack / Hyper Game Framework. Each tool describes a UE editor "
        "or runtime operation with its full input schema."
    ),
)


def _make_handler(tool_def: dict):
    """Create a handler function for a tool definition.

    The handler simply echoes back the tool metadata and whatever
    parameters the caller supplied — actual execution happens inside
    the Unreal Editor via the AgentIntegrationKit plugin.
    """
    schema = tool_def.get("inputSchema", {})
    props = schema.get("properties", {})
    required = schema.get("required", [])
    desc = tool_def.get("description", "No description.")
    name = tool_def["name"]

    # Build a dynamic function with the right signature for FastMCP
    async def handler(**kwargs: Any) -> dict:
        return {
            "tool": name,
            "description": desc,
            "parameters_received": kwargs,
            "status": "dispatched",
            "note": (
                "This tool definition is served by the MCP server. "
                "Actual execution is performed inside Unreal Engine "
                "via the AgentIntegrationKit plugin."
            ),
        }

    # Give the function a proper name & docstring so FastMCP picks it up
    handler.__name__ = name.replace(".", "_").replace("-", "_")
    handler.__qualname__ = handler.__name__
    handler.__doc__ = desc

    # Attach parameter annotations for FastMCP introspection
    # Sanitise Python reserved words (e.g. 'class', 'async') by appending '_'
    annotations: dict[str, Any] = {}
    for pname, pinfo in props.items():
        safe = pname + "_" if keyword.iskeyword(pname) else pname
        ptype = pinfo.get("type", "string")
        if ptype == "string":
            annotations[safe] = str
        elif ptype == "number":
            annotations[safe] = float
        elif ptype == "integer":
            annotations[safe] = int
        elif ptype == "boolean":
            annotations[safe] = bool
        elif ptype == "array":
            annotations[safe] = list
        elif ptype == "object":
            annotations[safe] = dict
        else:
            annotations[safe] = str
    annotations["return"] = dict
    handler.__annotations__ = annotations

    # Build parameter defaults: required params have no default, optional get None
    params = []
    for pname in props:
        safe = pname + "_" if keyword.iskeyword(pname) else pname
        if pname in required:
            params.append(
                inspect.Parameter(safe, inspect.Parameter.KEYWORD_ONLY)
            )
        else:
            params.append(
                inspect.Parameter(
                    safe, inspect.Parameter.KEYWORD_ONLY, default=None
                )
            )
    handler.__signature__ = inspect.Signature(params)

    return handler


def register_all_tools():
    """Dynamically register every tool from the JSON definitions."""
    tools = load_tools()
    print(f"[INFO] Loaded {len(tools)} tool definitions from JSON files.")

    registered = 0
    errors = 0
    for tool_def in tools:
        try:
            name = tool_def["name"]
            handler = _make_handler(tool_def)
            mcp.tool(name=name)(handler)
            registered += 1
        except Exception as exc:
            errors += 1
            print(
                f"[WARN] Failed to register tool '{tool_def.get('name', '?')}': {exc}",
                file=sys.stderr,
            )

    print(f"[INFO] Registered {registered} tools ({errors} errors).")


# Register on import so tools are ready when the server starts
register_all_tools()

# ---------------------------------------------------------------------------
# Raw JSON endpoint for UE C++ plugin consumption
# ---------------------------------------------------------------------------
# The UE plugin's FJsonToolLoader can GET /tools.json to receive the same
# JSON array it previously read from disk, enabling cloud-based tool sync.

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

_cached_tools_json: list[dict] | None = None


def _get_tools_json() -> list[dict]:
    """Return the merged tools array (cached after first call)."""
    global _cached_tools_json
    if _cached_tools_json is None:
        _cached_tools_json = load_tools()
    return _cached_tools_json


async def tools_json_endpoint(request):
    """GET /tools.json — returns the raw JSON tool definitions array."""
    return JSONResponse(_get_tools_json())


async def health_endpoint(request):
    """GET /health — lightweight health check."""
    return JSONResponse({"status": "ok", "tools": len(_get_tools_json())})


# Build a custom ASGI app that mounts both the MCP handler and /tools.json
_mcp_app = mcp.http_app(path="/mcp")

_extra_routes = Starlette(
    routes=[
        Route("/tools.json", tools_json_endpoint, methods=["GET"]),
        Route("/health", health_endpoint, methods=["GET"]),
    ],
)


async def combined_app(scope, receive, send):
    """ASGI app that routes /tools.json and /health to Starlette,
    everything else to the FastMCP HTTP handler."""
    path = scope.get("path", "")
    if path in ("/tools.json", "/health"):
        await _extra_routes(scope, receive, send)
    else:
        await _mcp_app(scope, receive, send)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"[INFO] Starting HopStackMCP server on 0.0.0.0:{port}")
    print(f"[INFO]   MCP endpoint : /mcp")
    print(f"[INFO]   Tools JSON   : /tools.json")
    print(f"[INFO]   Health check : /health")
    uvicorn.run(combined_app, host="0.0.0.0", port=port)
