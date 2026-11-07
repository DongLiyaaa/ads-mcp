from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import hmac
import json
from fastapi import FastAPI, Request, Depends, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import delete, text
from sqlalchemy.exc import SQLAlchemyError
from .settings import Settings
from .database import Database
from .service import Service, audit
from .models import Session
from .security import Problem, csrf_token, token_hash
from .contracts import public_catalog
from .mcp_server import build_mcp, BearerGuard
from .http_limits import RequestSizeLimit


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=1024)


class SetupInput(Input):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=1024)
    setup_token: str = Field(default="", max_length=256)


class ResetInput(Input):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=1024)
    setup_token: str = Field(default="", max_length=256)


class PasswordInput(Input):
    password: str = Field(min_length=1, max_length=1024)


class AccountInput(Input):
    label: str = Field(min_length=1, max_length=160)
    region: Literal["NA", "EU", "FE"] = "NA"
    marketplace: str = Field(pattern="^[A-Z]{2}$")
    profile_id: str = Field(pattern="^[0-9]{1,30}$")
    client_id: str = Field(min_length=10, max_length=256)
    client_secret: str = Field(min_length=10, max_length=2048)
    refresh_token: str = Field(min_length=10, max_length=8192)


class AccountLabelInput(Input):
    label: str = Field(min_length=1, max_length=160)


class AccountRelayInput(Input):
    relay_id: str | None = Field(default=None, max_length=36)


class ServerInput(Input):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    ssh_port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, min_length=1, max_length=64)
    auth_type: Literal["key", "password"] | None = None
    password: str | None = Field(default=None, max_length=1024)
    private_key: str | None = Field(default=None, max_length=16384)
    passphrase: str | None = Field(default=None, max_length=1024)
    relay_port: int | None = Field(default=None, ge=1024, le=65535)
    reset_host_key: bool = False


class TokenInput(Input):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(min_length=1, max_length=5)
    account_ids: list[str] = Field(min_length=1, max_length=100)
    # null = never expires (until revoked or deleted).
    expires_in_days: int | None = Field(default=30, ge=1, le=365)


class OperationInput(Input):
    account_id: str = Field(min_length=1, max_length=36)
    operation: str = Field(min_length=1, max_length=100)
    arguments: dict = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=8, max_length=120)


class SyncInput(Input):
    days: Literal[1, 7]


class ApprovalInput(Input):
    confirm_text: str
    payload_hash: str = Field(min_length=64, max_length=64)


def create_app(settings=None, service=None):
    settings = settings or Settings.load()
    service = service or Service(Database(settings), settings)
    mcp = build_mcp(service)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="Amazon Ads Control Plane",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.service = service
    app.add_middleware(RequestSizeLimit)

    @app.exception_handler(Problem)
    async def problem(request, exc):
        return JSONResponse({"error": exc.message}, status_code=exc.status)

    @app.exception_handler(SQLAlchemyError)
    async def database_unavailable(request, exc):
        return JSONResponse(
            {"error": "数据库尚未就绪或暂时不可用，请稍后重试"}, status_code=503
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse(
            {
                "error": "；".join(
                    ".".join(map(str, e["loc"])) + ": " + e["msg"] for e in exc.errors()
                )
            },
            status_code=422,
        )

    @app.middleware("http")
    async def protection(request, call_next):
        try:
            content_length = int(request.headers.get("content-length", "0") or 0)
        except ValueError:
            return JSONResponse({"error": "Invalid Content-Length"}, status_code=400)
        if content_length > 1024 * 1024:
            return JSONResponse({"error": "请求体过大"}, status_code=413)
        if request.url.path.startswith("/api/") and request.method not in {
            "GET",
            "HEAD",
            "OPTIONS",
        }:
            if request.headers.get("origin") != settings.public_origin:
                return JSONResponse({"error": "Origin 校验失败"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith(("/api", "/mcp")) else "no-cache"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    def session_actor(request: Request):
        raw = request.cookies.get("ads_session")
        actor, _ = service.authenticate_session(raw)
        if request.method not in {"GET", "HEAD"}:
            supplied = request.headers.get("x-csrf-token", "")
            if not hmac.compare_digest(supplied, csrf_token(raw, settings.session_key)):
                raise Problem(403, "CSRF 校验失败")
        return actor

    @app.get("/healthz")
    def health():
        try:
            with service.db.engine.connect() as conn:
                version = conn.scalar(text("SELECT version FROM ads_schema_version"))
                if version != 1:
                    raise RuntimeError("Schema is not ready")
            return {"status": "ok", "database": "postgresql", "schema_version": version}
        except Exception:
            return JSONResponse(
                {"status": "unavailable", "database": "unreachable"}, status_code=503
            )

    def signed_in(username, raw):
        response = JSONResponse(
            {
                "username": username,
                "csrf_token": csrf_token(raw, settings.session_key),
            }
        )
        response.set_cookie(
            "ads_session",
            raw,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="strict",
            max_age=43200,
        )
        return response

    @app.get("/api/setup")
    def setup_state():
        return service.setup_state()

    @app.post("/api/setup")
    def setup(data: SetupInput):
        raw = service.setup_admin(data.username, data.password, data.setup_token)
        return signed_in(data.username, raw)

    @app.post("/api/login")
    def login(data: Login, request: Request):
        raw = service.login(
            data.username,
            data.password,
            request.client.host if request.client else "unknown",
        )
        return signed_in(data.username, raw)

    @app.post("/api/password/reset")
    def reset_password(data: ResetInput, request: Request):
        return service.reset_password(
            data.username,
            data.password,
            data.setup_token,
            request.client.host if request.client else "unknown",
        )

    @app.post("/api/password")
    def change_password(
        data: PasswordInput, request: Request, actor=Depends(session_actor)
    ):
        return service.change_password(
            actor, request.cookies["ads_session"], data.password
        )

    @app.get("/api/session")
    def session(request: Request):
        raw = request.cookies.get("ads_session")
        _, username = service.authenticate_session(raw)
        return {
            "username": username,
            "csrf_token": csrf_token(raw, settings.session_key),
        }

    @app.post("/api/logout")
    def logout(request: Request, actor=Depends(session_actor)):
        with service.db.sessions.begin() as s:
            s.execute(
                delete(Session).where(
                    Session.token_hash == token_hash(request.cookies["ads_session"])
                )
            )
            audit(s, actor.user_id, "session.logout")
        response = JSONResponse({"logged_out": True})
        response.delete_cookie("ads_session")
        return response

    @app.get("/api/overview")
    def overview(actor=Depends(session_actor)):
        return service.overview(actor)

    @app.get("/api/capabilities")
    def capabilities(actor=Depends(session_actor)):
        return public_catalog()

    @app.get("/api/accounts")
    def accounts(actor=Depends(session_actor)):
        return service.accounts(actor)

    @app.post("/api/accounts")
    def add_account(data: AccountInput, actor=Depends(session_actor)):
        return service.add_account(actor, data.model_dump())

    @app.patch("/api/accounts/{account_id}")
    def rename_account(
        account_id: str, data: AccountLabelInput, actor=Depends(session_actor)
    ):
        return service.rename_account(actor, account_id, data.label)

    @app.post("/api/accounts/{account_id}/verify")
    def verify(account_id: str, actor=Depends(session_actor)):
        return service.verify_account(actor, account_id)

    @app.get("/api/accounts/{account_id}/amc")
    def amc(account_id: str, refresh: bool = False, actor=Depends(session_actor)):
        return service.amc_overview(actor, account_id, refresh)

    @app.put("/api/accounts/{account_id}/relay")
    def account_relay(account_id: str, data: AccountRelayInput, actor=Depends(session_actor)):
        return service.set_account_relay(actor, account_id, data.relay_id)

    @app.get("/api/servers")
    def servers(actor=Depends(session_actor)):
        return service.servers(actor)

    @app.post("/api/servers")
    def add_server(data: ServerInput, actor=Depends(session_actor)):
        return service.add_server(actor, data.model_dump())

    @app.patch("/api/servers/{server_id}")
    def update_server(server_id: str, data: ServerInput, actor=Depends(session_actor)):
        return service.update_server(actor, server_id, data.model_dump(exclude_unset=True))

    @app.delete("/api/servers/{server_id}")
    def delete_server(server_id: str, actor=Depends(session_actor)):
        return service.delete_server(actor, server_id)

    @app.post("/api/servers/{server_id}/test")
    def test_server(server_id: str, actor=Depends(session_actor)):
        return service.test_server(actor, server_id)

    @app.post("/api/servers/{server_id}/install")
    def install_server(server_id: str, actor=Depends(session_actor)):
        return service.install_server(actor, server_id)

    @app.post("/api/servers/{server_id}/check")
    def check_server(server_id: str, actor=Depends(session_actor)):
        return service.check_server(actor, server_id)

    @app.post("/api/servers/{server_id}/uninstall")
    def uninstall_server(server_id: str, actor=Depends(session_actor)):
        return service.uninstall_server(actor, server_id)

    @app.get("/api/tokens")
    def tokens(actor=Depends(session_actor)):
        return service.tokens(actor)

    @app.post("/api/tokens")
    def new_token(data: TokenInput, actor=Depends(session_actor)):
        return service.create_token(
            actor, data.name, data.scopes, data.account_ids, data.expires_in_days
        )

    @app.post("/api/tokens/{token_id}/revoke")
    def revoke(token_id: str, actor=Depends(session_actor)):
        return service.revoke_token(actor, token_id)

    @app.post("/api/tokens/{token_id}/reveal")
    def reveal(token_id: str, actor=Depends(session_actor)):
        return service.reveal_token(actor, token_id)

    @app.post("/api/tokens/{token_id}/rotate")
    def rotate(token_id: str, actor=Depends(session_actor)):
        return service.rotate_token(actor, token_id)

    @app.delete("/api/tokens/{token_id}")
    def delete_token(token_id: str, actor=Depends(session_actor)):
        return service.delete_token(actor, token_id)

    @app.post("/api/queries")
    def query(data: OperationInput, actor=Depends(session_actor)):
        return service.create_task(
            actor,
            data.account_id,
            data.operation,
            data.arguments,
            data.idempotency_key,
            "read",
        )

    @app.post("/api/accounts/{account_id}/sync")
    def sync(account_id: str, data: SyncInput, actor=Depends(session_actor)):
        return service.sync_reports(actor, account_id, data.days)

    @app.post("/api/reports")
    def report(data: OperationInput, actor=Depends(session_actor)):
        return service.create_task(
            actor,
            data.account_id,
            data.operation,
            data.arguments,
            data.idempotency_key,
            "report",
        )

    @app.post("/api/plans")
    def plan(data: OperationInput, actor=Depends(session_actor)):
        return service.create_task(
            actor,
            data.account_id,
            data.operation,
            data.arguments,
            data.idempotency_key,
            "write",
        )

    @app.get("/api/tasks")
    def tasks(
        status: str | None = None,
        kind: Literal["read", "report", "write"] | None = None,
        account_id: str | None = Query(None, max_length=36),
        operation: str | None = Query(None, max_length=100),
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        actor=Depends(session_actor),
    ):
        return service.tasks(actor, status, offset, limit, kind, account_id, operation)

    @app.get("/api/tasks/{task_id}")
    def task(task_id: str, actor=Depends(session_actor)):
        return service.task(actor, task_id)

    @app.get("/api/tasks/{task_id}/rows")
    def rows(
        task_id: str,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        actor=Depends(session_actor),
    ):
        return service.result_rows(actor, task_id, offset, limit)

    @app.get("/api/tasks/{task_id}/summary")
    def summary(
        task_id: str,
        metrics: str = Query(min_length=1, max_length=2000),
        group_by: str | None = Query(None, max_length=64),
        actor=Depends(session_actor),
    ):
        return service.result_summary(actor, task_id, group_by, metrics.split(","))

    @app.get("/api/tasks/{task_id}/export")
    def export(task_id: str, actor=Depends(session_actor)):
        detail = service.task(actor, task_id)
        if detail["status"] != "SUCCEEDED":
            raise Problem(409, "任务尚未成功完成")

        def content():
            yield "["
            offset = 0
            first = True
            while True:
                page = service.result_rows(actor, task_id, offset, 500)
                for row in page["rows"]:
                    yield ("" if first else ",") + json.dumps(row, ensure_ascii=False)
                    first = False
                offset += len(page["rows"])
                if offset >= page["total"] or not page["rows"]:
                    break
            yield "]"

        return StreamingResponse(
            content(),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="ads-{task_id}.json"'
            },
        )

    @app.post("/api/tasks/{task_id}/approve")
    def approve(task_id: str, data: ApprovalInput, actor=Depends(session_actor)):
        return service.approve(actor, task_id, data.confirm_text, data.payload_hash)

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel(task_id: str, actor=Depends(session_actor)):
        return service.cancel(actor, task_id)

    @app.get("/api/logs")
    def logs(
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        actor=Depends(session_actor),
    ):
        return service.logs(actor, offset, limit)

    app.mount("/mcp", BearerGuard(mcp_app, service))
    dist = Path(settings.frontend_dir)
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        if path.startswith(("api/", "mcp/")) or not (dist / "index.html").exists():
            return JSONResponse({"error": "页面尚未构建或路径不存在"}, status_code=404)
        return FileResponse(dist / "index.html")

    return app
