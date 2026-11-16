"""A3: OpenBB's MCP server as the wrapper for our research server (V2-D19).

Run in a venv with openbb-mcp-server (repo commit), from outside the repo:
    python -I a3_mcp_server.py results.json

A small FastAPI app stands in for our research API: `research/*` routes (allowed)
and `admin/*` routes (must never be reachable from a chat: e.g. "set the trial
count", "delete a trial"). Every call increments a counter inside the app, so we
can see whether a forbidden route was reached, whatever the MCP layer reports.
Rules: PREREGISTERED.md (A3 a/b/c).
"""
import asyncio
import json
import socket
import sys
import threading
import time

from fastapi import FastAPI
from fastmcp import Client
from openbb_mcp_server.app.app import create_mcp_server
from openbb_mcp_server.models.settings import MCPSettings

HITS = {"research": 0, "admin": 0}


def make_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/research/backtest")
    def research_backtest(strategy: str = "ma") -> dict:
        HITS["research"] += 1
        return {"strategy": strategy, "trial_id": "t1"}

    @app.get("/api/v1/research/prices")
    def research_prices(symbol: str = "BTC") -> dict:
        HITS["research"] += 1
        return {"symbol": symbol, "rows": 3}

    @app.get("/api/v1/admin/set_trial_count")
    def admin_set_trial_count(n: int = 0) -> dict:
        HITS["admin"] += 1
        return {"trial_count": n}

    @app.get("/api/v1/admin/delete_trial")
    def admin_delete_trial(trial_id: str = "t1") -> dict:
        HITS["admin"] += 1
        return {"deleted": trial_id}

    return app


async def probe(mcp, label):
    """List tools and try every route to the admin endpoints a client could use."""
    out = {"label": label}
    before = dict(HITS)
    async with Client(mcp) as c:
        tools = [t.name for t in await c.list_tools()]
        out["tools_listed"] = sorted(tools)
        attempts = {}
        for name in ("admin_set_trial_count", "admin_delete_trial"):
            try:
                r = await c.call_tool(name, {"n": 999} if "count" in name else {"trial_id": "t1"})
                attempts[f"direct:{name}"] = "called"
            except Exception as e:
                attempts[f"direct:{name}"] = f"refused: {type(e).__name__}: {str(e)[:120]}"
        if "call_tool" in tools:
            try:
                await c.call_tool("call_tool", {"tool_name": "admin_set_trial_count", "parameters": {"n": 999}})
                attempts["via call_tool"] = "called"
            except Exception as e:
                attempts["via call_tool"] = f"refused: {type(e).__name__}: {str(e)[:120]}"
        pipe = [t for t in tools if "pipeline" in t]
        for p in pipe:
            schema = None
            for t in await c.list_tools():
                if t.name == p:
                    schema = t.inputSchema
            try:
                await c.call_tool(p, {"steps": [{"tool": "admin_set_trial_count", "params": {"n": 999}}]})
                attempts[f"via {p}"] = "called"
            except Exception as e:
                attempts[f"via {p}"] = f"refused: {type(e).__name__}: {str(e)[:160]}"
            out[f"{p}_schema_keys"] = list((schema or {}).get("properties", {}).keys())
        out["attempts"] = attempts
    out["admin_hits"] = HITS["admin"] - before["admin"]
    return out


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


async def probe_http_auth():
    """(c) server auth over real HTTP: a client without the token must get nothing."""
    import uvicorn

    settings = MCPSettings(api_prefix="/api/v1", allowed_tool_categories=["research"])
    mcp = create_mcp_server(settings, make_app(), auth=("founder", "s3cret-test-only"))
    port = free_port()
    config = uvicorn.Config(mcp.http_app(), host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    res = {}
    try:
        async with Client(f"http://127.0.0.1:{port}/mcp") as c:
            res["no_token"] = f"listed {len(await c.list_tools())} tools"
    except Exception as e:
        res["no_token"] = f"refused: {type(e).__name__}: {str(e)[:120]}"
    server.should_exit = True
    th.join(timeout=5)
    return res


async def main_async():
    results = {}
    app_default = make_app()
    results["a_default"] = await probe(create_mcp_server(MCPSettings(api_prefix="/api/v1"), app_default), "default settings")
    results["b_allowed_research_only"] = await probe(
        create_mcp_server(MCPSettings(api_prefix="/api/v1", allowed_tool_categories=["research"]), make_app()),
        "allowed_tool_categories=[research]")
    results["b2_allowed_research_with_discovery"] = await probe(
        create_mcp_server(MCPSettings(api_prefix="/api/v1", allowed_tool_categories=["research"], enable_tool_discovery=True), make_app()),
        "allowed=[research] + tool discovery")
    results["b3_default_categories_research_only"] = await probe(
        create_mcp_server(MCPSettings(api_prefix="/api/v1", default_tool_categories=["research"]), make_app()),
        "default_tool_categories=[research] (not allowed_)")
    results["c_http_auth"] = await probe_http_auth()
    results["verdict"] = {
        "a_admin_reachable_by_default": results["a_default"]["admin_hits"] > 0,
        "b_admin_unreachable_with_allow_list": results["b_allowed_research_only"]["admin_hits"] == 0
        and results["b2_allowed_research_with_discovery"]["admin_hits"] == 0,
        "c_no_token_refused": results["c_http_auth"]["no_token"].startswith("refused"),
    }
    return results


def main():
    res = asyncio.run(main_async())
    with open(sys.argv[1], "w") as f:
        json.dump(res, f, indent=2)
    for k, v in res.items():
        print(k, json.dumps(v)[:900])


if __name__ == "__main__":
    main()
