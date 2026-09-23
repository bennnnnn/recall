# Recall modular monolith

Recall is migrating toward one obvious home per product feature without changing deployment
topology. The API remains one FastAPI application and worker; the mobile app remains one Expo
application.

## Ownership map

| Concern | Home |
| --- | --- |
| Backend product behavior | `apps/api/app/modules/<domain>/` |
| Backend product tests | `apps/api/app/tests/modules/<domain>/` |
| Backend infrastructure | `apps/api/app/core/`, `gateways/`, `repositories/` |
| Mobile product behavior | `apps/mobile/features/<feature>/` |
| Expo navigation | `apps/mobile/app/` (route adapters only) |
| Mobile request transport | `apps/mobile/lib/api/client.ts` |
| Reusable mobile primitives | `apps/mobile/ui/` after extraction |

The rule is simple: if a product feature breaks, its module or feature folder is the first place
to open. Chat may orchestrate public feature interfaces; it must not know how another feature
stores data, schedules work, or talks to an external provider.

## Backend module shape

Use only the files a domain needs. A full module may contain `api.py`, `service.py`,
`repository.py`, `models.py`, `schemas.py`, `jobs.py`, `scheduler.py`, `tool.py`, and focused
implementation packages. File names are not mandatory; ownership and dependency direction are.

Infrastructure cannot import product modules. Application composition roots (`main.py`, process
bootstrap, tool registration, and model metadata registration) connect the two sides. Temporary
legacy modules may re-export a migrated public surface, but they contain no executable behavior
and must not receive new imports.

## Mobile feature shape

A feature owns its screens, components, hooks, model/state helpers, API slice, and tests. Expo
Router files only map URLs to feature screens. Feature API slices call the shared authenticated
request client and are composed into the existing `lib/api.ts` public barrel.

## Migration order

1. My Job (pilot) — migrated
2. Todos — migrated; the mobile feature is a day-grouped To-do list with optional dates
3. Learning — migrated
4. Memory — migrated
5. Google Calendar and Gmail — migrated
6. Images, attachments, and voice — attachments migrated
7. Math, physics, and chemistry
8. AI/model/tool infrastructure
9. Chat last

Each migration is its own reviewable change: preserve behavior, establish the public seam, run
the feature tests and architecture checks, then remove compatibility imports in a later cleanup.
