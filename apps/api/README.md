# True Grit API

FastAPI application targeting Cloudflare Python Workers, with a portable core: business rules
never import Worker objects (ADR-003). The same app runs under uvicorn locally.

## Layout

```text
src/truegrit_api/
├── main.py            # create_app()
├── worker.py          # Cloudflare Python Workers entry point
├── config.py          # validated settings
├── errors.py          # application error hierarchy
├── middleware/        # request id, security headers, error handler
├── auth/              # sessions, principals, RBAC permission checks
├── domain/            # pure business rules (money, workflow, rules, blocks, inventory, orders)
├── services/          # orchestration: workflow + audit + outbox composition
├── repositories/      # protocols + parameterized SQL (D1-compatible)
├── platform/          # Database protocol, SQLite adapter (local/tests), D1 adapter (Workers)
└── schemas/           # Pydantic response DTOs (camelCase public boundary)
```

## Develop

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest --cov=src
uv run uvicorn truegrit_api.main:app --port 8787 --reload
```

Local runs build an in-memory SQLite database from `database/migrations` + the development
seed, exercising exactly the SQL that D1 will run. On Workers, the `DB` binding replaces it.

## Endpoints

- `GET /health/live`
- `GET /v1/public/bootstrap | home | categories/:slug | products/:slug | search?q=`
- `GET /v1/admin/me | products | categories | audit` (session cookie + RBAC)
- `GET /v1/admin/inventory-intelligence` (SKU forecasts + reorder decisions)
- `GET /v1/public/products/:id/recommendations` (explainable ranked products)
- `POST /v1/admin/categories/:id/publish` (workflow + audit + outbox in one batch)

Docs are intentionally not public (`docs_url=None`); the OpenAPI document is served at
`/internal/openapi.json` for contract generation.
