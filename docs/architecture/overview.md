# System architecture

```text
Browser
  |
  +--> www.truegrit.example ------------------+
  |      React storefront on Workers          |
  |                                           |
  +--> admin.truegrit.example                 |
         Cloudflare Access                    |
         React admin on Workers               |
                                              v
                                    api.truegrit.example
                                    Python FastAPI Worker
                                              |
        +----------------+--------------------+----------------+
        |                |                    |                |
        v                v                    v                v
       D1               R2                  Queues            KV
  relational data    media/files       async processing   short cache
```

## Layering (API)

Router -> Service -> Repository -> Platform adapter. Routers own HTTP concerns and permission
dependencies; services own business rules, workflow transitions, audit and outbox writes;
repositories own parameterized SQL; platform adapters own Cloudflare bindings. Business code
never imports Worker-specific objects (ADR-003).

## Key flows

- **Public catalogue request:** storefront loader -> `/v1/public/categories/:slug` -> slug
  validation -> published version + resolved products -> stable DTO -> SSR HTML with cache
  headers -> hydration.
- **Admin publish:** Cloudflare Access -> session/permission/CSRF checks -> workflow rule check
  -> immutable version row -> `published_version_id` swap -> audit log + outbox event in one
  batch -> queue invalidates cache and updates search.
- **Checkout (Release 2):** idempotency key -> server-side revalidation -> conditional
  inventory reservation -> order + snapshots -> payment intent via adapter -> signed webhook ->
  idempotent state transitions.

## State ownership (frontends)

URL for search/filter/sort/pagination; loaders for initial public content; TanStack Query for
interactive server state; local state for transient UI. No global store.
