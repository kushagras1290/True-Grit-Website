"""Admin list queries — server pagination, never the whole catalogue."""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

MAX_PAGE_SIZE = 100
DEFAULT_SEARCH_LIMIT = 5

# Escaping user-typed '%'/'_' before they reach LIKE keeps a literal percent
# sign or underscore in a search term (e.g. a discount code "50%") from being
# reinterpreted as a wildcard. '!' is the escape character because it has no
# meaning of its own in SQL LIKE patterns.
_LIKE_ESCAPE_CHAR = "!"
_LIKE_ESCAPE_TRANSLATION = str.maketrans(
    {
        _LIKE_ESCAPE_CHAR: _LIKE_ESCAPE_CHAR * 2,
        "%": f"{_LIKE_ESCAPE_CHAR}%",
        "_": f"{_LIKE_ESCAPE_CHAR}_",
    }
)


def _like_term(raw: str) -> str:
    return f"%{raw.translate(_LIKE_ESCAPE_TRANSLATION)}%"


class AdminRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_products(
        self,
        limit: int = 50,
        offset: int = 0,
        farm_id: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), MAX_PAGE_SIZE)
        like = f"%{search}%" if search else None
        return await self._db.fetch_all(
            """
            SELECT
              p.id, p.name, p.slug, p.status,
              COALESCE(
                '/media/' || m.object_key,
                NULLIF(p.image_url, ''),
                (
                  SELECT c.hero_image_url
                  FROM product_categories pc2
                  JOIN categories c ON c.id = pc2.category_id
                  WHERE pc2.product_id = p.id AND NULLIF(c.hero_image_url, '') IS NOT NULL
                  ORDER BY pc2.is_primary DESC, pc2.sort_order, c.sort_order
                  LIMIT 1
                )
              ) AS image_url,
              NULLIF(p.image_alt, '') AS image_alt, p.updated_at,
              u.display_name AS updated_by,
              COALESCE(f.name, b.name, '') AS farm_name,
              (SELECT v.sku FROM product_variants v
                WHERE v.product_id = p.id ORDER BY v.sort_order LIMIT 1) AS sku,
              (SELECT GROUP_CONCAT(c.name, ', ') FROM product_categories pc
                JOIN categories c ON c.id = pc.category_id
                WHERE pc.product_id = p.id) AS categories,
              (SELECT MIN(vp.list_amount_minor) FROM product_variants v
                JOIN variant_prices vp ON vp.variant_id = v.id AND vp.status = 'active'
                WHERE v.product_id = p.id) AS min_price_minor,
              (SELECT MAX(vp.list_amount_minor) FROM product_variants v
                JOIN variant_prices vp ON vp.variant_id = v.id AND vp.status = 'active'
                WHERE v.product_id = p.id) AS max_price_minor,
              (SELECT COALESCE(SUM(il.on_hand - il.reserved), 0) FROM product_variants v
                JOIN inventory_levels il ON il.variant_id = v.id
                WHERE v.product_id = p.id) AS available_stock
            FROM products p
            LEFT JOIN farms f ON f.id = p.farm_id
            LEFT JOIN brands b ON b.id = p.brand_id
            LEFT JOIN users u ON u.id = p.updated_by
            LEFT JOIN media_assets m ON m.id = p.primary_media_id
            WHERE p.archived_at IS NULL
              AND (? IS NULL OR p.farm_id = ?)
              AND (
                ? IS NULL
                OR p.name LIKE ?
                OR p.slug LIKE ?
                OR EXISTS (
                  SELECT 1 FROM product_variants pv
                  WHERE pv.product_id = p.id AND pv.sku LIKE ?
                )
              )
            ORDER BY p.updated_at DESC, p.name
            LIMIT ? OFFSET ?
            """,
            (farm_id, farm_id, like, like, like, like, limit, max(offset, 0)),
        )

    async def list_categories(
        self, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), MAX_PAGE_SIZE)
        like = f"%{search}%" if search else None
        return await self._db.fetch_all(
            """
            SELECT
              c.id, c.name, c.slug, c.visibility, c.status, c.updated_at,
              c.hero_image_url, c.hero_image_alt,
              parent.name AS parent_name,
              (SELECT COUNT(*) FROM product_categories pc WHERE pc.category_id = c.id)
                AS product_count
            FROM categories c
            LEFT JOIN categories parent ON parent.id = c.parent_id
            WHERE c.archived_at IS NULL
              AND (? IS NULL OR c.name LIKE ? OR c.slug LIKE ?)
            ORDER BY c.sort_order, c.name
            LIMIT ? OFFSET ?
            """,
            (like, like, like, limit, max(offset, 0)),
        )

    async def list_inventory(
        self,
        limit: int = 100,
        offset: int = 0,
        farm_id: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 200)
        search_clause = ""
        params: list[Any] = [farm_id, farm_id]
        if search:
            search_clause = "AND (p.name LIKE ? OR v.sku LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        params.extend([limit, max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT
              il.variant_id, p.id AS product_id, p.status AS product_status,
              p.name AS product_name, v.name AS variant_name, v.sku,
              loc.name AS location_name, il.on_hand, il.reserved,
              il.reorder_threshold, il.updated_at
            FROM inventory_levels il
            JOIN product_variants v ON v.id = il.variant_id
            JOIN products p ON p.id = v.product_id
            JOIN inventory_locations loc ON loc.id = il.location_id
            WHERE (? IS NULL OR p.farm_id = ?) AND p.archived_at IS NULL
            {search_clause}
            ORDER BY (il.on_hand - il.reserved - il.reorder_threshold) ASC, p.name
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def get_product_detail(self, product_id: str) -> dict[str, Any] | None:
        product = await self._db.fetch_one(
            """
            SELECT p.id, p.name, p.slug, p.short_description, p.product_type, p.status,
                   p.seo_title, p.seo_description, p.farm_id,
                   COALESCE(
                     '/media/' || m.object_key,
                     NULLIF(p.image_url, ''),
                     (
                       SELECT c.hero_image_url
                       FROM product_categories pc
                       JOIN categories c ON c.id = pc.category_id
                       WHERE pc.product_id = p.id AND NULLIF(c.hero_image_url, '') IS NOT NULL
                       ORDER BY pc.is_primary DESC, pc.sort_order, c.sort_order
                       LIMIT 1
                     )
                   ) AS image_url,
                   NULLIF(p.image_alt, '') AS image_alt,
                   p.updated_at,
                   p.release_scope,
                   p.return_eligible,
                   COALESCE(f.name, b.name, '') AS farm_name
            FROM products p
            LEFT JOIN farms f ON f.id = p.farm_id
            LEFT JOIN brands b ON b.id = p.brand_id
            LEFT JOIN media_assets m ON m.id = p.primary_media_id
            WHERE p.id = ? AND p.archived_at IS NULL
            """,
            (product_id,),
        )
        if product is None:
            return None
        release_rows = await self._db.fetch_all(
            "SELECT country_code FROM product_release_countries WHERE product_id = ?"
            " ORDER BY country_code",
            (product_id,),
        )
        product["release_countries"] = [row["country_code"] for row in release_rows]
        category_rows = await self._db.fetch_all(
            "SELECT category_id FROM product_categories WHERE product_id = ? ORDER BY sort_order",
            (product_id,)
        )
        product["category_ids"] = [row["category_id"] for row in category_rows]
        product["linked_products"] = await self._db.fetch_all(
            """
            SELECT p.id, p.name, p.slug, p.status
            FROM product_links pl
            JOIN products p ON p.id = pl.linked_product_id
            WHERE pl.product_id = ? AND p.archived_at IS NULL
            ORDER BY pl.sort_order
            """,
            (product_id,),
        )
        variants = await self._db.fetch_all(
            """
            SELECT v.id, v.name, v.sku, v.status,
              (SELECT vp.list_amount_minor FROM variant_prices vp
                WHERE vp.variant_id = v.id AND vp.status = 'active'
                ORDER BY vp.starts_at DESC LIMIT 1) AS list_minor,
              (SELECT vp.sale_amount_minor FROM variant_prices vp
                WHERE vp.variant_id = v.id AND vp.status = 'active'
                ORDER BY vp.starts_at DESC LIMIT 1) AS sale_minor,
              (SELECT COALESCE(SUM(il.on_hand - il.reserved), 0) FROM inventory_levels il
                WHERE il.variant_id = v.id) AS available
            FROM product_variants v
            WHERE v.product_id = ?
            ORDER BY v.sort_order, v.name
            """,
            (product_id,),
        )
        product["variants"] = variants
        return product

    async def get_category_detail(self, category_id: str) -> dict[str, Any] | None:
        category = await self._db.fetch_one(
            """
            SELECT id, name, slug, short_description, hero_eyebrow, hero_title, hero_description,
                   season_label, theme_key, visibility, status, seo_title, seo_description,
                   hero_image_url, hero_image_alt, product_assignment_mode, updated_at,
                   release_scope
            FROM categories WHERE id = ? AND archived_at IS NULL
            """,
            (category_id,),
        )
        if category is None:
            return None
        release_rows = await self._db.fetch_all(
            "SELECT country_code FROM category_release_countries WHERE category_id = ?"
            " ORDER BY country_code",
            (category_id,),
        )
        category["release_countries"] = [row["country_code"] for row in release_rows]
        return category

    async def list_users(
        self, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), MAX_PAGE_SIZE)
        where_clause = "WHERE u.user_type = 'staff' AND u.deleted_at IS NULL"
        params: list[Any] = []
        if search:
            where_clause += " AND (u.display_name LIKE ? OR u.email LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        params.extend([limit, max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT u.id, u.display_name, u.email, u.status, u.last_sign_in_at,
              (SELECT GROUP_CONCAT(r.name, ', ') FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id WHERE ur.user_id = u.id) AS role_names,
              (SELECT GROUP_CONCAT(ur.role_id, ',') FROM user_roles ur
                WHERE ur.user_id = u.id) AS role_ids
            FROM users u
            {where_clause}
            ORDER BY u.display_name
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def list_roles(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT id, key, name, description, is_system,
              (SELECT GROUP_CONCAT(permission_id, ',') FROM (
                SELECT rp.permission_id
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = roles.id
                ORDER BY p.key
              )) AS permission_ids,
              (SELECT GROUP_CONCAT(key, ',') FROM (
                SELECT p.key
                FROM role_permissions rp
                JOIN permissions p ON p.id = rp.permission_id
                WHERE rp.role_id = roles.id
                ORDER BY p.key
              )) AS permission_keys
            FROM roles
            ORDER BY
              CASE key
                WHEN 'super_admin' THEN 0
                WHEN 'admin' THEN 1
                WHEN 'manager' THEN 2
                WHEN 'inventory' THEN 3
                WHEN 'farm_owner' THEN 4
                ELSE 10
              END,
              name
            """
        )

    async def list_permissions(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT id, key, description
            FROM permissions
            ORDER BY key
            """
        )

    async def list_orders(
        self, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), MAX_PAGE_SIZE)
        where_clause = ""
        params: list[Any] = []
        if search:
            where_clause = "WHERE public_reference LIKE ? OR customer_email LIKE ?"
            params.extend([f"%{search}%", f"%{search}%"])
        params.extend([limit, max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT id, public_reference, customer_email, currency_code, total_minor,
                   order_status, payment_status, fulfilment_status, placed_at, created_at
            FROM orders
            {where_clause}
            ORDER BY COALESCE(placed_at, created_at) DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def get_order_detail(self, order_id: str) -> dict[str, Any] | None:
        order = await self._db.fetch_one(
            """
            SELECT id, public_reference, customer_email, customer_phone_e164, currency_code,
                   subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor,
                   order_status, payment_status, fulfilment_status, delivery_status,
                   delivery_address_json, placed_at, created_at
            FROM orders WHERE id = ?
            """,
            (order_id,),
        )
        if order is None:
            return None
        order["items"] = await self._db.fetch_all(
            """
            SELECT id, product_name, variant_name, sku, quantity,
                   unit_effective_amount_minor, line_total_minor
            FROM order_items WHERE order_id = ? ORDER BY product_name
            """,
            (order_id,),
        )
        payment = await self._db.fetch_one(
            """
            SELECT id, provider, amount_minor, currency_code, status,
                   COALESCE(
                     (SELECT SUM(amount_minor) FROM payment_events
                       WHERE payment_id = payments.id AND event_type = 'refund'),
                     0
                   ) AS refunded_minor
            FROM payments WHERE order_id = ? ORDER BY created_at DESC LIMIT 1
            """,
            (order_id,),
        )
        order["payment"] = payment
        return order

    async def search_products(
        self, term: str, *, limit: int = DEFAULT_SEARCH_LIMIT, farm_id: str | None = None
    ) -> list[dict[str, Any]]:
        pattern = _like_term(term)
        return await self._db.fetch_all(
            """
            SELECT p.id, p.name, p.slug,
              (SELECT v.sku FROM product_variants v
                WHERE v.product_id = p.id ORDER BY v.sort_order LIMIT 1) AS sku
            FROM products p
            WHERE p.archived_at IS NULL
              AND (? IS NULL OR p.farm_id = ?)
              AND (
                p.name LIKE ? ESCAPE '!'
                OR p.slug LIKE ? ESCAPE '!'
                OR EXISTS (
                  SELECT 1 FROM product_variants v2
                  WHERE v2.product_id = p.id AND v2.sku LIKE ? ESCAPE '!'
                )
              )
            ORDER BY p.name
            LIMIT ?
            """,
            (farm_id, farm_id, pattern, pattern, pattern, limit),
        )

    async def search_orders(
        self, term: str, *, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[dict[str, Any]]:
        pattern = _like_term(term)
        return await self._db.fetch_all(
            """
            SELECT id, public_reference, customer_email, order_status, total_minor, currency_code
            FROM orders
            WHERE public_reference LIKE ? ESCAPE '!' OR customer_email LIKE ? ESCAPE '!'
            ORDER BY COALESCE(placed_at, created_at) DESC
            LIMIT ?
            """,
            (pattern, pattern, limit),
        )

    async def search_users(
        self, term: str, *, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[dict[str, Any]]:
        pattern = _like_term(term)
        return await self._db.fetch_all(
            """
            SELECT id, display_name, email, status
            FROM users
            WHERE user_type = 'staff' AND deleted_at IS NULL
              AND (display_name LIKE ? ESCAPE '!' OR email LIKE ? ESCAPE '!')
            ORDER BY display_name
            LIMIT ?
            """,
            (pattern, pattern, limit),
        )

    async def search_categories(
        self, term: str, *, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> list[dict[str, Any]]:
        pattern = _like_term(term)
        return await self._db.fetch_all(
            """
            SELECT id, name, slug, status
            FROM categories
            WHERE archived_at IS NULL
              AND (name LIKE ? ESCAPE '!' OR slug LIKE ? ESCAPE '!')
            ORDER BY name
            LIMIT ?
            """,
            (pattern, pattern, limit),
        )
