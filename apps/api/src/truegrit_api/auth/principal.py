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

    def has(self, permission: str) -> bool:
        return permission in self.permissions
