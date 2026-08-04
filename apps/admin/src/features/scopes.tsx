import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  Button,
  ConfirmDialog,
  DataTableShell,
  EmptyState,
  Field,
  Input,
  LoadingRows,
  Modal,
  PageHeader,
  StatusPill,
  Td,
  Textarea,
  Th,
} from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type AdminPermission, type AdminRole } from "../lib/api";
import { T } from "../lib/i18n";

const GROUP_LABELS: Record<string, string> = {
  analytics: "Analytics",
  articles: "Blog",
  audit: "Audit",
  bundles: "Bundles",
  categories: "Categories",
  customers: "Customers",
  discussions: "Community",
  inventory: "Inventory",
  media: "Media",
  orders: "Orders",
  pages: "CMS pages",
  products: "Products",
  promotions: "Coupons & Promotions",
  recipes: "Recipes",
  reports: "Owner reports",
  returns: "Returns",
  reviews: "Reviews",
  settings: "Settings",
  submissions: "Submissions",
  subscriptions: "Subscriptions",
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

export function CreateRoleModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (roleId: string) => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.createRole({ name: name.trim(), description: description.trim(), permissionIds: [] }),
    onSuccess: async (role) => {
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast.success(`Role "${role.name}" created — choose its permissions below.`);
      onCreated(role.id);
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not create the role."),
  });

  return (
    <Modal title="Add role" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label="Name" htmlFor="role-name">
          <Input
            id="role-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Accounts"
            required
            minLength={3}
          />
        </Field>
        <Field label="Description" htmlFor="role-description">
          <Textarea
            id="role-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What this role is for"
          />
        </Field>
        <p className="text-xs text-ink-muted">
          <T>Starts with no permissions — you'll pick what it can do right after creating it.</T>
        </p>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            <T>Cancel</T>
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={mutation.isPending || name.trim().length < 3}
          >
            {mutation.isPending ? <T>{"Creating..."}</T> : <T>{"Create role"}</T>}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function RenameRoleModal({ role, onClose }: { role: AdminRole; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState(role.name);
  const [description, setDescription] = useState(role.description);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateRole(role.id, { name: name.trim(), description: description.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      toast.success("Role updated.");
      onClose();
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not update the role."),
  });

  return (
    <Modal title="Edit role" onClose={onClose}>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label="Name" htmlFor="edit-role-name">
          <Input
            id="edit-role-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            minLength={3}
          />
        </Field>
        <Field label="Description" htmlFor="edit-role-description">
          <Textarea
            id="edit-role-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            <T>Cancel</T>
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={mutation.isPending || name.trim().length < 3}
          >
            {mutation.isPending ? <T>{"Saving..."}</T> : <T>{"Save"}</T>}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/** Compact add/rename/delete surface for roles, reused by both Scope
 * Management and the Users & Roles page so role upkeep doesn't require a
 * detour through the permission-checkbox editor to do it. */
export function ManageRolesModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
  const [creating, setCreating] = useState(false);
  const [renamingRole, setRenamingRole] = useState<AdminRole | null>(null);
  const [deletingRole, setDeletingRole] = useState<AdminRole | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (roleId: string) => api.deleteRole(roleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      setDeletingRole(null);
      toast.success("Role deleted.");
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "Could not delete the role.");
      setDeletingRole(null);
    },
  });

  return (
    <Modal title="Manage roles" onClose={onClose}>
      {creating ? (
        <CreateRoleModal onClose={() => setCreating(false)} onCreated={() => setCreating(false)} />
      ) : null}
      {renamingRole ? (
        <RenameRoleModal role={renamingRole} onClose={() => setRenamingRole(null)} />
      ) : null}
      {deletingRole ? (
        <ConfirmDialog
          title="Delete role"
          description={`"${deletingRole.name}" will be permanently removed. This only works while no user holds it.`}
          confirmLabel="Delete role"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setDeletingRole(null)}
          onConfirm={() => deleteMutation.mutate(deletingRole.id)}
        />
      ) : null}

      <div className="mb-3 flex justify-end">
        <Button type="button" variant="primary" onClick={() => setCreating(true)}>
          <T>Add role</T>
        </Button>
      </div>
      <ul className="max-h-96 divide-y divide-line overflow-auto rounded-md border border-line">
        {(roles.data ?? []).map((role) => (
          <li key={role.id} className="flex items-center gap-3 px-3 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{role.name}</p>
              <p className="truncate text-xs text-ink-muted">
                {role.permissionIds.length} permission{role.permissionIds.length === 1 ? "" : "s"}
                {role.description ? ` · ${role.description}` : ""}
              </p>
            </div>
            {role.isSystem ? (
              <StatusPill status="locked" />
            ) : (
              <div className="flex shrink-0 gap-2">
                <Button type="button" variant="secondary" onClick={() => setRenamingRole(role)}>
                  <T>Edit</T>
                </Button>
                <Button type="button" variant="destructive" onClick={() => setDeletingRole(role)}>
                  <T>Delete</T>
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Modal>
  );
}

export function ScopeManagementPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const roles = useQuery({ queryKey: ["roles"], queryFn: api.roles });
  const permissions = useQuery({ queryKey: ["permissions"], queryFn: api.permissions });
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [draft, setDraft] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);

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

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteRole(selectedRole?.id ?? ""),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["roles"] });
      setSelectedRoleId(null);
      setDeleting(false);
      toast.success("Role deleted.");
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "Could not delete the role.");
      setDeleting(false);
    },
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
          <>
            <Button variant="secondary" onClick={() => setCreating(true)}>
              <T>Add role</T>
            </Button>
            <Button
              variant="primary"
              onClick={() => mutation.mutate()}
              disabled={!selectedRole || selectedRole.locked || mutation.isPending}
            >
              {mutation.isPending ? <T>{"Saving..."}</T> : <T>{"Save scope"}</T>}
            </Button>
          </>
        }
      />

      {creating ? (
        <CreateRoleModal
          onClose={() => setCreating(false)}
          onCreated={(roleId) => {
            setSelectedRoleId(roleId);
            setCreating(false);
          }}
        />
      ) : null}
      {renaming && selectedRole ? (
        <RenameRoleModal role={selectedRole} onClose={() => setRenaming(false)} />
      ) : null}
      {deleting && selectedRole ? (
        <ConfirmDialog
          title="Delete role"
          description={`"${selectedRole.name}" will be permanently removed. This only works while no user holds it.`}
          confirmLabel="Delete role"
          pendingLabel="Deleting..."
          isPending={deleteMutation.isPending}
          onCancel={() => setDeleting(false)}
          onConfirm={() => deleteMutation.mutate()}
        />
      ) : null}

      {roles.isError || permissions.isError ? (
        <EmptyState title="Scopes unavailable" hint="Only the owner can manage role scopes." />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
          <DataTableShell>
            <thead className="bg-canvas">
              <tr>
                <Th>
                  <T>Role</T>
                </Th>
                <Th>
                  <T>Permissions</T>
                </Th>
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
                  <div className="flex items-center gap-3">
                    {!selectedRole.isSystem ? (
                      <div className="flex gap-2">
                        <Button variant="secondary" onClick={() => setRenaming(true)}>
                          <T>Edit</T>
                        </Button>
                        <Button variant="destructive" onClick={() => setDeleting(true)}>
                          <T>Delete</T>
                        </Button>
                      </div>
                    ) : null}
                    <p className="text-sm text-ink-muted">{draft.length} selected</p>
                  </div>
                </div>
                <div className="max-h-[calc(100vh-260px)] overflow-auto px-5 py-4">
                  {permissions.isLoading ? (
                    <p className="text-sm text-ink-muted">
                      <T>Loading permissions...</T>
                    </p>
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
