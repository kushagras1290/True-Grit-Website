/** Restrained admin primitives — one button hierarchy, quiet surfaces, no card zoo. */

import { cn } from "@truegrit/ui";
import { AlertTriangle, X } from "lucide-react";
import { useEffect, useState } from "react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TdHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

export function Button({
  variant = "secondary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "tertiary" | "destructive";
}) {
  const styles = {
    primary: "bg-brand text-ink-inverse hover:opacity-90",
    secondary: "border border-line-strong bg-surface text-ink hover:bg-subtle/50",
    tertiary: "text-brand underline-offset-4 hover:underline",
    destructive: "bg-danger text-ink-inverse hover:opacity-90",
  } as const;
  return (
    <button
      className={cn(
        "inline-flex min-h-9 items-center justify-center gap-2 rounded-sm px-3.5 text-sm font-medium",
        "transition-opacity duration-150 disabled:cursor-not-allowed disabled:opacity-50",
        styles[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "min-h-9 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink",
        "placeholder:text-ink-muted",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-20 w-full rounded-sm border border-line-strong bg-surface px-3 py-2 text-sm text-ink",
        "placeholder:text-ink-muted",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "min-h-9 w-full rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink",
        className,
      )}
      {...props}
    />
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-ink/40 px-4 py-10"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="w-full max-w-lg rounded-md border border-line bg-surface shadow-overlay"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="font-display text-lg text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 items-center justify-center text-ink-muted hover:text-ink"
          >
            <X size={17} />
          </button>
        </div>
        <div className="px-5 py-5">{children}</div>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  pendingLabel,
  isPending = false,
  onCancel,
  onConfirm,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  pendingLabel?: string;
  isPending?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal title={title} onClose={() => (isPending ? undefined : onCancel())}>
      <div className="flex gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-sm bg-danger/10 text-danger">
          <AlertTriangle size={19} aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-6 text-ink-muted">{description}</p>
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onCancel} disabled={isPending}>
              Cancel
            </Button>
            <Button type="button" variant="destructive" onClick={onConfirm} disabled={isPending}>
              {isPending ? (pendingLabel ?? "Working...") : confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

export function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function ImagePreview({
  src,
  alt,
  label,
  className,
}: {
  src: string;
  alt?: string;
  label: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const initial = label.trim().charAt(0).toUpperCase() || "?";
  const apiUrl = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/+$/, "");
  const resolvedSrc = src.startsWith("/media/") && apiUrl ? `${apiUrl}${src}` : src;

  useEffect(() => {
    setFailed(false);
  }, [src]);

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md",
        "border border-line bg-canvas text-sm font-semibold text-ink-muted",
        className ?? "h-28 w-28",
      )}
    >
      {resolvedSrc && !failed ? (
        <img
          src={resolvedSrc}
          alt={alt || label}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        initial
      )}
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  published: "bg-subtle text-brand",
  active: "bg-subtle text-brand",
  paid: "bg-subtle text-brand",
  confirmed: "bg-subtle text-brand",
  draft: "bg-canvas text-ink-muted border border-line",
  in_review: "bg-warning/10 text-warning",
  pending: "bg-warning/10 text-warning",
  pending_payment: "bg-warning/10 text-warning",
  processing: "bg-warning/10 text-warning",
  low_stock: "bg-warning/10 text-warning",
  archived: "bg-canvas text-ink-muted border border-line",
  disabled: "bg-danger/10 text-danger",
  cancelled: "bg-danger/10 text-danger",
  out_of_stock: "bg-danger/10 text-danger",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        STATUS_STYLES[status] ?? "bg-canvas text-ink-muted border border-line",
      )}
    >
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-2xl text-ink">{title}</h1>
        {description ? <p className="mt-1 text-sm text-ink-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex gap-2">{actions}</div> : null}
    </header>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-md border border-dashed border-line-strong bg-surface px-6 py-12 text-center">
      <p className="font-medium text-ink">{title}</p>
      {hint ? <p className="mt-1 text-sm text-ink-muted">{hint}</p> : null}
    </div>
  );
}

export function LoadingRows({ columns }: { columns: number }) {
  return (
    <tbody aria-busy="true">
      {Array.from({ length: 5 }, (_, rowIndex) => (
        <tr key={rowIndex} className="border-t border-line">
          {Array.from({ length: columns }, (_, cellIndex) => (
            <td key={cellIndex} className="px-3 py-3">
              <div className="h-3.5 animate-pulse rounded-sm bg-subtle" />
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  );
}

export function DataTableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-md border border-line bg-surface shadow-card">
      <table className="w-full min-w-[640px] border-collapse text-left text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, className }: { children?: ReactNode; className?: string }) {
  return (
    <th
      scope="col"
      className={cn(
        "px-3 py-2.5 text-xs font-semibold tracking-wide text-ink-muted uppercase",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({ children, className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("px-3 py-3 align-middle text-ink", className)} {...props}>
      {children}
    </td>
  );
}
