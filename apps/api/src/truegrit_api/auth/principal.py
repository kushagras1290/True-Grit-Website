"""Authenticated principal with resolved permissions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    user_id: str
    display_name: str
    email: str
    user_type: str  # 'staff' | 'customer'
    permissions: frozenset[str] = field(default_factory=frozenset)
    # For farm-owner sub-admins: the single farm they may manage. None for
    # unrestricted staff and customers.
    farm_id: str | None = None

    def has(self, permission: str) -> bool:
        return permission in self.permissions
