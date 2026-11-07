import { useRef, useState } from "react";
import { ArrowClockwise } from "@phosphor-icons/react";
import { Modal } from "./ui";
import { api } from "../api";
import type { Task } from "../lib/types";
import { useWorkspace } from "../workspace";

type SyncResult = {
  account_id: string;
  start_date: string;
  end_date: string;
  timezone: string;
  tasks: Task[];
  failures: { operation: string; detail: string }[];
  skipped: { operation: string; detail: string }[];
};

export function SyncActions() {
  const { selected, accountId, busy, action, navigate } = useWorkspace();
  const [result, setResult] = useState<SyncResult | null>(null);
  const submitting = useRef(false);
  function sync(days: 1 | 7) {
    if (!accountId || busy || submitting.current) return;
    submitting.current = true;
    setResult(null);
    void action(`sync-${days}`, async () => {
      setResult(
        await api<SyncResult>(`/accounts/${accountId}/sync`, "POST", { days }),
      );
    }).finally(() => {
      submitting.current = false;
    });
  }
  const visible = result?.account_id === accountId ? result : null;
  return (
    <div className="sync-controls">
      <div className="sync-buttons">
        {([1, 7] as const).map((days) => (
          <button
            key={days}
            className="secondary"
            disabled={!selected?.timezone || !!busy}
            onClick={() => sync(days)}
            aria-busy={busy === `sync-${days}`}
          >
            <ArrowClockwise
              size={17}
              className={busy === `sync-${days}` ? "spin" : ""}
            />
            {busy === `sync-${days}`
              ? "正在提交…"
              : days === 1
                ? "同步最新数据"
                : "同步7天数据"}
          </button>
        ))}
      </div>
      <small className="sync-help">
        {selected?.timezone
          ? "当前账户 · 截至昨天 · 同日重复点击复用任务"
          : "连接并验证账户时区后可同步"}
      </small>
      {visible && (
        <Modal title="同步任务已提交" close={() => setResult(null)}>
          <div className="sync-result" role="status">
            <strong>{visible.tasks.length} 个任务已创建或复用</strong>
            <p>
              {visible.start_date} 至 {visible.end_date} · {visible.timezone}
            </p>
            <p>报表在后台生成；AMC 最近两天的数据可能尚未完整。</p>
            {!!(visible.failures.length + visible.skipped.length) && (
              <details>
                <summary>
                  {visible.failures.length} 项提交失败，{visible.skipped.length}{" "}
                  项跳过
                </summary>
                {[...visible.failures, ...visible.skipped].map((item, i) => (
                  <p key={i}>
                    {item.operation}：{item.detail}
                  </p>
                ))}
              </details>
            )}
            <button
              className="text-button"
              onClick={() => navigate("/reports")}
            >
              查看任务与同步结果
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
