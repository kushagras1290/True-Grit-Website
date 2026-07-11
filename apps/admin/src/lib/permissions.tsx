/**
 * Permission-aware rendering.
 *
 * Hiding a control is a UX courtesy, not authorization — the API enforces
 * every permission independently (see apps/api auth dependencies).
 */

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { api } from "./api";

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: 5 * 60_000 });
}

export function usePermissions(): ReadonlySet<string> {
  const { data } = useMe();
  return new Set(data?.permissions ?? []);
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
