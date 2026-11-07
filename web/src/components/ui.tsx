import { useEffect, useEffectEvent, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import {
  CaretLeft,
  CaretRight,
  Database,
  GithubLogo,
  TiktokLogo,
  WechatLogo,
  X,
} from "@phosphor-icons/react";
import { statuses } from "../lib/constants";

export function Status({ value, label }: { value: string; label?: string }) {
  return (
    <span className={`status ${value.toLowerCase()}`}>
      {label || statuses[value] || (value === "OK" ? "成功" : value)}
    </span>
  );
}

export function Empty({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty" role="status">
      <span className="empty-icon">
        <Database size={26} weight="duotone" />
      </span>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function PanelHeading({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="panel-heading">
      <div>
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {children && <div className="panel-tools">{children}</div>}
    </div>
  );
}

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((o) => (
        <button
          type="button"
          key={o.value}
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Pagination({
  label,
  canPrev,
  canNext,
  onPrev,
  onNext,
}: {
  label: ReactNode;
  canPrev: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
}) {
  if (!canPrev && !canNext) return null;
  return (
    <div className="pagination">
      <span>{label}</span>
      <button type="button" disabled={!canPrev} onClick={onPrev}>
        <CaretLeft size={14} />
        上一页
      </button>
      <button type="button" disabled={!canNext} onClick={onNext}>
        下一页
        <CaretRight size={14} />
      </button>
    </div>
  );
}

export function Modal({
  title,
  children,
  close,
  wide,
  narrow,
}: {
  title: string;
  children: ReactNode;
  close: () => void;
  wide?: boolean;
  narrow?: boolean;
}) {
  const dialog = useRef<HTMLElement>(null);
  const pressedBackdrop = useRef(false);
  const onClose = useEffectEvent(close);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const nodes = Array.from(
          dialog.current?.querySelectorAll<HTMLElement>(
            "button:not(:disabled), input:not(:disabled):not([type=hidden]), textarea:not(:disabled), select:not(:disabled), [tabindex='0'], a[href], summary",
          ) || [],
        ).filter((node) => node.getClientRects().length > 0);
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (!first) {
          e.preventDefault();
          return;
        }
        if (
          e.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === dialog.current)
        ) {
          e.preventDefault();
          last.focus();
        } else if (
          !e.shiftKey &&
          (document.activeElement === last ||
            document.activeElement === dialog.current)
        ) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = previousOverflow;
      previous?.focus();
    };
  }, []);
  // Portalled so a transformed ancestor (e.g. the page entrance animation)
  // can't become the containing block and shrink the fixed backdrop.
  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(e) =>
        (pressedBackdrop.current = e.target === e.currentTarget)
      }
      onClick={(e) => {
        // Portals still bubble through the React tree; keep clicks local.
        e.stopPropagation();
        // Ignore drags that start inside the dialog (e.g. selecting text).
        if (pressedBackdrop.current && e.target === e.currentTarget) close();
      }}
    >
      <section
        className={`modal${wide ? " wide" : ""}${narrow ? " narrow" : ""}`}
        ref={dialog}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={close}>
            <X size={20} />
          </button>
        </header>
        {children}
      </section>
    </div>,
    document.body,
  );
}

/** In-app replacement for window.confirm(), for irreversible actions. */
export function ConfirmDialog({
  title,
  children,
  confirmLabel,
  busy,
  onConfirm,
  close,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  close: () => void;
}) {
  return (
    <Modal title={title} close={close} narrow>
      <div className="confirm-body">{children}</div>
      <div className="modal-actions">
        <button type="button" className="secondary" onClick={close}>
          取消
        </button>
        <button
          type="button"
          className="primary destructive"
          disabled={busy}
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

/** Author line shown at the bottom of every screen. */
export function AuthorCredit({ className = "" }: { className?: string }) {
  return (
    <p className={`author-credit ${className}`.trim()}>
      <a
        href="https://github.com/DongLiyaaa"
        target="_blank"
        rel="noopener noreferrer"
      >
        <GithubLogo size={14} weight="fill" aria-hidden="true" />
        GitHub：DongLiyaaa
      </a>
      <span>
        <WechatLogo size={14} weight="fill" aria-hidden="true" />
        微信公众号：冬离鸭冬离
      </span>
      <span>
        <TiktokLogo size={14} weight="fill" aria-hidden="true" />
        抖音号：冬离鸭冬离
      </span>
    </p>
  );
}
