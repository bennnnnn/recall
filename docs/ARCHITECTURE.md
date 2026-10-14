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
| Reusable mobile primitives | `apps/mobile/ui/` (catalog: `apps/mobile/ui/README.md`) |

The rule is simple: if a product feature breaks, its module or feature folder is the first place
to open. Chat may orchestrate public feature interfaces; it must not know how another feature
stores data, schedules work, or talks to an external provider.

## Backend module shape

Use only the files a domain needs. A full module may contain `api.py`, `service.py`,
`repository.py`, `models.py`, `schemas.py`, `jobs.py`, `scheduler.py`, `tool.py`, and focused
implementation packages. File names are not mandatory; ownership and dependency direction are.

Infrastructure cannot import product modules. Application composition roots (`main.py`, process
bootstrap, tool registration, and model metadata registration) connect the two sides.

The re-exports that let callers move one at a time during the migrations are deleted. Their old
paths are listed in `app/tests/architecture/boundary_support.py` (`RETIRED_LEGACY_MODULES`), and
`test_legacy_paths_removed.py` fails if code or a test imports or patches one again. A future
migration may add a behavior-free re-export while its callers move, then deletes it and lists the
path there.

## Mobile feature shape

A feature owns its screens, components, hooks, model/state helpers, API slice, and tests. Expo
Router files only map URLs to feature screens. Feature API slices call the shared authenticated
request client and are composed into the existing `lib/api.ts` public barrel.

## Migration order

1. My Job — removed. Do not restore `modules/job_search/` or `/my-job`.
2. Todos — migrated; the mobile feature is a day-grouped To-do list with optional dates
3. Language learning — removed (do not restore `modules/learning/` or `/projects`)
4. Memory — migrated
5. Google Calendar and Gmail — removed (migration `0106`). Do not restore `modules/integrations/` or the Google OAuth gateways.
6. Images, attachments, and voice — migrated
7. Math, physics, and chemistry — three sibling modules, not `modules/stem/`. All three are migrated (`modules/math/`, `modules/physics/`, `modules/chemistry/`). A supported physics question uses the physics status, physics hints, and `[BEGIN VERIFIED PHYSICS]`. Algebra and average speed stay on the math status and `[BEGIN VERIFIED MATH]`. Dispatch is `services/subject_solving.py`: it picks one subject, then that subject's direct reply. Shared files are only the ones both sides use (graph fence, unit registry, verified-block primitives) and they live in a leaf neither subject owns. Molecule rendering stays in `lib/chemistry` because markdown already imports it.
8. AI/model/tool infrastructure. Product chat tools live with their modules (`images/gen_tool.py`, `images/search_tool.py`, `math/tool.py`). Registration stays in `services/mcp/__init__.py`, called from process bootstrap. The tool loop stays in `services/tool_loop.py` because it binds every module, and infrastructure cannot import product modules. Model catalog data stays in `models/model_catalog.py`. Web search lives in `modules/web_search/`, including its chat tool.
9. Home — migrated (`modules/home/`, `features/home/`).
10. Search — migrated (`modules/search/`, drawer search in `features/search/`).
11. Suggestions — migrated (`modules/suggestions/`, follow-up chips in `features/suggestions/`).
12. Account — migrated (`modules/account/` for `/auth`; sign-in in `features/auth/`, settings screens in
    `features/account/`). Every request still verifies its token in `core/deps.py` through
    `core/access_tokens.py`, so infrastructure never imports the module. Push-token registration is
    `modules/notifications/api.py`.
13. Chat — migrated. History, the WebSocket and SSE transports, turn prep, the stream pipeline and
    post-turn jobs are all `modules/chat/`. Chat reaches other modules only through the submodules
    they declare public (`_MODULE_EXPORTS`), and they reach chat's turn cues, presentation and stream
    status through the `app.modules.chat` package. The tool loop stays in `services/tool_loop.py`.
    On mobile, the chat screen, its hooks, components, stream/socket model and API slice are
    `features/chat/`; `app/index.tsx` is a one-line route.

Each migration is its own reviewable change: preserve behavior, establish the public seam, run
the feature tests and architecture checks, then remove compatibility imports in a later cleanup
(done for every domain above).
