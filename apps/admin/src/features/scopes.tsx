import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  Button,
  DataTableShell,
  EmptyState,
  LoadingRows,
  PageHeader,
  StatusPill,
  Td,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type AdminPermission, type AdminRole } from "../lib/api";

const GROUP_LABELS: Record<string, string> = {
  audit: "Audit",
  categories: "Categories",
  customers: "Customers",
  inventory: "Inventory",
  media: "Media",
  orders: "Orders",
  pages: "CMS pages",
  products: "Products",
  settings: "Settings",
  users: "Users and roles",
};

const FARM_OWNER_ALLOWED_GROUPS = new Set(["products", "inventory", "media"]);

function permissionGroup(permission: AdminPermission) {
  return permission.key.split(".", 1)[0] || "other";
}

function groupPermissions(permissions: AdminPermission[]) {
  const groups = new Map<string, AdminPermission[]>();
  for (const permission of permissions) {
    const group = permissionGroup(permission);
    groups.set(group, [...(groups.get(group) ?? []), permission]);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

function isBlockedForRole(role: AdminRole, permission: AdminPermission) {
  return role.key === "farm_owner" && !FARM_OWNER_ALLOWED_GROUPS.has(permissionGroup(permission));
}

export function ScopeManagementPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
  const permissions = useQuery({ queryKey: ["permissions"], queryFn: api.permissions });
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [draft, setDraft] = useState<string[]>([]);

  const roleList = roles.data ?? [];
  const selectedRole = roleList.find((role) => role.id === selectedRoleId) ?? roleList[0] ?? null;
  const permissionGroups = useMemo(
    () => groupPermissions(permissions.data ?? []),
    [permissions.data],
  );

  useEffect(() => {
    const firstRoleId = roleList[0]?.id;
    if (!selectedRoleId && firstRoleId) {
      setSelectedRoleId(firstRoleId);
    }
  }, [roleList, selectedRoleId]);

  useEffect(() => {
    setDraft(selectedRole?.permissionIds ?? []);
  }, [selectedRole?.id, selectedRole?.permissionIds]);

  const mutation = useMutation({
    mutationFn: () => api.setRolePermissions(selectedRole?.id ?? "", draft),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast.success("Role scope updated. Affected users will sign in again.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update role scope."),
  });

  function toggle(permission: AdminPermission) {
    setDraft((current) =>
      current.includes(permission.id)
        ? current.filter((permissionId) => permissionId !== permission.id)
        : [...current, permission.id],
    );
  }

  return (
    <div>
      <PageHeader
        title="Scope Management"
        description="Control what each role can view, create, edit, publish or manage."
        actions={
          <Button
            variant="primary"
            onClick={() => mutation.mutate()}
            disabled={!selectedRole || selectedRole.locked || mutation.isPending}
          >
            {mutation.isPending ? "Saving..." : "Save scope"}
          </Button>
        }
      />

      {roles.isError || permissions.isError ? (
        <EmptyState
          title="Scopes unavailable"
          hint="Only the owner can manage role scopes."
        />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <DataTableShell>
            <thead className="bg-canvas">
              <tr>
                <Th>Role</Th>
                <Th>Permissions</Th>
              </tr>
            </thead>
            {roles.isLoading ? (
              <LoadingRows columns={2} />
            ) : (
              <tbody>
                {roleList.map((role) => (
                  <tr
                    key={role.id}
                    className={
                      role.id === selectedRole?.id
                        ? "border-t border-line bg-subtle/60"
                        : "border-t border-line"
                    }
                  >
                    <Td>
                      <button
                        type="button"
                        className="block w-full text-left"
                        onClick={() => setSelectedRoleId(role.id)}
                      >
                        <span className="block font-medium text-ink">{role.name}</span>
                        <span className="block text-xs text-ink-muted">{role.description}</span>
                      </button>
                    </Td>
                    <Td>
                      <span className="text-sm text-ink-muted">{role.permissionIds.length}</span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            )}
          </DataTableShell>

          <section className="rounded-md border border-line bg-surface">
            {selectedRole ? (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="font-display text-lg text-ink">{selectedRole.name}</h2>
                      {selectedRole.locked ? <StatusPill status="locked" /> : null}
                    </div>
                    <p className="mt-1 text-sm text-ink-muted">{selectedRole.description}</p>
                  </div>
                  <p className="text-sm text-ink-muted">{draft.length} selected</p>
                </div>
                <div className="max-h-[calc(100vh-260px)] overflow-auto px-5 py-4">
                  {permissions.isLoading ? (
                    <p className="text-sm text-ink-muted">Loading permissions...</p>
                  ) : permissionGroups.length === 0 ? (
                    <EmptyState title="No permissions" hint="Permissions have not been seeded." />
                  ) : (
                    <div className="space-y-5">
                      {permissionGroups.map(([group, items]) => (
                        <div key={group}>
                          <h3 className="mb-2 text-xs font-semibold tracking-[0.14em] text-ink-muted uppercase">
                            {GROUP_LABELS[group] ?? group}
                          </h3>
                          <div className="grid gap-2 md:grid-cols-2">
                            {items.map((permission) => {
                              const blocked = isBlockedForRole(selectedRole, permission);
                              return (
                                <label
                                  key={permission.id}
                                  className={
                                    blocked || selectedRole.locked
                                      ? "rounded-md border border-line bg-canvas px-3 py-2 opacity-60"
                                      : "rounded-md border border-line bg-surface px-3 py-2"
                                  }
                                >
                                  <span className="flex items-start gap-2">
                                    <input
                                      type="checkbox"
                                      className="mt-1"
                                      checked={draft.includes(permission.id)}
                                      disabled={selectedRole.locked || blocked}
                                      onChange={() => toggle(permission)}
                                    />
                                    <span>
                                      <span className="block text-sm font-medium text-ink">
                                        {permission.key}
                                      </span>
                                      <span className="block text-xs leading-5 text-ink-muted">
                                        {permission.description}
                                      </span>
                                    </span>
                                  </span>
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : (
              <EmptyState title="No roles" hint="Roles have not been seeded yet." />
            )}
          </section>
        </div>
      )}
    </div>
  );
}
