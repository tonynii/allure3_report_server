import json
from contextlib import asynccontextmanager, AsyncExitStack

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.database import engine
from app.mcp.server import mcp
from app.routers import projects, reports, dashboard, compare


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mcp_app = mcp.streamable_http_app()
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())
        yield
    await engine.dispose()


app = FastAPI(
    title="Allure3 Report Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def mcp_middleware(request: Request, call_next):
    if not request.url.path.startswith("/mcp"):
        return await call_next(request)

    if request.method == "GET":
        return Response(
            content=json.dumps({
                "server": "Allure3 Report Server",
                "protocol": "MCP streamable-http",
                "status": "ok",
                "endpoint": "/mcp",
                "tools": 11,
                "resources": 3,
                "prompts": 2,
            }),
            media_type="application/json",
        )

    mcp_app = request.app.state.mcp_app
    start = None
    body_chunks: list[bytes] = []

    async def send(message):
        nonlocal start
        if message["type"] == "http.response.start":
            start = message
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    await mcp_app(request.scope, request.receive, send)

    if start is None:
        return await call_next(request)

    headers = dict(start.get("headers", []))
    ct = headers.get(b"content-type", b"application/json").decode()
    return Response(
        content=b"".join(body_chunks),
        status_code=start["status"],
        media_type=ct,
    )


app.include_router(projects.router)
app.include_router(reports.router)
app.include_router(dashboard.router)
app.include_router(compare.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
