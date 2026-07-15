"""Authenticated principal with resolved permissions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Principal:
    user_id: str
    display_name: str
    # The raw stored address. For a phone-only customer this is the synthetic
    # `@phone.invalid` placeholder that satisfies users.email NOT NULL — read it
    # through `services.contact.contactable_email` before showing or sending to
    # it, or use `contact_email` below.
    email: str
    user_type: str  # 'staff' | 'customer'
    permissions: frozenset[str] = field(default_factory=frozenset)
    # For farm-owner sub-admins: the single farm they may manage. None for
    # unrestricted staff and customers.
    farm_id: str | None = None
    # Verified mobile, or None. `phone_verified` is not a separate flag: an
    # unverified number is never written to users.phone_e164 in the first place,
    # so presence is proof.
    phone_e164: str | None = None

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    @property
    def contact_email(self) -> str | None:
        """The address this principal can actually receive mail at, or None."""
        from truegrit_api.services.contact import contactable_email

        return contactable_email(self.email)

    @property
    def has_verified_phone(self) -> bool:
        return self.phone_e164 is not None
