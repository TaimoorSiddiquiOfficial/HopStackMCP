"""
HopStack UE Tools - FastMCP Server (Meta-Tools Pattern)

Instead of registering 774 individual tools (causing slow startup and token bloat),
this server exposes 3 meta-tools:
  1. list_available_tools - Returns compact catalog with optional filtering
  2. get_tool_schema - Returns full schema for a specific tool
  3. execute_ue_tool - Proxies execution to the UE plugin MCP server

This dramatically reduces:
  - MCP tools/list response size (774 tools -> 3 tools)
  - Token usage per API call
  - Response latency / stuck responses

Designed for HopCoderX and Railway deployment.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
import httpx

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
UE_PLUGIN_MCP_URL = os.environ.get("UE_PLUGIN_MCP_URL", "http://localhost:9315")

# ---------------------------------------------------------------------------
# Resolve JSON tool-definition files
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JSON_FILES = [
    DATA_DIR / "ue_cpp_api_tools_with_schema.json",
    DATA_DIR / "ue_cpp_api_tools_with_schema_more.json",
]

# ---------------------------------------------------------------------------
# Load & cache tool definitions
# ---------------------------------------------------------------------------
_tools_cache: list[dict] | None = None
_tools_by_name: dict[str, dict] | None = None


def load_tools() -> list[dict]:
    """Load all valid tool entries from JSON files (cached)."""
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache

    tools: list[dict] = []
    for path in JSON_FILES:
        if not path.exists():
            print(f"[WARN] Tool file not found: {path}", file=sys.stderr)
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            if "name" not in entry:
                continue
            tools.append(entry)

    _tools_cache = tools
    print(f"[INFO] Loaded {len(tools)} tool definitions from JSON files.")
    return tools


def get_tools_by_name() -> dict[str, dict]:
    """Get tools indexed by name (cached)."""
    global _tools_by_name
    if _tools_by_name is not None:
        return _tools_by_name

    tools = load_tools()
    _tools_by_name = {t["name"]: t for t in tools}
    return _tools_by_name


def get_tool_categories() -> list[str]:
    """Extract unique category prefixes from tool names.

    Tool names use dot notation: category.action_name
    e.g., blueprintgraph.spawn_function_node -> blueprintgraph
    """
    tools = load_tools()
    categories = set()
    for tool in tools:
        name = tool["name"]
        if "." in name:
            categories.add(name.split(".")[0])
        elif "_" in name:
            categories.add(name.split("_")[0])
        else:
            categories.add("general")
    return sorted(categories)


# ---------------------------------------------------------------------------
# Build the FastMCP server with Meta-Tools
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "HopStackMCP",
    instructions=(
        "MCP server for Unreal Engine 5 tool definitions from HopStack / Agent Integration Kit.\n\n"
        "This server uses a META-TOOLS pattern for efficiency:\n"
        "- Use `list_available_tools` to discover available UE tools (with optional filtering)\n"
        "- Use `get_tool_schema` to get the full parameter schema for a specific tool\n"
        "- Use `execute_ue_tool` to run any tool by name\n\n"
        "This approach avoids sending 700+ tool definitions in every request."
    ),
)


# ---------------------------------------------------------------------------
# Meta-Tool 1: list_available_tools
# ---------------------------------------------------------------------------
@mcp.tool()
async def list_available_tools(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List available Unreal Engine tools with optional filtering.

    Returns a compact catalog of tool names and short descriptions.
    Use this to discover tools before calling get_tool_schema or execute_ue_tool.

    Args:
        category: Filter by category prefix (e.g., 'blueprint', 'material', 'level', 'actor')
        search: Search term to filter tool names/descriptions (case-insensitive)
        limit: Maximum number of tools to return (default 50, max 200)
        offset: Pagination offset for large result sets

    Returns:
        Dictionary with:
        - tools: List of {name, description} objects
        - total: Total matching tools
        - categories: List of all available categories (when no filter applied)
        - has_more: Whether more results exist beyond limit
    """
    tools = load_tools()
    filtered = tools

    # Filter by category (tools use dot notation: category.action_name)
    if category:
        category_lower = category.lower()
        filtered = [
            t
            for t in filtered
            if t["name"].lower().startswith(category_lower + ".")
            or t["name"].lower().startswith(category_lower + "_")
            or t["name"].lower() == category_lower
        ]

    # Filter by search term
    if search:
        search_lower = search.lower()
        filtered = [
            t
            for t in filtered
            if search_lower in t["name"].lower()
            or search_lower in t.get("description", "").lower()
        ]

    total = len(filtered)

    # Apply pagination
    limit = min(limit, 200)  # Cap at 200
    paginated = filtered[offset : offset + limit]

    # Build compact result
    result_tools = []
    for tool in paginated:
        desc = tool.get("description", "")
        # Truncate description to save tokens
        if len(desc) > 100:
            desc = desc[:97] + "..."
        result_tools.append(
            {
                "name": tool["name"],
                "description": desc,
            }
        )

    result = {
        "tools": result_tools,
        "total": total,
        "returned": len(result_tools),
        "has_more": (offset + limit) < total,
    }

    # Include categories when no filter is applied
    if not category and not search and offset == 0:
        result["categories"] = get_tool_categories()

    return result


# ---------------------------------------------------------------------------
# Meta-Tool 2: get_tool_schema
# ---------------------------------------------------------------------------
@mcp.tool()
async def get_tool_schema(tool_name: str) -> dict[str, Any]:
    """
    Get the full JSON schema for a specific Unreal Engine tool.

    Returns the complete parameter schema including property names, types,
    descriptions, and required fields. Use this before execute_ue_tool
    when you need to know the exact parameters.

    Args:
        tool_name: Exact name of the tool (from list_available_tools)

    Returns:
        Dictionary with:
        - name: Tool name
        - description: Full description
        - inputSchema: Complete JSON Schema for parameters
        - found: Boolean indicating if tool was found
    """
    tools_by_name = get_tools_by_name()
    tool = tools_by_name.get(tool_name)

    if not tool:
        # Try case-insensitive search
        tool_name_lower = tool_name.lower()
        for name, t in tools_by_name.items():
            if name.lower() == tool_name_lower:
                tool = t
                break

    if not tool:
        return {
            "found": False,
            "error": f"Tool '{tool_name}' not found",
            "suggestion": "Use list_available_tools to find available tools",
        }

    return {
        "found": True,
        "name": tool["name"],
        "description": tool.get("description", ""),
        "inputSchema": tool.get("inputSchema", {}),
    }


# ---------------------------------------------------------------------------
# Meta-Tool 3: execute_ue_tool
# ---------------------------------------------------------------------------
@mcp.tool()
async def execute_ue_tool(
    tool_name: str, arguments: Optional[str] = None
) -> dict[str, Any]:
    """
    Execute an Unreal Engine tool by name.

    This proxies the tool call to the Agent Integration Kit MCP server
    running inside Unreal Engine. The UE plugin performs the actual operation.

    Args:
        tool_name: Exact name of the tool to execute
        arguments: JSON string of arguments for the tool (use get_tool_schema to see parameters)

    Returns:
        The result from the Unreal Engine tool execution
    """
    # Validate tool exists
    tools_by_name = get_tools_by_name()
    if tool_name not in tools_by_name:
        # Try case-insensitive
        found = False
        for name in tools_by_name:
            if name.lower() == tool_name.lower():
                tool_name = name
                found = True
                break
        if not found:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "suggestion": "Use list_available_tools to find available tools",
            }

    # Parse arguments
    args_dict = {}
    if arguments:
        try:
            args_dict = json.loads(arguments)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON in arguments: {e}",
                "arguments_received": arguments,
            }

    # Build MCP tool call request
    mcp_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": args_dict,
        },
    }

    # Proxy to UE plugin MCP server
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{UE_PLUGIN_MCP_URL}/mcp",
                json=mcp_request,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"UE Plugin returned HTTP {response.status_code}",
                    "details": response.text[:500] if response.text else None,
                    "hint": "Ensure Unreal Editor is running with Agent Integration Kit",
                }

            result = response.json()

            # Extract result from JSON-RPC response
            if "error" in result:
                return {
                    "success": False,
                    "error": result["error"].get("message", "Unknown error"),
                    "code": result["error"].get("code"),
                }

            if "result" in result:
                return {
                    "success": True,
                    "tool": tool_name,
                    "result": result["result"],
                }

            return {
                "success": True,
                "tool": tool_name,
                "result": result,
            }

    except httpx.ConnectError:
        return {
            "success": False,
            "error": "Cannot connect to Unreal Engine MCP server",
            "url": f"{UE_PLUGIN_MCP_URL}/mcp",
            "hint": "Ensure Unreal Editor is running with Agent Integration Kit plugin loaded",
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request to Unreal Engine timed out (60s)",
            "tool": tool_name,
            "hint": "The tool may still be executing. Check Unreal Editor.",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {e}",
            "tool": tool_name,
        }


# ---------------------------------------------------------------------------
# HTTP Endpoints for UE Plugin / External Consumers
# ---------------------------------------------------------------------------
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


async def tools_json_endpoint(request):
    """
    GET /tools.json - Returns tool definitions with optional filtering.

    Query params:
        compact=1 - Return only name/description (no schema)
        names_only=1 - Return just an array of tool names
        category=X - Filter by category prefix
        limit=N - Limit results (default: all)
        offset=N - Pagination offset
    """
    tools = load_tools()

    # Parse query params
    compact = request.query_params.get("compact") == "1"
    names_only = request.query_params.get("names_only") == "1"
    category = request.query_params.get("category")
    limit = request.query_params.get("limit")
    offset = int(request.query_params.get("offset", 0))

    # Filter by category (tools use dot notation: category.action_name)
    if category:
        category_lower = category.lower()
        tools = [
            t
            for t in tools
            if t["name"].lower().startswith(category_lower + ".")
            or t["name"].lower().startswith(category_lower + "_")
        ]

    # Apply pagination
    if limit:
        limit = int(limit)
        tools = tools[offset : offset + limit]
    elif offset > 0:
        tools = tools[offset:]

    # Format output
    if names_only:
        return JSONResponse([t["name"] for t in tools])

    if compact:
        return JSONResponse(
            [
                {"name": t["name"], "description": t.get("description", "")[:100]}
                for t in tools
            ]
        )

    return JSONResponse(tools)


async def tool_schema_endpoint(request):
    """
    GET /tool/{name}/schema - Returns full schema for a single tool.
    """
    tool_name = request.path_params["name"]
    tools_by_name = get_tools_by_name()

    tool = tools_by_name.get(tool_name)
    if not tool:
        # Case-insensitive fallback
        for name, t in tools_by_name.items():
            if name.lower() == tool_name.lower():
                tool = t
                break

    if not tool:
        return JSONResponse({"error": f"Tool '{tool_name}' not found"}, status_code=404)

    return JSONResponse(tool)


async def categories_endpoint(request):
    """
    GET /categories - Returns list of tool categories.
    """
    return JSONResponse(get_tool_categories())


async def health_endpoint(request):
    """GET /health - Lightweight health check."""
    tools = load_tools()
    return JSONResponse(
        {
            "status": "ok",
            "tools": len(tools),
            "mode": "meta-tools",
            "registered_mcp_tools": 3,
        }
    )


# Build combined ASGI app
_mcp_app = mcp.http_app(path="/mcp")

_extra_routes = Starlette(
    routes=[
        Route("/tools.json", tools_json_endpoint, methods=["GET"]),
        Route("/tool/{name:path}/schema", tool_schema_endpoint, methods=["GET"]),
        Route("/categories", categories_endpoint, methods=["GET"]),
        Route("/health", health_endpoint, methods=["GET"]),
    ],
)


async def combined_app(scope, receive, send):
    """ASGI app that routes HTTP endpoints to Starlette, MCP to FastMCP."""
    path = scope.get("path", "")
    if path in ("/tools.json", "/categories", "/health") or path.startswith("/tool/"):
        await _extra_routes(scope, receive, send)
    else:
        await _mcp_app(scope, receive, send)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"[INFO] Starting HopStackMCP server (Meta-Tools Mode) on 0.0.0.0:{port}")
    print(f"[INFO]   MCP endpoint    : /mcp (3 meta-tools)")
    print(f"[INFO]   Tools JSON      : /tools.json")
    print(f"[INFO]   Tool Schema     : /tool/{{name}}/schema")
    print(f"[INFO]   Categories      : /categories")
    print(f"[INFO]   Health check    : /health")
    print(f"[INFO]   UE Plugin URL   : {UE_PLUGIN_MCP_URL}")
    uvicorn.run(combined_app, host="0.0.0.0", port=port, ws="wsproto")
