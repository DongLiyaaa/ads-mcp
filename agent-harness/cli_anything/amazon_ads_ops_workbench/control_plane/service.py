import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import hashlib
import hmac
import re
import secrets
import threading
import time
from sqlalchemy import delete, select, func, text
from sqlalchemy.exc import IntegrityError
from ..core.client import AmazonAdsClient
from ..core.env import AdsEnvironment
from ..core import relay as relay_transport
from ..core.relay import RelayEndpoint
from . import servers as ssh
from .models import (
    User,
    Session,
    Account,
    Token,
    Task,
    Audit,
    RelayServer,
    ReportRow,
    LoginAttempt,
    now,
)
from .security import (
    Actor,
    Problem,
    SCOPES,
    token_hash,
    password_matches,
    password_hash,
    encrypt_config,
    decrypt_config,
    bound_hash,
    redact,
)
from .contracts import invoke_contract, validate_arguments, public_catalog
from ..core.amc import (
    public_templates as public_amc_templates,
    summarize_data_sources as summarize_amc_data_sources,
    summarize_instance as summarize_amc_instance,
)

# Permanent MCP tokens use a far-future expiry instead of NULL, so every
# expiry check (and older releases on rollback) keeps working unchanged.
NEVER_EXPIRES = datetime(9999, 1, 1, tzinfo=timezone.utc)  # margin for any session time zone


USERNAME = re.compile(r"[A-Za-z0-9._@-]{3,64}")
SSH_USER = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]{0,63}")
HOSTNAME = re.compile(r"[A-Za-z0-9.:\[\]-]{1,255}")
# Served by the relay when egress works; any HTTP answer proves the route.
EGRESS_PROBE = "https://advertising-api.amazon.com/"


def new_token_value():
    return "amcp_" + secrets.token_urlsafe(40)


FIELD = re.compile(r"[A-Za-z0-9_]{1,64}")


def audit(s, owner, action, status="OK", account=None, task=None, detail=None):
    s.add(
        Audit(
            owner_id=owner,
            action=action,
            status=status,
            account_id=account,
            task_id=task,
            detail=redact(detail or {}),
        )
    )


def account_json(a):
    return {
        "id": a.id,
        "label": a.label,
        "region": a.region,
        "marketplace": a.marketplace,
        "profile_id": a.profile_id,
        "verified_at": a.verified_at.isoformat() if a.verified_at else None,
        "currency": a.profile.get("currencyCode"),
        "timezone": a.profile.get("timezone"),
        "created_at": a.created_at.isoformat(),
        "relay_id": a.relay_id,
    }


def host_fingerprint(host_key):
    if not host_key:
        return None
    digest = hashlib.sha256(base64.b64decode(host_key.split()[-1])).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def server_json(r, accounts=()):
    return {
        "id": r.id,
        "name": r.name,
        "host": r.host,
        "ssh_port": r.ssh_port,
        "username": r.username,
        "auth_type": r.auth_type,
        "relay_port": r.relay_port,
        "status": r.status,
        "checks": (r.status_detail or {}).get("checks", []),
        "message": (r.status_detail or {}).get("message"),
        "host_fingerprint": host_fingerprint(r.host_key),
        "installed": bool(r.relay_secret_ciphertext),
        "relay_version": r.relay_version,
        "checked_at": r.checked_at.isoformat() if r.checked_at else None,
        "installed_at": r.installed_at.isoformat() if r.installed_at else None,
        "created_at": r.created_at.isoformat(),
        "accounts": [{"id": a.id, "label": a.label} for a in accounts],
    }


def task_json(t, detail=False):
    value = {
        "id": t.id,
        "account_id": t.account_id,
        "kind": t.kind,
        "operation": t.operation,
        "status": t.status,
        "remote_status": t.remote_status,
        "remote_id": t.remote_id,
        "row_count": t.row_count,
        "error": t.error,
        "payload_hash": t.payload_hash,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
        "approved_at": t.approved_at.isoformat() if t.approved_at else None,
    }
    if t.kind == "report":
        # Report arguments are just the date range; lists show it without detail.
        value["arguments"] = t.arguments
        if isinstance(t.result, dict) and isinstance(t.result.get("privacy"), dict):
            value["privacy"] = t.result["privacy"]
    if detail:
        result = t.result
        value.update(
            arguments=t.arguments,
            payload=redact(t.payload),
            result=redact(result[:50] if isinstance(result, list) else result),
            result_truncated=isinstance(result, list) and len(result) > 50,
        )
    return value


def relay_key(env):
    relay = getattr(env, "relay", None)
    return f"|relay:{relay.id}:{relay.fingerprint}" if relay else ""


class Gateway:
    def __init__(self):
        self.cache = {}
        self.amc_cache = {}
        self.lock = threading.Lock()

    def amc(self, env, client, token, instance_id=None):
        """(entity ID, AMC instance) for an account; both rarely change."""
        key = token_hash(
            "|".join([env.client_id, env.refresh_token, env.region, env.marketplace, env.profile_id, instance_id or "", relay_key(env)])
        )
        with self.lock:
            cached = self.amc_cache.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        value = client.amc_context(token, instance_id)
        with self.lock:
            self.amc_cache[key] = (time.monotonic() + 1800, value)
        return value

    def context(self, env):
        key = token_hash(
            env.client_id + env.client_secret + env.refresh_token + env.region + relay_key(env)
        )
        with self.lock:
            cached = self.cache.get(key)
        client = AmazonAdsClient(env)
        if cached and cached[0] > time.monotonic():
            token, profiles = cached[1:]
        else:
            token = client.exchange_refresh_token()
            profiles = client.list_profiles(token)
            with self.lock:
                self.cache[key] = (time.monotonic() + 300, token, profiles)
                if len(self.cache) > 200:
                    self.cache = {
                        k: v for k, v in self.cache.items() if v[0] > time.monotonic()
                    }
        selected = next(
            (p for p in profiles if str(p.get("profileId")) == env.profile_id), None
        )
        if not selected or selected.get("countryCode") != env.marketplace:
            raise Problem(400, "Profile 不属于指定站点或当前授权账户")
        return client, token, profiles, selected


class Service:
    def __init__(self, db, settings, gateway=None):
        self.db, self.settings = db, settings
        self.gateway = gateway or Gateway()
        self.dummy_hash = password_hash(secrets.token_urlsafe(24))
        self.amc_cache = {}

    def attempt(self, s, key, message):
        # The lock also covers the absent-row case on first attempt.
        s.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(key[:15], 16)}
        )
        attempt = s.get(LoginAttempt, key)
        if attempt is None:
            attempt = LoginAttempt(key=key, count=0, window_start=now())
            s.add(attempt)
        if now() - attempt.window_start > timedelta(minutes=15):
            attempt.count, attempt.window_start = 0, now()
        if attempt.count >= 10:
            raise Problem(429, message)
        return attempt

    def login(self, username, password, ip):
        with self.db.sessions.begin() as s:
            attempt = self.attempt(
                s, token_hash(ip), "登录尝试过多，请 15 分钟后重试"
            )
            user = s.scalar(select(User).where(User.username == username))
            valid = password_matches(
                password, user.password_hash if user else self.dummy_hash
            )
            if not valid or not user:
                attempt.count += 1
                failure = True
            else:
                failure = False
                attempt.count = 0
                raw = self.open_session(s, user)
                audit(s, user.id, "session.login")
        if failure:
            raise Problem(401, "用户名或密码不正确")
        return raw

    def open_session(self, s, user):
        raw = secrets.token_urlsafe(40)
        s.add(
            Session(
                token_hash=token_hash(raw),
                user_id=user.id,
                expires_at=now() + timedelta(hours=12),
            )
        )
        return raw

    def setup_state(self):
        with self.db.sessions() as s:
            empty = not s.scalar(select(func.count()).select_from(User))
        return {
            "needs_setup": empty,
            "token_required": bool(self.settings.setup_token),
            "available": bool(self.settings.setup_token) or self.settings.loopback,
        }

    def check_setup_token(self, setup_token):
        # Setup and password reset need no login. Without a setup token anyone
        # who reaches the page could take the admin account, so only loopback
        # deployments may skip it.
        expected = self.settings.setup_token
        if expected:
            if not hmac.compare_digest(setup_token.encode(), expected.encode()):
                raise Problem(403, "初始化口令不正确")
        elif not self.settings.loopback:
            raise Problem(403, "远程部署需先在 .env 设置 ADS_SETUP_TOKEN")

    @staticmethod
    def check_password(username, password):
        if len(password) < 12:
            raise Problem(422, "密码至少需要 12 位")
        if password.lower() == username.lower():
            raise Problem(422, "密码不能与用户名相同")

    def setup_admin(self, username, password, setup_token=""):
        self.check_setup_token(setup_token)
        if not USERNAME.fullmatch(username):
            raise Problem(422, "用户名需为 3–64 位字母、数字或 . _ @ -")
        self.check_password(username, password)
        with self.db.sessions.begin() as s:
            # Same lock as migrate(), so env bootstrap and concurrent setups serialize.
            s.execute(text("SELECT pg_advisory_xact_lock(6666, 1)"))
            if s.scalar(select(func.count()).select_from(User)):
                raise Problem(409, "控制台已完成初始化，请直接登录")
            user = User(username=username, password_hash=password_hash(password))
            s.add(user)
            s.flush()
            raw = self.open_session(s, user)
            audit(s, user.id, "setup.admin_created")
        return raw

    def reset_password(self, username, password, setup_token, ip):
        self.check_setup_token(setup_token)
        self.check_password(username, password)
        with self.db.sessions.begin() as s:
            attempt = self.attempt(
                s, token_hash("reset:" + ip), "重置尝试过多，请 15 分钟后重试"
            )
            user = s.scalar(select(User).where(User.username == username))
            if user:
                user.password_hash = password_hash(password)
                # Sign out everywhere: an old session must not survive a reset.
                s.execute(delete(Session).where(Session.user_id == user.id))
                audit(s, user.id, "password.reset")
                attempt.count = 0
            else:
                attempt.count += 1
        if not user:
            raise Problem(404, "用户名不存在")
        return {"reset": True}

    def change_password(self, actor, raw_session, password):
        with self.db.sessions.begin() as s:
            user = s.get(User, actor.user_id)
            self.check_password(user.username, password)
            user.password_hash = password_hash(password)
            # Keep the current session; sign out every other one.
            s.execute(
                delete(Session).where(
                    Session.user_id == user.id,
                    Session.token_hash != token_hash(raw_session),
                )
            )
            audit(s, user.id, "password.changed")
        return {"changed": True}

    def authenticate_session(self, raw):
        if not raw:
            raise Problem(401, "请先登录")
        with self.db.sessions() as s:
            row = s.get(Session, token_hash(raw))
            if not row or row.expires_at <= now():
                raise Problem(401, "登录已过期")
            user = s.get(User, row.user_id)
            return Actor(user.id, "session"), user.username

    def authenticate_token(self, raw):
        if not raw or not raw.startswith("amcp_"):
            raise Problem(401, "缺少 MCP Bearer Token")
        with self.db.sessions.begin() as s:
            t = s.scalar(select(Token).where(Token.token_hash == token_hash(raw)))
            if not t or t.revoked_at or t.expires_at <= now():
                raise Problem(401, "MCP Token 无效、过期或已撤销")
            t.last_used_at = now()
            return Actor(
                t.owner_id, "token", frozenset(t.scopes), tuple(t.account_ids), t.id
            )

    def account(self, s, actor, account_id):
        account = s.scalar(
            select(Account).where(
                Account.id == account_id, Account.owner_id == actor.user_id
            )
        )
        if not account or not actor.account_allowed(account_id):
            raise Problem(404, "账户不存在或不可访问")
        return account

    def relay_endpoint(self, account):
        if not account.relay_id:
            return None
        with self.db.sessions() as s:
            r = s.get(RelayServer, account.relay_id)
        if not r or r.owner_id != account.owner_id or not r.relay_secret_ciphertext:
            # Never fall back to direct calls: the account asked for this egress.
            raise Problem(409, f"店铺「{account.label}」绑定的转发服务器不可用（未安装或已删除），请重新安装或切回本地直连")
        return self.relay_of(r)

    def relay_of(self, r):
        secret = decrypt_config(r.relay_secret_ciphertext, self.settings.encryption_key)["secret"]
        return RelayEndpoint(r.id, r.name, r.host.strip("[]"), r.relay_port, r.relay_fingerprint, secret)

    def environment(self, account):
        relay = self.relay_endpoint(account)
        config = decrypt_config(
            account.credentials_ciphertext, self.settings.encryption_key
        )
        return AdsEnvironment(
            client_id=config["client_id"],
            client_secret=config["client_secret"],
            refresh_token=config["refresh_token"],
            profile_id=account.profile_id,
            region=account.region,
            marketplace=account.marketplace,
            relay=relay,
        )

    def accounts(self, actor):
        with self.db.sessions() as s:
            rows = s.scalars(
                select(Account)
                .where(Account.owner_id == actor.user_id)
                .order_by(Account.created_at.desc())
            ).all()
            return [account_json(a) for a in rows if actor.account_allowed(a.id)]

    def add_account(self, actor, data):
        if actor.kind != "session":
            raise Problem(403, "仅管理页面可配置账户")
        credentials = {
            key: data[key] for key in ("client_id", "client_secret", "refresh_token")
        }
        a = Account(
            owner_id=actor.user_id,
            label=data["label"],
            region=data["region"],
            marketplace=data["marketplace"],
            profile_id=data["profile_id"],
            credentials_ciphertext=encrypt_config(
                credentials, self.settings.encryption_key
            ),
        )
        try:
            with self.db.sessions.begin() as s:
                s.add(a)
                s.flush()
                audit(s, actor.user_id, "account.created", account=a.id)
        except IntegrityError:
            raise Problem(409, "该 Profile 已存在") from None
        return account_json(a)

    def rename_account(self, actor, account_id, label):
        if actor.kind != "session":
            raise Problem(403, "仅管理页面可修改账户")
        label = label.strip()
        if not label:
            raise Problem(422, "店铺名称不能为空")
        with self.db.sessions.begin() as s:
            a = self.account(s, actor, account_id)
            before, a.label = a.label, label
            audit(s, actor.user_id, "account.renamed", account=a.id, detail={"from": before, "to": label})
        return account_json(a)

    # ---- relay servers (SSH-managed egress) ----

    def require_session(self, actor):
        if actor.kind != "session":
            raise Problem(403, "仅管理页面可管理转发服务器")

    def owned_server(self, s, actor, server_id, lock=False):
        query = select(RelayServer).where(RelayServer.id == server_id, RelayServer.owner_id == actor.user_id)
        r = s.scalar(query.with_for_update() if lock else query)
        if not r:
            raise Problem(404, "转发服务器不存在")
        return r

    def bound_accounts(self, s, r):
        return s.scalars(
            select(Account).where(Account.owner_id == r.owner_id, Account.relay_id == r.id).order_by(Account.label)
        ).all()

    def servers(self, actor):
        self.require_session(actor)
        with self.db.sessions() as s:
            rows = s.scalars(
                select(RelayServer).where(RelayServer.owner_id == actor.user_id).order_by(RelayServer.created_at)
            ).all()
            return [server_json(r, self.bound_accounts(s, r)) for r in rows]

    def server_fields(self, data, creating):
        fields = {}
        for key in ("name", "host", "username"):
            if key in data and data[key] is not None:
                fields[key] = data[key].strip()
        if "name" in fields and not 1 <= len(fields["name"]) <= 120:
            raise Problem(422, "服务器名称需为 1–120 个字符")
        if "host" in fields and not HOSTNAME.fullmatch(fields["host"]):
            raise Problem(422, "服务器地址只能是域名或 IP")
        if "username" in fields and not SSH_USER.fullmatch(fields["username"]):
            raise Problem(422, "SSH 用户名格式不正确")
        for key, low in (("ssh_port", 1), ("relay_port", 1024)):
            if data.get(key) is not None:
                if not low <= int(data[key]) <= 65535:
                    raise Problem(422, "SSH 端口需为 1–65535" if key == "ssh_port" else "转发端口需为 1024–65535")
                fields[key] = int(data[key])
        if creating and not all(fields.get(k) for k in ("name", "host", "username")):
            raise Problem(422, "请填写服务器名称、地址和 SSH 用户名")
        auth = data.get("auth_type")
        if auth is not None and auth not in {"key", "password"}:
            raise Problem(422, "认证方式只能是私钥或密码")
        secret = data.get("password") if auth == "password" else data.get("private_key")
        if creating or auth:
            if not auth or not secret:
                raise Problem(422, "请填写 SSH 密码或私钥")
            if auth == "key":
                ssh.load_private_key(secret, data.get("passphrase"))  # fail early on bad keys
            credentials = (
                {"password": secret}
                if auth == "password"
                else {"private_key": secret.strip() + "\n", "passphrase": data.get("passphrase") or ""}
            )
            fields["auth_type"] = auth
            fields["credentials_ciphertext"] = encrypt_config(credentials, self.settings.encryption_key)
        return fields

    def add_server(self, actor, data):
        self.require_session(actor)
        try:
            fields = self.server_fields(data, creating=True)
        except ssh.SSHFailure as exc:
            raise Problem(422, str(exc)) from None
        r = RelayServer(owner_id=actor.user_id, status="NEW", status_detail={}, **fields)
        try:
            with self.db.sessions.begin() as s:
                s.add(r)
                s.flush()
                audit(s, actor.user_id, "server.created", detail={"server_id": r.id, "host": r.host})
        except IntegrityError:
            raise Problem(409, "已有同名转发服务器") from None
        return server_json(r)

    def update_server(self, actor, server_id, data):
        self.require_session(actor)
        try:
            fields = self.server_fields(data, creating=False)
        except ssh.SSHFailure as exc:
            raise Problem(422, str(exc)) from None
        try:
            with self.db.sessions.begin() as s:
                r = self.owned_server(s, actor, server_id, lock=True)
                if r.relay_secret_ciphertext and fields.get("relay_port", r.relay_port) != r.relay_port:
                    raise Problem(409, "转发服务已安装，修改端口需要先卸载再重新安装")
                if fields.get("host", r.host) != r.host or fields.get("ssh_port", r.ssh_port) != r.ssh_port or data.get("reset_host_key"):
                    r.host_key = None
                for key, value in fields.items():
                    setattr(r, key, value)
                audit(s, actor.user_id, "server.updated", detail={"server_id": r.id, "fields": sorted(k for k in fields if k != "credentials_ciphertext")})
                s.flush()
                return server_json(r, self.bound_accounts(s, r))
        except IntegrityError:
            raise Problem(409, "已有同名转发服务器") from None

    def delete_server(self, actor, server_id):
        self.require_session(actor)
        with self.db.sessions.begin() as s:
            r = self.owned_server(s, actor, server_id, lock=True)
            if self.bound_accounts(s, r):
                raise Problem(409, "仍有店铺使用该服务器转发，请先把它们切回本地直连")
            s.delete(r)
            audit(s, actor.user_id, "server.deleted", detail={"server_id": server_id, "host": r.host})
        return {"deleted": True}

    def remote(self, r):
        credentials = decrypt_config(r.credentials_ciphertext, self.settings.encryption_key)
        return ssh.Remote(r.host.strip("[]"), r.ssh_port, r.username, r.auth_type, credentials, r.host_key), credentials

    @contextmanager
    def server_lock(self, server_id):
        # One SSH operation per server at a time, across web and worker processes.
        with self.db.engine.connect() as conn:
            key = int(token_hash(server_id)[:15], 16)
            if not conn.scalar(text("SELECT pg_try_advisory_lock(6668, :k)"), {"k": key & 0x7FFFFFFF}):
                raise Problem(409, "该服务器正在执行其他操作，请稍后再试")
            try:
                yield
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(6668, :k)"), {"k": key & 0x7FFFFFFF})
                conn.commit()

    def record_server(self, actor, server_id, action, status, checks=None, message=None, **values):
        with self.db.sessions.begin() as s:
            r = self.owned_server(s, actor, server_id, lock=True)
            r.status, r.checked_at = status, now()
            r.status_detail = {"checks": checks if checks is not None else (r.status_detail or {}).get("checks", []), "message": message}
            for key, value in values.items():
                setattr(r, key, value)
            audit(s, actor.user_id, action, "OK" if status in {"READY", "INSTALLED"} else status, detail={"server_id": r.id, "status": status, "message": message})
            s.flush()
            return server_json(r, self.bound_accounts(s, r))

    def inspect_server(self, r):
        """SSH in, gather facts and checks; returns (remote host key, facts, checks)."""
        remote, credentials = self.remote(r)
        with remote:
            code, out, err = remote.run(ssh.probe_script(r.relay_port, self.relay_root))
            if code:
                raise ssh.SSHFailure(f"环境检测失败：{err.strip()[:300]}")
            facts = ssh.parse_facts(out)
            return remote.host_key, facts, ssh.evaluate(facts, r.auth_type, remote.fingerprint)

    # Test hooks: path prefix for every installed file, and the relay bind address.
    relay_root = ""
    relay_listen = "0.0.0.0"

    def relay_health(self, r):
        try:
            info = relay_transport.health(self.relay_of(r))
            return {"key": "tls", "label": "加密通道", "ok": True, "detail": f"本机 → {r.host}:{r.relay_port} 连通，证书指纹匹配（ads-relay {info.get('version')} / Python {info.get('python')}）", "required": False}
        except Exception as exc:
            return {"key": "tls", "label": "加密通道", "ok": False, "detail": f"{redact(str(exc))[:300]}；请检查安全组是否放行 TCP {r.relay_port}", "required": False}

    def test_server(self, actor, server_id):
        self.require_session(actor)
        with self.db.sessions() as s:
            r = self.owned_server(s, actor, server_id)
        with self.server_lock(server_id):
            try:
                host_key, facts, checks = self.inspect_server(r)
            except ssh.SSHFailure as exc:
                return self.record_server(actor, server_id, "server.tested", "ERROR", [], str(exc))
            if r.relay_secret_ciphertext:
                checks.append(self.relay_health(r))
            blocked = [c["label"] for c in checks if c["required"] and not c["ok"]]
            if r.relay_secret_ciphertext:
                status = "INSTALLED" if checks[-1]["ok"] else "UNREACHABLE"
            else:
                status = "BLOCKED" if blocked else "READY"
            message = "缺少条件：" + "、".join(blocked) if blocked else None
            result = self.record_server(actor, server_id, "server.tested", status, checks, message, host_key=r.host_key or host_key)
        result["plan"] = ssh.install_plan(facts, r.relay_port, self.relay_root)
        return result

    def install_server(self, actor, server_id):
        self.require_session(actor)
        with self.db.sessions() as s:
            r = self.owned_server(s, actor, server_id)
        with self.server_lock(server_id):
            secret = secrets.token_urlsafe(32)
            try:
                remote, credentials = self.remote(r)
                with remote:
                    code, out, err = remote.run(ssh.probe_script(r.relay_port, self.relay_root))
                    facts = ssh.parse_facts(out)
                    checks = ssh.evaluate(facts, r.auth_type, remote.fingerprint)
                    blocked = [c["label"] for c in checks if c["required"] and not c["ok"]]
                    if code or blocked:
                        return self.record_server(actor, server_id, "server.install_failed", "BLOCKED", checks, "无法安装，缺少条件：" + "、".join(blocked or ["环境检测"]))
                    prefix, stdin = ssh.privilege(facts, r.auth_type, credentials)
                    cert, key, fingerprint = ssh.make_certificate()
                    script = ssh.install_script(self.relay_root, r.relay_port, secret, cert, key, self.relay_listen)
                    code, out, err = ssh.run_as_root(remote, script, prefix, stdin)
                    host_key = r.host_key or remote.host_key
            except ssh.SSHFailure as exc:
                return self.record_server(actor, server_id, "server.install_failed", "ERROR", None, str(exc))
            if code:
                tail = (out + "\n" + err).replace(secret, "[REDACTED]").strip()[-800:]
                return self.record_server(actor, server_id, "server.install_failed", "ERROR", checks, f"安装脚本失败（退出码 {code}）：{tail}")
            # The remote now holds the new secret; store it even if the port is still closed.
            self.record_server(
                actor, server_id, "server.installed", "INSTALLED", checks, None,
                host_key=host_key,
                relay_secret_ciphertext=encrypt_config({"secret": secret}, self.settings.encryption_key),
                relay_fingerprint=fingerprint,
                relay_version=ssh.relay_agent.VERSION,
                installed_at=now(),
            )
            with self.db.sessions() as s:
                r = self.owned_server(s, actor, server_id)
            health = self.relay_health(r)
            checks = checks + [health]
            if health["ok"]:
                return self.record_server(actor, server_id, "server.checked", "INSTALLED", checks)
            return self.record_server(actor, server_id, "server.checked", "UNREACHABLE", checks, "服务已安装并运行，但本机连不上转发端口；请在安全组放行后点“检查服务”")

    def check_server(self, actor, server_id):
        """Hub → relay TLS health plus a real egress call to Amazon through it."""
        self.require_session(actor)
        with self.db.sessions() as s:
            r = self.owned_server(s, actor, server_id)
        if not r.relay_secret_ciphertext:
            raise Problem(409, "该服务器尚未安装转发服务")
        checks = [self.relay_health(r)]
        if checks[0]["ok"]:
            started = time.monotonic()
            try:
                status = relay_transport.probe_egress(self.relay_of(r), EGRESS_PROBE)
                checks.append({"key": "egress", "label": "Amazon 出口", "ok": True, "detail": f"经 {r.name} 访问 Amazon Ads API 返回 HTTP {status}（未带授权的探测请求，有响应即出口可用），耗时 {int((time.monotonic() - started) * 1000)} ms", "required": False})
            except Exception as exc:
                checks.append({"key": "egress", "label": "Amazon 出口", "ok": False, "detail": redact(str(exc))[:300], "required": False})
        ok = all(c["ok"] for c in checks)
        return self.record_server(actor, server_id, "server.checked", "INSTALLED" if ok else "UNREACHABLE", checks, None if ok else "转发服务检查未通过")

    def uninstall_server(self, actor, server_id):
        self.require_session(actor)
        with self.db.sessions() as s:
            r = self.owned_server(s, actor, server_id)
            if self.bound_accounts(s, r):
                raise Problem(409, "仍有店铺使用该服务器转发，请先把它们切回本地直连")
        with self.server_lock(server_id):
            try:
                remote, credentials = self.remote(r)
                with remote:
                    code, out, err = remote.run(ssh.probe_script(r.relay_port, self.relay_root))
                    prefix, stdin = ssh.privilege(ssh.parse_facts(out), r.auth_type, credentials)
                    code, out, err = ssh.run_as_root(remote, ssh.uninstall_script(self.relay_root), prefix, stdin)
            except ssh.SSHFailure as exc:
                return self.record_server(actor, server_id, "server.uninstall_failed", "ERROR", None, str(exc))
            if code:
                return self.record_server(actor, server_id, "server.uninstall_failed", "ERROR", None, f"卸载失败（退出码 {code}）：{(out + err).strip()[-500:]}")
            return self.record_server(
                actor, server_id, "server.uninstalled", "NEW", [], "已卸载 ads-relay 并删除其文件和系统用户",
                relay_secret_ciphertext=None, relay_fingerprint=None, relay_version=None, installed_at=None,
            )

    def set_account_relay(self, actor, account_id, relay_id):
        if actor.kind != "session":
            raise Problem(403, "仅管理页面可修改账户")
        with self.db.sessions.begin() as s:
            a = self.account(s, actor, account_id)
            if relay_id:
                r = self.owned_server(s, actor, relay_id)
                if not r.relay_secret_ciphertext:
                    raise Problem(409, "该服务器尚未安装转发服务")
            before, a.relay_id = a.relay_id, relay_id or None
            audit(s, actor.user_id, "account.egress_changed", account=a.id, detail={"from": before, "to": a.relay_id})
        with self.gateway.lock:
            self.amc_cache.pop((actor.user_id, account_id), None)
        return account_json(a)

    def verify_account(self, actor, account_id):
        actor.require("ads:read")
        with self.db.sessions() as s:
            a = self.account(s, actor, account_id)
        try:
            with self.db.api_slot():
                _, _, _, profile = self.gateway.context(self.environment(a))
        except Problem:
            raise
        except Exception as exc:
            raise Problem(502, str(redact(str(exc)))) from None
        with self.db.sessions.begin() as s:
            a = self.account(s, actor, account_id)
            a.verified_at, a.profile = now(), profile
            audit(s, actor.user_id, "account.verified", account=a.id)
        return account_json(a)

    def amc_overview(self, actor, account_id, refresh=False):
        """AMC instance, SQL-usable tables and templates for the web console."""
        actor.require("ads:read")
        with self.db.sessions() as s:
            a = self.account(s, actor, account_id)
        env = self.environment(a)
        key = (actor.user_id, a.id)
        with self.gateway.lock:
            cached = self.amc_cache.get(key)
        if cached and cached[0] > time.monotonic() and not refresh:
            return cached[1]
        try:
            with self.db.api_slot():
                client, token, _, _ = self.gateway.context(env)
                entity, instance = self.gateway.amc(env, client, token)
                sources = client.amc_data_sources(token, entity, instance["instanceId"])
            value = {
                "available": True,
                "instance": summarize_amc_instance(instance),
                "dataSources": summarize_amc_data_sources(sources),
            }
        except Problem:
            raise
        except Exception as exc:
            message = str(redact(str(exc)))
            value = {
                "available": False,
                "reason": "AMC 未授权：请用该 Amazon 账号登录 AMC 控制台接受条款后重试"
                if " 403 " in message or "Unauthorized" in message
                else message[:500],
            }
        value["templates"] = public_amc_templates()
        with self.gateway.lock:
            self.amc_cache[key] = (time.monotonic() + (1800 if value["available"] else 60), value)
        return value

    def create_token(self, actor, name, scopes, account_ids, days):
        if actor.kind != "session":
            raise Problem(403, "仅管理页面可生成 Token")
        if not scopes or not set(scopes) <= SCOPES or not account_ids:
            raise Problem(400, "请选择权限及账户")
        raw = new_token_value()
        with self.db.sessions.begin() as s:
            for account_id in account_ids:
                self.account(s, actor, account_id)
            t = Token(
                owner_id=actor.user_id,
                name=name,
                prefix=raw[:14],
                token_hash=token_hash(raw),
                scopes=sorted(set(scopes)),
                account_ids=sorted(set(account_ids)),
                expires_at=NEVER_EXPIRES if days is None else now() + timedelta(days=days),
                token_ciphertext=encrypt_config({"token": raw}, self.settings.encryption_key),
            )
            s.add(t)
            s.flush()
            audit(
                s,
                actor.user_id,
                "token.created",
                detail={"token_id": t.id, "scopes": scopes},
            )
        return {
            "id": t.id,
            "token": raw,
            "prefix": t.prefix,
            "expires_at": t.expires_at.isoformat(),
            "permanent": t.expires_at >= NEVER_EXPIRES,
        }

    def tokens(self, actor):
        with self.db.sessions() as s:
            rows = s.scalars(
                select(Token)
                .where(Token.owner_id == actor.user_id, Token.deleted_at.is_(None))
                .order_by(Token.created_at.desc())
            ).all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "prefix": t.prefix,
                    "scopes": t.scopes,
                    "account_ids": t.account_ids,
                    "created_at": t.created_at.isoformat(),
                    "expires_at": t.expires_at.isoformat(),
                    "permanent": t.expires_at >= NEVER_EXPIRES,
                    "revoked": bool(t.revoked_at),
                    "can_reveal": bool(t.token_ciphertext)
                    and not t.revoked_at
                    and t.expires_at > now(),
                    "last_used_at": t.last_used_at.isoformat()
                    if t.last_used_at
                    else None,
                }
                for t in rows
            ]

    def owned_token(self, s, actor, token_id):
        if actor.kind != "session":
            raise Problem(403, "仅管理页面可管理 Token")
        t = s.scalar(
            select(Token)
            .where(
                Token.id == token_id,
                Token.owner_id == actor.user_id,
                Token.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if not t:
            raise Problem(404, "Token 不存在")
        return t

    def reveal_token(self, actor, token_id):
        with self.db.sessions.begin() as s:
            t = self.owned_token(s, actor, token_id)
            if t.revoked_at or t.expires_at <= now():
                raise Problem(409, "已撤销或已过期的 Token 不能再查看")
            if not t.token_ciphertext:
                raise Problem(409, "该 Token 生成于支持再次查看之前，明文没有保存；点“重新生成”后即可复制")
            raw = decrypt_config(t.token_ciphertext, self.settings.encryption_key)["token"]
            audit(s, actor.user_id, "token.revealed", detail={"token_id": t.id})
        return {"token": raw}

    def rotate_token(self, actor, token_id):
        # Same name, accounts, scopes and expiry; only the secret changes, so
        # tokens issued before plaintext was stored can be copied again.
        raw = new_token_value()
        with self.db.sessions.begin() as s:
            t = self.owned_token(s, actor, token_id)
            if t.revoked_at or t.expires_at <= now():
                raise Problem(409, "已撤销或已过期的 Token 不能重新生成")
            t.prefix = raw[:14]
            t.token_hash = token_hash(raw)
            t.token_ciphertext = encrypt_config({"token": raw}, self.settings.encryption_key)
            t.last_used_at = None
            audit(s, actor.user_id, "token.rotated", detail={"token_id": t.id})
        return {"id": token_id, "token": raw, "prefix": raw[:14]}

    def revoke_token(self, actor, token_id):
        with self.db.sessions.begin() as s:
            t = self.owned_token(s, actor, token_id)
            t.revoked_at = t.revoked_at or now()
            t.token_ciphertext = None
            audit(s, actor.user_id, "token.revoked", detail={"token_id": t.id})
        return {"revoked": True}

    def delete_token(self, actor, token_id):
        # Soft delete: tasks keep their source_token_id reference, and the
        # revoked_at check still stops any queued work from that token.
        with self.db.sessions.begin() as s:
            t = self.owned_token(s, actor, token_id)
            t.revoked_at = t.revoked_at or now()
            t.token_ciphertext = None
            t.deleted_at = now()
            audit(s, actor.user_id, "token.deleted", detail={"token_id": t.id})
        return {"deleted": True}

    def sync_reports(self, actor, account_id, days):
        """Queue supported reports; stable daily keys make retries safe across tabs."""
        if days not in (1, 7):
            raise Problem(400, "同步范围只能为 1 天或 7 天")
        actor.require("reports:create")
        actor.require("ads:read")
        with self.db.sessions() as s:
            account = self.account(s, actor, account_id)
            zone = account.profile.get("timezone")
        if not zone:
            raise Problem(400, "账户缺少时区，请先验证账户后同步")
        try:
            today = datetime.now(ZoneInfo(zone)).date()
        except ZoneInfoNotFoundError:
            raise Problem(400, "账户时区无效，请重新验证账户") from None
        end = today - timedelta(days=1)
        start = end - timedelta(days=days - 1)
        tasks, failures, skipped = [], [], []

        def enqueue(operation, arguments, suffix=""):
            key = f"sync:{account_id}:{start}:{end}:{operation}:{suffix}"
            # Hash the batch identity to keep keys below the existing API limit.
            key = "sync:" + hashlib.sha256(key.encode()).hexdigest()
            try:
                tasks.append(self.create_task(actor, account_id, operation,
                                              arguments, key, "report"))
            except Problem as exc:
                failures.append({"operation": operation, "detail": str(exc)})

        for entry in public_catalog():
            operation = entry["operation"]
            if entry["kind"] == "report" and operation != "reports.create-amc-query":
                enqueue(operation, {"start_date": str(start), "end_date": str(end),
                                    "time_unit": "DAILY"})
        try:
            amc = self.amc_overview(actor, account_id)
            if amc["available"]:
                sources = {source["id"] for source in amc["dataSources"]}
                for template in amc["templates"]:
                    if template.get("category") != "full":
                        continue
                    if not set(template["sources"]).issubset(sources):
                        skipped.append({"operation": template["id"], "detail": "所需 AMC 数据源未开通"})
                        continue
                    enqueue("reports.create-amc-query", {
                        "template": template["id"], "start_date": str(start),
                        "end_date": str(end), "time_zone": zone,
                    }, template["id"])
            else:
                skipped.append({"operation": "AMC", "detail": amc.get("reason", "AMC 不可用")})
        except Problem as exc:
            failures.append({"operation": "AMC", "detail": str(exc)})
        return {"account_id": account_id, "start_date": str(start),
                "end_date": str(end), "timezone": zone, "tasks": tasks,
                "failures": failures, "skipped": skipped}

    def create_task(self, actor, account_id, operation, arguments, key, kind):
        if not isinstance(key, str) or not 8 <= len(key) <= 120:
            raise Problem(400, "幂等键长度需为 8–120")
        actor.require(
            {"read": "ads:read", "report": "reports:create", "write": "changes:plan"}[
                kind
            ]
        )
        entry = validate_arguments(operation, arguments)
        if entry["kind"] != kind:
            raise Problem(400, "操作类型不匹配")
        with self.db.sessions() as s:
            a = self.account(s, actor, account_id)
        env = self.environment(a)
        mode = {"read": "read", "report": "report_plan", "write": "plan"}[kind]
        payload = (
            arguments
            if kind == "read"
            else invoke_contract(operation, arguments, env, mode)
        )
        digest = bound_hash(actor.user_id, a.id, a.profile_id, operation, payload)
        try:
            with self.db.sessions.begin() as s:
                old = s.scalar(
                    select(Task).where(
                        Task.owner_id == actor.user_id, Task.idempotency_key == key
                    )
                )
                if old:
                    if old.payload_hash != digest:
                        raise Problem(409, "幂等键已用于不同操作")
                    return task_json(old, True)
                t = Task(
                    owner_id=actor.user_id,
                    account_id=a.id,
                    kind=kind,
                    operation=operation,
                    arguments=arguments,
                    payload=payload,
                    payload_hash=digest,
                    idempotency_key=key,
                    source_token_id=actor.token_id,
                    status="AWAITING_CONFIRMATION" if kind == "write" else "QUEUED",
                    approval_expires_at=now() + timedelta(hours=24)
                    if kind == "write"
                    else None,
                )
                s.add(t)
                s.flush()
                audit(
                    s,
                    actor.user_id,
                    "task.created",
                    t.status,
                    a.id,
                    t.id,
                    {
                        "operation": operation,
                        "arguments": arguments,
                        "payload_hash": digest,
                    },
                )
                return task_json(t, True)
        except IntegrityError:
            with self.db.sessions() as s:
                old = s.scalar(
                    select(Task).where(
                        Task.owner_id == actor.user_id, Task.idempotency_key == key
                    )
                )
                if not old or old.payload_hash != digest:
                    raise Problem(409, "幂等键冲突") from None
                return task_json(old, True)

    def owned_task(self, s, actor, task_id):
        t = s.scalar(
            select(Task).where(Task.id == task_id, Task.owner_id == actor.user_id)
        )
        if not t or not actor.account_allowed(t.account_id):
            raise Problem(404, "任务不存在或不可访问")
        if actor.kind == "token":
            actor.require(
                "reports:read"
                if t.kind == "report"
                else "changes:plan"
                if t.kind == "write"
                else "ads:read"
            )
        return t

    def task(self, actor, task_id):
        with self.db.sessions() as s:
            return task_json(self.owned_task(s, actor, task_id), True)

    def tasks(
        self, actor, status=None, offset=0, limit=50, kind=None, account_id=None, operation=None
    ):
        with self.db.sessions() as s:
            q = select(Task).where(Task.owner_id == actor.user_id)
            if actor.kind == "token":
                q = q.where(Task.account_id.in_(actor.account_ids))
            if status:
                q = q.where(Task.status == status)
            if kind:
                q = q.where(Task.kind == kind)
            if account_id:
                q = q.where(Task.account_id == account_id)
            if operation:
                q = q.where(Task.operation == operation)
            rows = s.scalars(
                q.order_by(Task.created_at.desc()).offset(offset).limit(limit)
            ).all()
            if actor.kind == "token":
                rows = [
                    t
                    for t in rows
                    if {
                        "read": "ads:read",
                        "report": "reports:read",
                        "write": "changes:plan",
                    }[t.kind]
                    in actor.scopes
                ]
            return [task_json(t) for t in rows]

    def approve(self, actor, task_id, confirm_text, expected_hash):
        if actor.kind == "token" and "changes:approve" not in actor.scopes:
            raise Problem(403, "此 MCP Token 没有“确认执行变更”权限，请在管理页面确认")
        if confirm_text != "确认":
            raise Problem(400, "请输入“确认”")
        with self.db.sessions.begin() as s:
            t = s.scalar(
                select(Task)
                .where(Task.id == task_id, Task.owner_id == actor.user_id)
                .with_for_update()
            )
            if not t:
                raise Problem(404, "任务不存在")
            if t.kind != "write" or t.status != "AWAITING_CONFIRMATION":
                raise Problem(409, "计划已执行、已确认或不可确认")
            if t.approval_expires_at <= now():
                raise Problem(409, "计划已过期，请重新生成")
            a = self.account(s, actor, t.account_id)
            if actor.kind == "token" and t.source_token_id != actor.token_id:
                raise Problem(403, "只能确认本 Token 提交的计划，其他计划请在管理页面确认")
            actual = bound_hash(
                actor.user_id, a.id, a.profile_id, t.operation, t.payload
            )
            if expected_hash != t.payload_hash or actual != expected_hash:
                raise Problem(409, "计划内容已变化")
            t.approved_by, t.approved_at, t.status, t.next_run_at = (
                actor.user_id,
                now(),
                "QUEUED",
                now(),
            )
            audit(
                s,
                actor.user_id,
                "task.approved",
                "QUEUED",
                a.id,
                t.id,
                {
                    "payload_hash": actual,
                    "via": "mcp" if actor.kind == "token" else "web",
                    "token_id": actor.token_id,
                },
            )
            return task_json(t, True)

    def cancel(self, actor, task_id):
        if actor.kind != "session":
            raise Problem(403, "仅管理页面可取消任务")
        with self.db.sessions.begin() as s:
            t = s.scalar(
                select(Task)
                .where(Task.id == task_id, Task.owner_id == actor.user_id)
                .with_for_update()
            )
            if not t:
                raise Problem(404, "任务不存在")
            if t.status not in {"QUEUED", "WAITING", "AWAITING_CONFIRMATION"}:
                raise Problem(409, "任务已开始执行或已结束，不能取消")
            t.status = "CANCELLED"
            audit(s, actor.user_id, "task.cancelled", "CANCELLED", t.account_id, t.id)
            return task_json(t)

    def result_summary(self, actor, task_id, group_by, metrics):
        """Sum numeric fields over every saved row, optionally grouped by one field."""
        names = [m for m in metrics if m]
        if not names or len(names) > 40 or len(set(names)) != len(names):
            raise Problem(400, "请选择 1–40 个不重复的汇总字段")
        for name in names + ([group_by] if group_by else []):
            if not FIELD.fullmatch(name):
                raise Problem(400, "字段名不合法: " + name[:64])
        if group_by in names:
            raise Problem(400, "汇总维度不能同时作为汇总字段")
        with self.db.sessions() as s:
            t = self.owned_task(s, actor, task_id)
            if t.kind != "report":
                raise Problem(400, "只有报表任务支持汇总")
            # Field names are bound parameters; only the m0..mN aliases are generated.
            params = {"task": task_id, "group": group_by or ""}
            sums = []
            for i, name in enumerate(names):
                params[f"f{i}"] = name
                sums.append(
                    f"SUM(CASE WHEN jsonb_typeof(data->:f{i}) = 'number' THEN (data->>:f{i})::numeric END) AS m{i}"
                )
            columns = ", ".join(["COUNT(*) AS n", *sums])
            base = f"FROM ads_report_rows WHERE task_id = :task"

            def shape(values):
                # values = (count, sum0, sum1, ...)
                return {
                    "rows": values[0],
                    "sums": {
                        name: None if values[i + 1] is None else float(values[i + 1])
                        for i, name in enumerate(names)
                    },
                }

            total = shape(tuple(s.execute(text(f"SELECT {columns} {base}"), params).one()))
            groups, truncated = [], False
            if group_by:
                found = s.execute(
                    text(
                        f"SELECT data->>:group AS k, {columns} {base} GROUP BY 1 ORDER BY n DESC, 1 LIMIT 2001"
                    ),
                    params,
                ).all()
                truncated = len(found) > 2000
                groups = [{"key": row[0], **shape(tuple(row[1:]))} for row in found[:2000]]
        return {
            "group_by": group_by,
            "total": total,
            "groups": groups,
            "truncated": truncated,
        }

    def result_rows(self, actor, task_id, offset, limit):
        with self.db.sessions() as s:
            t = self.owned_task(s, actor, task_id)
            if t.kind != "report":
                data = (
                    t.result
                    if isinstance(t.result, list)
                    else [t.result]
                    if t.result is not None
                    else []
                )
                return {
                    "rows": redact(data[offset : offset + limit]),
                    "total": len(data),
                    "offset": offset,
                    "status": t.status,
                }
            data = s.scalars(
                select(ReportRow)
                .where(ReportRow.task_id == task_id)
                .order_by(ReportRow.row_no)
                .offset(offset)
                .limit(limit)
            ).all()
            return {
                "rows": [r.data for r in data],
                "total": t.row_count,
                "offset": offset,
                "status": t.status,
            }

    def logs(self, actor, offset=0, limit=50):
        with self.db.sessions() as s:
            q = select(Audit).where(Audit.owner_id == actor.user_id)
            if actor.kind == "token":
                q = q.where(Audit.account_id.in_(actor.account_ids))
            rows = s.scalars(
                q.order_by(Audit.created_at.desc()).offset(offset).limit(limit)
            ).all()
            # Attribute each row to an MCP token without an audit column, so old
            # rows resolve too: an explicit detail.token_id wins (None = web),
            # otherwise the token that submitted the row's task.
            task_ids = {r.task_id for r in rows if r.task_id}
            task_tokens = dict(
                s.execute(
                    select(Task.id, Task.source_token_id).where(Task.id.in_(task_ids))
                ).all()
            ) if task_ids else {}
            row_tokens = {}
            for r in rows:
                detail = r.detail if isinstance(r.detail, dict) else {}
                token_id = (
                    detail.get("token_id")
                    if "token_id" in detail
                    else task_tokens.get(r.task_id)
                )
                row_tokens[r.id] = token_id if isinstance(token_id, str) else None
            token_ids = {v for v in row_tokens.values() if v}
            names = {
                t.id: (t.name, t.prefix)
                for t in s.scalars(
                    select(Token).where(
                        Token.id.in_(token_ids), Token.owner_id == actor.user_id
                    )
                )
            } if token_ids else {}
            return [
                {
                    "id": r.id,
                    "action": r.action,
                    "status": r.status,
                    "account_id": r.account_id,
                    "task_id": r.task_id,
                    "token_name": names.get(row_tokens[r.id], (None, None))[0],
                    "token_prefix": names.get(row_tokens[r.id], (None, None))[1],
                    "detail": r.detail,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]

    def overview(self, actor):
        with self.db.sessions() as s:
            counts = dict(
                s.execute(
                    select(Task.status, func.count())
                    .where(Task.owner_id == actor.user_id)
                    .group_by(Task.status)
                ).all()
            )
            return {
                "accounts": s.scalar(
                    select(func.count())
                    .select_from(Account)
                    .where(Account.owner_id == actor.user_id)
                ),
                "tasks_by_status": counts,
                "report_rows": s.scalar(
                    select(func.coalesce(func.sum(Task.row_count), 0)).where(
                        Task.owner_id == actor.user_id
                    )
                ),
                "mcp_endpoint": self.settings.public_origin + "/mcp/",
                "max_api_concurrency": self.settings.api_concurrency,
            }
