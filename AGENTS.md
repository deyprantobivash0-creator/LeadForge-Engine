# LeadForge engineering contract

## Product and source of truth

LeadForge-Engine is an AI Lead Intelligence & Revenue Operations SaaS platform. The repository is the source of truth for implemented behavior; product intent is not proof of implementation. Read the relevant documents before changing code:

- [Architecture](docs/ARCHITECTURE.md)
- [API contracts](docs/API_CONTRACTS.md)
- [AI architecture](docs/AI_ARCHITECTURE.md)
- [Database](docs/DATABASE.md)
- [Development](docs/DEVELOPMENT.md)
- [Production roadmap](docs/PRODUCTION_ROADMAP.md)

## Repository map

`backend/api/` owns HTTP routes and transport schemas; `backend/services/` owns business operations; `backend/repositories/` owns database queries; `backend/models/` owns ORM entities; `backend/schemas/` owns shared API schemas; `backend/ai/` owns provider and AI orchestration concerns; `backend/agents/` owns specialized analyses; `backend/database/` owns sessions and metadata. `frontend/src/` owns the React app, views, and API services. `alembic/` owns schema migrations. `tests/` is the intended isolated test home.

These are responsibility boundaries, not a claim that current code consistently follows them. Competing ingestion, AI workflow, schema, and frontend paths must be reconciled before extension. Search for an existing implementation before adding another service, provider, or workflow.

## Mandatory rules

1. Scope every customer-owned query and mutation to an organization obtained from authenticated user membership. Never bypass tenant isolation or add another default-organization business path.
2. Keep routes thin, business rules in services, and database access in repositories. Give multi-step writes one operation-level transaction boundary.
3. Change application schema through Alembic. Do not use `Base.metadata.create_all()` as a production migration strategy or casually rewrite historical migrations.
4. Verify backend response schemas before frontend work. `frontend/src/services/api.js` currently returns parsed JSON directly; callers must not assume `response.data` unless the wrapper is intentionally redesigned and all callers migrated.
5. Do not hardcode intelligence that looks like customer data. Validate AI structured output before persistence, preserve deterministic scoring where specified, and handle provider timeouts and errors.
6. Do not expose or commit secrets. Do not read or modify `.env` contents unless explicitly instructed.
7. Avoid unrelated refactors. Inspect `git diff` after meaningful changes and report verification honestly; do not claim completion while required checks fail.

## Definition of done

- **Backend:** relevant isolated tests pass; tenant isolation is tested where applicable; API contract is preserved or intentionally versioned; schema changes include verified migrations; no secrets or duplicate architecture are introduced.
- **Frontend:** API shape is verified; loading and error states work; production build passes, including case-sensitive imports.
- **AI:** mock-provider path works without paid services; structured output is validated; pending, processing, completed, and failed transitions are tested.
