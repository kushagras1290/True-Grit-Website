/** Restrained admin primitives — one button hierarchy, quiet surfaces, no card zoo. */

import { cn } from "@truegrit/ui";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

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

export function Td({ children, className }: { children?: ReactNode; className?: string }) {
  return <td className={cn("px-3 py-3 align-middle text-ink", className)}>{children}</td>;
}
