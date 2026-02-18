"""Quick smoke test for the Railway-deployed HopStackMCP server."""

import httpx
import json
import random
import sys

URL = "https://hopstackmcp.up.railway.app/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream, application/json",
}


def post(body, sid=None):
    h = dict(HEADERS)
    if sid:
        h["Mcp-Session-Id"] = sid
    r = httpx.post(URL, content=json.dumps(body), headers=h, timeout=30)
    for line in r.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip()), r.headers.get("mcp-session-id")
    return None, None


# --- 1. Initialize ---
resp, sid = post({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "smoke-test", "version": "1.0"},
    },
})
assert resp and "result" in resp, f"Initialize failed: {resp}"
info = resp["result"]["serverInfo"]
print(f"[1/4] Initialize : OK  (server={info['name']} v{info['version']})")

# --- 2. List all tools ---
resp, _ = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sid)
assert resp and "result" in resp, f"tools/list failed: {resp}"
tools = resp["result"]["tools"]
print(f"[2/4] tools/list : {len(tools)} tools returned")

# --- 3. Call first tool with empty args ---
sample = tools[0]["name"]
resp, _ = post({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": sample, "arguments": {}}}, sid)
ok = resp and "result" in resp
print(f"[3/4] tools/call : {sample} -> {'OK' if ok else 'FAIL'}")

# --- 4. Spot-check 10 random tools ---
n = min(10, len(tools))
samples = random.sample(tools, n)
passed = 0
failed_names = []
for i, t in enumerate(samples):
    r, _ = post({"jsonrpc": "2.0", "id": 100 + i, "method": "tools/call", "params": {"name": t["name"], "arguments": {}}}, sid)
    if r and "result" in r:
        passed += 1
    else:
        failed_names.append(t["name"])
print(f"[4/4] Spot-check : {passed}/{n} random tools passed")
if failed_names:
    for fn in failed_names:
        print(f"       FAIL: {fn}")

# --- Summary ---
print(f"\n{'='*50}")
print(f"  Server  : {URL}")
print(f"  Tools   : {len(tools)}")
print(f"  Status  : {'ALL GOOD' if passed == n else f'{n - passed} FAILURES'}")
print(f"{'='*50}")
sys.exit(0 if passed == n else 1)
