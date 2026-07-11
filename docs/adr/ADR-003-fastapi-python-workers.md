# ADR-003: FastAPI on Cloudflare Python Workers

## Decision

Use FastAPI on Cloudflare Python Workers while isolating platform bindings.

## Reason

Python backend requirement, edge deployment, shared Cloudflare platform, FastAPI validation
and OpenAPI generation.

## Risk

Python Workers are beta.

## Mitigation

Repository protocols, platform adapters, pure-Python business services, no unsupported native
dependencies, migration path to Cloudflare Containers or another Python runtime. The
application also runs under uvicorn for local development and portability.
