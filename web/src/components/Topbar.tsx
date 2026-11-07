import { ArrowClockwise, Buildings } from "@phosphor-icons/react";
import { useWorkspace } from "../workspace";
import { Select } from "./Select";

export function Topbar({
  synced,
  onRefresh,
}: {
  synced: string;
  onRefresh: () => void;
}) {
  const { accounts, accountId, setAccountId, selected, busy } = useWorkspace();
  return (
    <header className="topbar">
      <div className="account-switch">
        <span aria-hidden="true">
          <Buildings size={16} />
          当前账户
        </span>
        <Select
          ariaLabel="当前账户"
          size="sm"
          className="account-select"
          menuWidth={320}
          value={accountId}
          onChange={setAccountId}
          disabled={!accounts.length || !!busy}
          placeholder="尚未连接账户"
          options={accounts.map((a) => ({
            value: a.id,
            label: `${a.label} · ${a.marketplace}`,
            description: `${a.region} · Profile ${a.profile_id}${
              a.verified_at ? "" : " · 待验证"
            }`,
          }))}
        />
        {selected && !selected.verified_at && (
          <span className="status waiting">待验证</span>
        )}
      </div>
      <div className="top-actions">
        <span className="sync">
          <i aria-hidden="true" className={synced ? "live" : ""} />
          {synced ? "状态更新 " + synced : "正在读取状态"}
        </span>
        <button
          className="icon-button"
          aria-label="立即刷新"
          data-tip="立即刷新"
          data-tip-align="end"
          onClick={onRefresh}
          disabled={!!busy}
        >
          <ArrowClockwise
            size={18}
            className={busy === "refresh" ? "spin" : ""}
          />
        </button>
      </div>
    </header>
  );
}
