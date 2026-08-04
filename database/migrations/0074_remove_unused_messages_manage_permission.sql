-- 0074_remove_unused_messages_manage_permission: clean up dead data left by
-- 0073.
--
-- 0073's own header comment explains that conversation-management (create,
-- rename, add/remove participants) is deliberately NOT a grantable
-- permission -- it is hard-gated to the super_admin role itself via
-- auth.dependencies.require_owner, specifically so it could never be swept
-- into the "Administrator gets every permission" blanket grant. But the SQL
-- below that comment still created a 'messages.manage' permission and
-- granted it to rol_super_admin anyway, contradicting the design it
-- documented. Nothing in the application ever checks for it
-- (api.messages gates every management route with require_owner, never
-- Principal.has("messages.manage")) -- it was inert, misleading data: a
-- permission that looks like it controls something but does not, sitting
-- there for the next migration to copy the pattern from. Removing it rather
-- than leaving it in place.
PRAGMA foreign_keys = ON;

DELETE FROM role_permissions
WHERE permission_id = (SELECT id FROM permissions WHERE key = 'messages.manage');

DELETE FROM permissions WHERE key = 'messages.manage';
