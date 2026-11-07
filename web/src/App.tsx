import {
  useEffect,
  useEffectEvent,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle, WarningCircle, X } from "@phosphor-icons/react";
import { api, setCsrf } from "./api";
import { PAGE_SIZE } from "./lib/constants";
import type {
  Account,
  Capability,
  LogEntry,
  MCPToken,
  Overview as OverviewData,
  RelayServer,
  SetupState,
  Task,
} from "./lib/types";
import { WorkspaceContext, type Workspace } from "./workspace";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { TaskDetail } from "./components/TaskDetail";
import { AccountModal } from "./components/AccountModal";
import { TokenModal } from "./components/TokenModal";
import { AuthorCredit } from "./components/ui";
import { Login } from "./pages/Login";
import { Setup } from "./pages/Setup";
import { ResetPassword } from "./pages/ResetPassword";
import { Password } from "./pages/Password";
import { ReportData } from "./pages/ReportData";
import { Amc } from "./pages/Amc";
import { Overview } from "./pages/Overview";
import { Accounts } from "./pages/Accounts";
import { Reports } from "./pages/Reports";
import { Operations } from "./pages/Operations";
import { Approvals } from "./pages/Approvals";
import { Tokens } from "./pages/Tokens";
import { Servers } from "./pages/Servers";
import { Logs } from "./pages/Logs";

const pages: Record<string, () => ReactNode> = {
  "/": Overview,
  "/accounts": Accounts,
  "/servers": Servers,
  "/reports": Reports,
  "/data": ReportData,
  "/amc": Amc,
  "/operations": Operations,
  "/approvals": Approvals,
  "/tokens": Tokens,
  "/logs": Logs,
  "/password": Password,
};

/** The approvals page opens on pending plans; every other page shows all statuses. */
function defaultFilter(path: string) {
  return path === "/approvals" ? "AWAITING_CONFIRMATION" : "";
}

export default function App() {
  const [user, setUser] = useState<string | null>(null),
    [booting, setBooting] = useState(true),
    [setup, setSetup] = useState<SetupState | null>(null),
    [loginNotice, setLoginNotice] = useState(""),
    [page, setPage] = useState(location.pathname);
  const [accounts, setAccounts] = useState<Account[]>([]),
    [accountId, setAccountId] = useState(""),
    [tasks, setTasks] = useState<Task[]>([]),
    [tokens, setTokens] = useState<MCPToken[]>([]),
    [servers, setServers] = useState<RelayServer[]>([]),
    [logs, setLogs] = useState<LogEntry[]>([]),
    [catalog, setCatalog] = useState<Capability[]>([]),
    [overview, setOverview] = useState<OverviewData>({});
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(""),
    [synced, setSynced] = useState(""),
    [offset, setOffset] = useState(0),
    [filter, setFilter] = useState(() => defaultFilter(location.pathname));
  const [accountModal, setAccountModal] = useState(false),
    [tokenModal, setTokenModal] = useState(false),
    [oneTime, setOneTime] = useState(""),
    [detail, setDetail] = useState<Task | null>(null);
  const actionLock = useRef(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const selected = accounts.find((a) => a.id === accountId);

  function navigate(path: string) {
    history.pushState({}, "", path);
    const pathname = new URL(path, location.origin).pathname;
    setPage(pathname);
    setOffset(0);
    setFilter(defaultFilter(pathname));
    setOneTime("");
    setDetail(null);
    setNotice("");
    setError("");
  }
  function clearSession() {
    setInitialLoading(true);
    setUser(null);
    setCsrf("");
    setAccounts([]);
    setTasks([]);
    setTokens([]);
    setServers([]);
    setLogs([]);
    setOverview({});
    setAccountId("");
    setDetail(null);
    setOneTime("");
  }
  useEffect(() => {
    const change = () => {
      setPage(location.pathname);
      setOffset(0);
      setFilter(defaultFilter(location.pathname));
    };
    addEventListener("popstate", change);
    return () => removeEventListener("popstate", change);
  }, []);
  useEffect(() => {
    api("/session")
      .then((s) => {
        setCsrf(s.csrf_token);
        setUser(s.username);
      })
      .catch(() =>
        // No session: a fresh database shows the first-run setup instead.
        api<SetupState>("/setup")
          .then((st) => setSetup(st.needs_setup ? st : null))
          .catch(() => {}),
      )
      .finally(() => setBooting(false));
  }, []);
  useEffect(() => {
    if (!notice) return;
    const id = setTimeout(() => setNotice(""), 4000);
    return () => clearTimeout(id);
  }, [notice]);
  async function refresh() {
    const [a, o, c, t] = await Promise.all([
      api<Account[]>("/accounts"),
      api<OverviewData>("/overview"),
      api<Capability[]>("/capabilities"),
      api<Task[]>(
        `/tasks?offset=${offset}&limit=${PAGE_SIZE}${filter ? "&status=" + filter : ""}`,
      ),
    ]);
    setInitialLoading(false);
    setAccounts(a);
    setOverview(o);
    setCatalog(c);
    setTasks(t);
    setAccountId((old) => (a.some((v) => v.id === old) ? old : a[0]?.id || ""));
    setSynced(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    if (page === "/tokens") setTokens(await api("/tokens"));
    if (page === "/servers" || page === "/accounts")
      setServers(await api("/servers"));
    if (page === "/logs")
      setLogs(await api(`/logs?offset=${offset}&limit=${PAGE_SIZE}`));
  }
  const tick = useEffectEvent(() =>
    refresh().catch((e) => {
      if (e.status === 401) {
        clearSession();
      } else setError(e.message);
    }),
  );
  useEffect(() => {
    if (!user) return;
    tick();
    const id = setInterval(() => tick(), 5000);
    return () => clearInterval(id);
  }, [user, page, offset, filter]);
  async function action(name: string, fn: () => Promise<unknown>) {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      actionLock.current = false;
      setBusy("");
    }
  }
  async function openTask(id: string) {
    setError("");
    try {
      setDetail(await api<Task>(`/tasks/${id}`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function closeTask() {
    setDetail(null);
    if (new URLSearchParams(location.search).has("task"))
      history.replaceState({}, "", location.pathname);
  }
  useEffect(() => {
    const id = new URLSearchParams(location.search).get("task");
    if (user && id) void openTask(id);
  }, [user]);
  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice("已复制");
    } catch {
      setError("浏览器未允许复制，请手动选择复制");
    }
  }
  function logout() {
    api("/logout", "POST", {})
      .then(() => {
        clearSession();
        setError("");
      })
      .catch((e) => setError(e.message));
  }

  if (booting) return <div className="boot">正在连接 Ads Console…</div>;
  if (!user && setup)
    return (
      <Setup
        state={setup}
        onDone={(name) => {
          setSetup(null);
          setUser(name);
        }}
        onAlreadySetup={(message) => {
          setSetup(null);
          setLoginNotice(message);
        }}
      />
    );
  if (!user && page === "/reset-password")
    return (
      <ResetPassword
        onBack={() => navigate("/")}
        onDone={(message) => {
          navigate("/");
          setLoginNotice(message);
        }}
      />
    );
  if (!user)
    return (
      <Login
        onLogin={(name) => {
          setLoginNotice("");
          setUser(name);
        }}
        onForgot={() => navigate("/reset-password")}
        notice={loginNotice}
      />
    );

  const workspace: Workspace = {
    user,
    page,
    navigate,
    accounts,
    accountId,
    setAccountId,
    selected,
    tasks,
    tokens,
    servers,
    logs,
    catalog,
    overview,
    busy,
    action,
    openTask,
    copy,
    setNotice,
    setError,
    offset,
    setOffset,
    filter,
    setFilter,
    openAccountModal: () => setAccountModal(true),
    openTokenModal: () => setTokenModal(true),
    oneTime,
    setOneTime,
  };
  const Page = pages[page] || Overview;
  return (
    <WorkspaceContext.Provider value={workspace}>
      <div className="shell">
        <Sidebar onLogout={logout} />
        <main className="main">
          <Topbar
            synced={synced}
            onRefresh={() => action("refresh", refresh)}
          />
          {error && (
            <div className="banner error" role="alert">
              <WarningCircle size={20} />
              <span>{error}</span>
              <button aria-label="关闭错误" onClick={() => setError("")}>
                <X />
              </button>
            </div>
          )}
          {notice && (
            <div className="banner success" role="status">
              <CheckCircle size={20} />
              <span>{notice}</span>
              <button aria-label="关闭提示" onClick={() => setNotice("")}>
                <X />
              </button>
            </div>
          )}
          <div className="page" key={page}>
            {initialLoading ? (
              <section
                className="panel loading-panel"
                role="status"
                aria-busy="true"
              >
                <h2>{error ? "暂时无法载入工作空间" : "正在载入工作空间…"}</h2>
                <p>
                  {error
                    ? "请检查连接后重试，已有数据不会丢失。"
                    : "正在读取账户、任务和报表状态。"}
                </p>
                {error ? (
                  <button
                    className="secondary"
                    disabled={!!busy}
                    onClick={() => action("refresh", refresh)}
                  >
                    重新加载
                  </button>
                ) : (
                  <div className="loading-bars" aria-hidden="true">
                    <i />
                    <i />
                    <i />
                  </div>
                )}
              </section>
            ) : (
              <Page />
            )}
          </div>
          <footer className="main-footer">
            <span>Amazon Ads Ops Workbench</span>
            <AuthorCredit />
          </footer>
        </main>
        {accountModal && <AccountModal close={() => setAccountModal(false)} />}
        {tokenModal && <TokenModal close={() => setTokenModal(false)} />}
        {detail && (
          <TaskDetail
            key={detail.id}
            task={detail}
            setTask={setDetail}
            close={closeTask}
          />
        )}
      </div>
    </WorkspaceContext.Provider>
  );
}
