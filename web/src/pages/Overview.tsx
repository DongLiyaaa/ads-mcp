import { SyncActions } from "../components/SyncActions";
import type { ReactNode } from "react";
import {
  ArrowRight,
  Buildings,
  ClockCounterClockwise,
  Database,
  Plus,
  PlugsConnected,
  ShieldCheck,
} from "@phosphor-icons/react";
import { ACTIVE_STATUSES } from "../lib/constants";
import { TaskTable } from "../components/TaskTable";
import { PageHeader, PanelHeading } from "../components/ui";
import { useWorkspace } from "../workspace";

function Stat({
  label,
  value,
  unit,
  note,
  icon,
  to,
  tone,
}: {
  label: string;
  value: number;
  unit?: string;
  note: string;
  icon: ReactNode;
  to: string;
  tone?: "attention";
}) {
  const { navigate } = useWorkspace();
  return (
    <a
      href={to}
      className={tone ? `stat ${tone}` : "stat"}
      onClick={(e) => {
        e.preventDefault();
        navigate(to);
      }}
    >
      <span className="stat-label">
        {label}
        {icon}
      </span>
      <strong>
        {value.toLocaleString()}
        {unit && <em>{unit}</em>}
      </strong>
      <small>{note}</small>
    </a>
  );
}

export function Overview() {
  const { overview, tasks, accounts, navigate, openAccountModal } =
    useWorkspace();
  const byStatus = overview.tasks_by_status || {};
  const pending = byStatus.AWAITING_CONFIRMATION || 0;
  const active = ACTIVE_STATUSES.reduce((n, k) => n + (byStatus[k] || 0), 0);
  return (
    <>
      <PageHeader
        title="工作概览"
        description="每 5 秒刷新任务状态；使用同步按钮从 Amazon 拉取当前账户的报表。"
        actions={
          <>
            <SyncActions />
            <button
              className="primary"
              disabled={!accounts.length}
              onClick={() => navigate("/reports")}
            >
              <Plus size={17} />
              创建报表
            </button>
          </>
        }
      />
      <section className="stats" aria-label="关键指标">
        <Stat
          label="待用户确认"
          value={pending}
          note={
            pending ? "尚未提交到 Amazon，点击前往核对" : "没有等待确认的变更"
          }
          icon={<ShieldCheck />}
          to="/approvals"
          tone={pending ? "attention" : undefined}
        />
        <Stat
          label="进行中的任务"
          value={active}
          note="等待结果时可以离开页面"
          icon={<ClockCounterClockwise />}
          to="/reports"
        />
        <Stat
          label="已保存报表数据"
          value={overview.report_rows || 0}
          unit="行"
          note="保存在 PostgreSQL 中"
          icon={<Database />}
          to="/reports"
        />
        <Stat
          label="已连接账户"
          value={overview.accounts ?? 0}
          note="独立凭证 · 按 Profile 隔离"
          icon={<Buildings />}
          to="/accounts"
        />
      </section>
      {accounts.length ? (
        <section className="connection-strip">
          <span className="strip-icon">
            <PlugsConnected size={22} />
          </span>
          <div>
            <h3>连接你的 AI 助手</h3>
            <p>
              生成账户范围明确的 Token，让 MCP
              读取数据、创建报表和提交变更计划。
            </p>
          </div>
          <button className="secondary" onClick={() => navigate("/tokens")}>
            管理 MCP Token
            <ArrowRight size={16} />
          </button>
        </section>
      ) : (
        <section className="connection-strip">
          <span className="strip-icon">
            <Buildings size={22} />
          </span>
          <div>
            <h3>先连接一个广告账户</h3>
            <p>
              准备 Client ID、Client Secret、Refresh Token 和站点 Profile
              ID，之后即可创建报表和 MCP Token。
            </p>
          </div>
          <button className="primary" onClick={openAccountModal}>
            <Plus size={16} />
            连接账户
          </button>
        </section>
      )}
      <section className="panel">
        <PanelHeading
          title="最近任务"
          description="真实任务状态，不以演示数据代替接口结果。"
        >
          <button className="text-button" onClick={() => navigate("/reports")}>
            查看全部
            <ArrowRight size={15} />
          </button>
        </PanelHeading>
        <TaskTable items={tasks.slice(0, 8)} />
      </section>
    </>
  );
}
