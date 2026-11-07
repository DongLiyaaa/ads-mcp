import { useEffect, useMemo, useState } from "react";
import { ArrowRight, DownloadSimple, Info, Plus } from "@phosphor-icons/react";
import { api } from "../api";
import {
  AMC_OPERATION,
  MAX_REPORT_DAYS,
  amcTemplateNames,
  reportNames,
  statuses,
} from "../lib/constants";
import { shiftDays, todayIn } from "../lib/dates";
import { daySpan, stamp } from "../lib/format";
import {
  columnLabel,
  formatCell,
  isAdditiveColumn,
  numericColumns,
  orderColumns,
} from "../lib/reportColumns";
import type { AmcPrivacy, RowsPage, SummaryResult, Task } from "../lib/types";
import { DateRangePicker } from "../components/DateRangePicker";
import { Select, type SelectOption } from "../components/Select";
import { SummaryTable } from "../components/SummaryTable";
import { reportLabel } from "../components/TaskTable";
import {
  Empty,
  PageHeader,
  Pagination,
  PanelHeading,
  Segmented,
} from "../components/ui";
import { useWorkspace } from "../workspace";

const PAGE_SIZES = ["50", "100", "200"] as const;
type PageSize = (typeof PAGE_SIZES)[number];
type View = "detail" | "summary";
const PREFERRED_GROUPS = [
  "campaignName",
  "campaign",
  "placementClassification",
  "date",
];

/** Metrics worth naming first when explaining what AMC hid. */
const PRIVACY_METRICS = [
  "spend",
  "product_sales",
  "purchases",
  "clicks",
  "impressions",
  "reached_users",
];

/** How much of the result Amazon kept without labels, in plain words. */
function privacyNote(p: AmcPrivacy) {
  const keys = Object.keys(p.shares).sort(
    (a, b) =>
      (PRIVACY_METRICS.indexOf(a) + 1 || 99) -
      (PRIVACY_METRICS.indexOf(b) + 1 || 99),
  );
  const shares = keys
    .slice(0, 4)
    .map((k) => `${columnLabel(k)} ${p.shares[k]}%`)
    .join("、");
  const where = p.merged
    ? "已合并为最后一行「隐私过滤合并」"
    : "保留在结果末尾，标签为空";
  return `合计值完整。Amazon 因覆盖人数过少隐去了 ${p.filtered_rows.toLocaleString()} 行的标签，${where}${
    shares ? `；这部分占${shares}` : ""
  }。`;
}

/** Report statuses that are still on their way to a result. */
const IN_FLIGHT = new Set(["QUEUED", "PROCESSING", "SUBMITTING", "WAITING", "EXECUTING"]);
/** Runs listed per report type; older runs stay reachable from 报表与数据. */
const RUNS_PER_TYPE = 3;
const PRODUCT_GROUPS: Record<string, string> = {
  SP: "Sponsored Products",
  SB: "Sponsored Brands",
  SD: "Sponsored Display",
  FF: "全流域广告活动 (Full-funnel)",
};
// Picker values that are not task ids: a report type not generated yet, or an AMC template.
const NEW = "new:";
const AMC = "amc:";

function reportParam() {
  return new URLSearchParams(location.search).get("report") || "";
}

function range(task: Task) {
  const { start_date, end_date } = task.arguments || {};
  return start_date ? `${start_date} ~ ${end_date}` : "";
}

function amcTemplate(task: Task) {
  return task.arguments?.template || "";
}

/**
 * Every report type the console can create, grouped by ad product: generated
 * types list their latest runs, the rest one "未生成" entry to create inline.
 */
function pickerOptions(done: Task[], recent: Task[], keep: string) {
  const options: SelectOption[] = [];
  const runOption = (t: Task, group: string): SelectOption => ({
    value: t.id,
    label: `${reportLabel(t.operation, t.arguments)} · ${range(t)}`,
    description: `${t.row_count.toLocaleString()} 行 · 完成于 ${stamp(t.updated_at)}`,
    group,
    prefix: <i className="dot succeeded" aria-hidden="true" />,
  });
  const addRuns = (runs: Task[], group: string) =>
    runs
      .filter((t, i) => i < RUNS_PER_TYPE || t.id === keep)
      .forEach((t) => options.push(runOption(t, group)));
  for (const [operation, name] of Object.entries(reportNames)) {
    const group = PRODUCT_GROUPS[name.slice(0, 2)];
    const runs = done.filter((t) => t.operation === operation);
    if (runs.length) {
      addRuns(runs, group);
      continue;
    }
    const last = recent.find((t) => t.operation === operation);
    const pending = last && IN_FLIGHT.has(last.status);
    options.push({
      value: NEW + operation,
      label: name,
      description: pending
        ? `生成中 · ${statuses[last.status] || last.status}`
        : last?.status === "FAILED"
          ? "未生成 · 上次失败，可重新创建"
          : "未生成 · 选中后可直接创建",
      group,
      prefix: (
        <i className={`dot ${pending ? "queued" : "all"}`} aria-hidden="true" />
      ),
    });
  }
  const amc = done.filter((t) => t.operation === AMC_OPERATION);
  for (const [template, name] of Object.entries(amcTemplateNames)) {
    const runs = amc.filter((t) => amcTemplate(t) === template);
    if (runs.length) addRuns(runs, "AMC");
    else
      options.push({
        value: AMC + template,
        label: `AMC · ${name}`,
        description: "未生成 · 在 AMC 洞察中创建",
        group: "AMC",
        prefix: <i className="dot all" aria-hidden="true" />,
      });
  }
  addRuns(
    amc.filter((t) => !amcTemplateNames[amcTemplate(t)]),
    "AMC",
  );
  return options;
}

export function ReportData() {
  const { accountId, selected, navigate, setError } = useWorkspace();
  const [reports, setReports] = useState<Task[] | null>(null);
  // Newest report tasks of any status: which types are generating or failed.
  const [recent, setRecent] = useState<Task[]>([]);
  const [taskId, setTaskId] = useState(reportParam);
  // A report created here; the picker moves to it once it succeeds.
  const [waiting, setWaiting] = useState("");
  const [size, setSize] = useState<PageSize>("200");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<RowsPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("detail");
  const [groupBy, setGroupBy] = useState<string | null>(null);
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const limit = Number(size);
  const isTask = !!taskId && !taskId.startsWith(NEW) && !taskId.startsWith(AMC);

  useEffect(() => {
    setReports(null);
    setRecent([]);
    setWaiting("");
  }, [accountId]);
  useEffect(() => {
    if (!accountId) return setReports([]);
    let live = true;
    const base = `/tasks?kind=report&account_id=${accountId}&limit=100`;
    Promise.all([
      api<Task[]>(`${base}&status=SUCCEEDED`),
      api<Task[]>(base),
    ])
      .then(([done, latest]) => {
        if (!live) return;
        setReports(done);
        setRecent(latest);
        const options = pickerOptions(done, latest, "");
        setTaskId((id) => {
          // Still looking at the type just created: show its result when ready.
          const made = done.find((t) => t.id === waiting);
          if (made && id === NEW + made.operation) return made.id;
          if (options.some((o) => o.value === id) || done.some((t) => t.id === id))
            return id;
          return done[0]?.id || options[0]?.value || "";
        });
      })
      .catch((e) => live && setError((e as Error).message));
    return () => {
      live = false;
    };
  }, [accountId, tick]);

  // Poll while a report this account asked for is still being generated.
  const generating = recent.some((t) => IN_FLIGHT.has(t.status));
  useEffect(() => {
    if (!generating) return;
    const timer = setInterval(() => setTick((n) => n + 1), 8000);
    return () => clearInterval(timer);
  }, [generating]);
  useEffect(() => {
    if (waiting && reports?.some((t) => t.id === waiting)) setWaiting("");
  }, [reports, waiting]);

  // Switching reports clears the table; paging keeps the old page (dimmed) until the next arrives.
  useEffect(() => {
    setPage(null);
    setSummary(null);
    setGroupBy(null);
  }, [taskId]);
  useEffect(() => {
    if (taskId) history.replaceState({}, "", `/data?report=${taskId}`);
    if (!isTask) return;
    let live = true;
    setLoading(true);
    api<RowsPage>(`/tasks/${taskId}/rows?offset=${offset}&limit=${limit}`)
      .then((p) => live && setPage(p))
      .catch((e) => live && setError((e as Error).message))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [taskId, offset, limit]);

  const options = useMemo(
    () => (reports ? pickerOptions(reports, recent, taskId) : []),
    [reports, recent, taskId],
  );
  const task = isTask ? reports?.find((t) => t.id === taskId) : undefined;
  const newType = taskId.startsWith(NEW) ? taskId.slice(NEW.length) : "";
  const amcType = taskId.startsWith(AMC) ? taskId.slice(AMC.length) : "";
  const columns = useMemo(() => orderColumns(page?.rows || []), [page]);
  const numeric = useMemo(
    () => numericColumns(columns, page?.rows || []),
    [columns, page],
  );
  const dimensions = columns.filter((k) => !numeric.has(k));
  const metrics = useMemo(() => columns.filter(isAdditiveColumn), [columns]);
  // null = not chosen yet; "" = grand total only.
  const group =
    groupBy ??
    (PREFERRED_GROUPS.find((k) => dimensions.includes(k)) ||
      dimensions[0] ||
      "");

  useEffect(() => {
    if (view !== "summary" || !isTask || !metrics.length) return;
    let live = true;
    setSummaryLoading(true);
    const query = new URLSearchParams({ metrics: metrics.join(",") });
    if (group) query.set("group_by", group);
    api<SummaryResult>(`/tasks/${taskId}/summary?${query}`)
      .then((r) => live && setSummary(r))
      .catch((e) => live && setError((e as Error).message))
      .finally(() => live && setSummaryLoading(false));
    return () => {
      live = false;
    };
  }, [view, taskId, group, metrics.join(",")]);
  const total = page?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <>
      <PageHeader
        title="数据表格"
        description="按报表查看已保存的数据，每页最多 200 条；完整数据可导出 JSON。"
      />
      <section className="panel">
        <PanelHeading
          title={
            task
              ? reportLabel(task.operation, task.arguments)
              : newType
                ? reportNames[newType]
                : amcType
                  ? `AMC · ${amcTemplateNames[amcType]}`
                  : "报表数据"
          }
          description={
            task
              ? `${range(task)} · ${task.row_count.toLocaleString()} 行 · 完成于 ${stamp(task.updated_at)}`
              : newType || amcType
                ? "这类报表还没有生成"
                : selected
                  ? `${selected.label} · ${selected.marketplace} 的全部报表类型`
                  : "先选择一个广告账户"
          }
        >
          {!!options.length && (
            <>
              <Select
                ariaLabel="选择报表"
                size="sm"
                className="report-picker"
                menuWidth={360}
                value={taskId}
                onChange={(id) => {
                  setTaskId(id);
                  setOffset(0);
                }}
                options={options}
              />
              {task && (
                <>
                  <Segmented
                    label="每页条数"
                    value={size}
                    options={PAGE_SIZES.map((v) => ({
                      value: v,
                      label: `${v} 条`,
                    }))}
                    onChange={(v) => {
                      setSize(v);
                      setOffset(0);
                    }}
                  />
                  <a className="secondary" href={`/api/tasks/${task.id}/export`}>
                    <DownloadSimple size={16} />
                    导出 JSON
                  </a>
                </>
              )}
            </>
          )}
        </PanelHeading>
        {reports === null ? (
          <p className="table-status">正在读取报表列表…</p>
        ) : !accountId ? (
          <Empty
            title="还没有选择广告账户"
            detail="连接并选择一个广告账户后，这里会列出它的全部报表类型。"
            action={
              <button className="primary" onClick={() => navigate("/accounts")}>
                去连接账户
                <ArrowRight size={16} />
              </button>
            }
          />
        ) : newType ? (
          <ReportCreate
            key={newType}
            operation={newType}
            last={recent.find((t) => t.operation === newType)}
            onCreated={(t) => {
              setWaiting(t.id);
              setTick((n) => n + 1);
            }}
          />
        ) : amcType ? (
          <Empty
            title={`还没有生成「${amcTemplateNames[amcType]}」`}
            detail="AMC 查询需要选择数据源和时间窗口，请在 AMC 洞察中运行，完成后会出现在这里。"
            action={
              <button className="primary" onClick={() => navigate("/amc")}>
                去 AMC 洞察
                <ArrowRight size={16} />
              </button>
            }
          />
        ) : !page ? (
          <p className="table-status">{loading ? "正在加载数据…" : ""}</p>
        ) : !page.rows.length ? (
          task?.remote_status === "NO_CAMPAIGNS" ? (
            <Empty
              title="当前站点没有全流域广告活动"
              detail="Amazon 广告活动接口在这个站点查不到全流域（Full-funnel）活动，所以没有可生成的数据。开启全流域活动后重新创建即可。"
            />
          ) : (
            <Empty
              title="这份报表没有数据"
              detail="Amazon 已完成生成，但该日期范围内没有记录；这不是仍在等待。"
            />
          )
        ) : (
          <>
            {!!task?.privacy?.filtered_rows && (
              <p className="callout info data-privacy">
                <Info size={18} />
                {privacyNote(task.privacy)}
              </p>
            )}
            <div className="data-toolbar">
              <Segmented
                label="显示方式"
                value={view}
                options={[
                  { value: "detail", label: "明细" },
                  { value: "summary", label: "汇总" },
                ]}
                onChange={setView}
              />
              {view === "summary" && (
                <Select
                  ariaLabel="汇总维度"
                  size="sm"
                  className="group-picker"
                  value={group}
                  onChange={setGroupBy}
                  options={[
                    { value: "", label: "全部合计" },
                    ...dimensions.map((k) => ({
                      value: k,
                      label: `按${columnLabel(k)}`,
                      description: k,
                    })),
                  ]}
                />
              )}
              <span className="data-toolbar-note">
                {view === "summary"
                  ? metrics.length
                    ? `汇总全部 ${total.toLocaleString()} 行${
                        summary?.group_by
                          ? `，共 ${summary.groups.length.toLocaleString()} 组`
                          : ""
                      }；点击率、ACOS 等比率按合计值重新计算`
                    : "这份报表没有可相加的指标"
                  : `共 ${total.toLocaleString()} 行`}
              </span>
            </div>
            {view === "summary" ? (
              summary && summary.group_by === (group || null) ? (
                <SummaryTable
                  key={`${taskId}:${group}`}
                  result={summary}
                  metrics={metrics}
                  limit={limit}
                  loading={summaryLoading}
                />
              ) : metrics.length ? (
                <p className="table-status">正在汇总…</p>
              ) : (
                <Empty
                  title="没有可汇总的指标"
                  detail="切换到明细查看原始数据。"
                />
              )
            ) : (
              <>
                <div
                  className="table-scroll data-table"
                  aria-busy={loading}
                  tabIndex={0}
                  aria-label="报表数据"
                >
                  <table>
                    <thead>
                      <tr>
                        <th className="row-no" scope="col">
                          #
                        </th>
                        {columns.map((k) => (
                          <th
                            key={k}
                            scope="col"
                            title={k}
                            className={
                              numeric.has(k) ? "numeric" : undefined
                            }
                          >
                            {columnLabel(k)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {page.rows.map(
                        (r: Record<string, unknown>, i: number) => (
                          <tr key={offset + i}>
                            <td className="row-no">{offset + i + 1}</td>
                            {columns.map((k) => (
                              <td
                                key={k}
                                className={
                                  numeric.has(k) ? "numeric" : undefined
                                }
                              >
                                {formatCell(k, r?.[k])}
                              </td>
                            ))}
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  label={`第 ${offset / limit + 1} / ${pages} 页 · ${offset + 1}–${Math.min(
                    offset + limit,
                    total,
                  )} / ${total.toLocaleString()} 条`}
                  canPrev={offset > 0 && !loading}
                  canNext={offset + limit < total && !loading}
                  onPrev={() => setOffset(Math.max(0, offset - limit))}
                  onNext={() => setOffset(offset + limit)}
                />
              </>
            )}
          </>
        )}
      </section>
    </>
  );
}

/** Inline creation for a report type that has no result yet. */
function ReportCreate({
  operation,
  last,
  onCreated,
}: {
  operation: string;
  last?: Task;
  onCreated: (task: Task) => void;
}) {
  const { selected, accountId, busy, action, setNotice } = useWorkspace();
  const today = todayIn(selected?.timezone || "America/Los_Angeles");
  const [startDate, setStartDate] = useState(() => shiftDays(today, -7));
  const [endDate, setEndDate] = useState(() => shiftDays(today, -1));
  const name = reportNames[operation];
  if (last && IN_FLIGHT.has(last.status))
    return (
      <Empty
        title={`「${name}」正在生成`}
        detail={`${statuses[last.status] || last.status} · ${range(last)} · 创建于 ${stamp(
          last.created_at,
        )}。完成后自动显示在这里，可以离开页面。`}
      />
    );
  const span = daySpan(startDate, endDate);
  const rangeError =
    span === null
      ? ""
      : span < 1
        ? "结束日期不能早于开始日期"
        : span > MAX_REPORT_DAYS
          ? `单个任务最多 ${MAX_REPORT_DAYS} 天，当前 ${span} 天`
          : "";
  const failed = last?.status === "FAILED";
  return (
    <div className="report-create">
      <h3>还没有生成「{name}」报表</h3>
      <p>
        选择日期后直接创建，后台会等待 Amazon 生成并保存，完成后显示在这里。
      </p>
      {failed && (
        <p className="field-note error">
          上次（{range(last)}）失败：{last.error || "Amazon 未返回原因"}
        </p>
      )}
      <form
        className="report-create-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (rangeError || !span) return;
          void action("report", async () => {
            const t = await api<Task>("/reports", "POST", {
              account_id: accountId,
              operation,
              arguments: {
                start_date: startDate,
                end_date: endDate,
                time_unit: "DAILY",
              },
              idempotency_key: crypto.randomUUID(),
            });
            setNotice(`「${name}」已入队，生成后自动显示`);
            onCreated(t);
          });
        }}
      >
        <DateRangePicker
          label="日期范围"
          start={startDate}
          end={endDate}
          today={today}
          maxDays={MAX_REPORT_DAYS}
          onChange={(start, end) => {
            setStartDate(start);
            setEndDate(end);
          }}
        />
        <button className="primary" disabled={!!busy || !span || !!rangeError}>
          <Plus size={17} />
          {busy === "report" ? "正在创建…" : "创建报表"}
        </button>
        <p className={rangeError ? "field-note error" : "field-note"}>
          {rangeError ||
            `按日汇总；日期按账户时区${selected?.timezone ? `（${selected.timezone}）` : ""}计算。`}
        </p>
      </form>
    </div>
  );
}
