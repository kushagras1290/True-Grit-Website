/**
 * Permission-aware rendering.
 *
 * Hiding a control is a UX courtesy, not authorization — the API enforces
 * every permission independently (see apps/api auth dependencies).
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo, type ReactNode } from "react";
import { Navigate } from "react-router";

import { api } from "./api";
import { EmptyState } from "../components/ui";
import { T } from "./i18n";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 5 * 60_000 });
}

export function usePermissions(): ReadonlySet<string> {
  const { data } = useMe();
  // Memoized so every consumer (Shell, PermissionGate, ...) gets the same Set
  // reference across renders instead of a new one each time -- a fresh Set
  // every render made every prop/effect that depends on it look "changed" on
  // every re-render, for no reason tied to the actual permission list.
  return useMemo(() => new Set(data?.permissions ?? []), [data?.permissions]);
}

export function PermissionGate({
  permission,
  children,
  fallback = null,
}: {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const permissions = usePermissions();
  return permissions.has(permission) ? children : fallback;
}

export function RequireSuperAdmin({ children }: { children: ReactNode }) {
  const { data: me, isLoading, isError } = useMe();
  if (isLoading)
    return (
      <p className="text-sm text-ink-muted">
        <T>Checking access…</T>
      </p>
    );
  if (isError) return <Navigate to="/login" replace />;
  if (!me?.isSuperAdmin) {
    return (
      <EmptyState
        title="Super administrator access required"
        hint="This page contains sensitive application diagnostics."
      />
    );
  }
  return children;
}
