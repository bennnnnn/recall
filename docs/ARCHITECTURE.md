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

## Adding to the backend: one place each

Paths are under `apps/api/app/`. Running more than one machine is
[SCALING.md](./SCALING.md).

| To add | Do this |
| --- | --- |
| A setting or feature flag | One field, with its default and a comment saying why, in the section of `core/settings/` it belongs to. Its env name is the field name in upper case. Code reads `get_settings().<field>`; `core/config.py` only joins the sections and holds the production boot rules (`validate_production_settings`). |
| A plan allowance | Three fields in `core/settings/plans.py` (`<base>`, `<base>_plus`, `<base>_pro`) and one `Allowance` in `modules/billing/entitlements.py`. |
| A model alias | One entry in `models/model_catalog.py`. Request schemas validate against the catalog itself (`validate_user_alias`); there is no second list. |
| An external API | One module in `gateways/` that calls `get_pooled_client(<NAME>_TIMEOUT_SECONDS)` (`gateways/http_client.py`), returns typed results and maps provider failures to its own errors or `None`. It imports no module. |
| A background job | The handler in the owning module (`jobs.py`) or `background/handlers.py`, one `register(...)` line in `background/handlers.register_all`, and an `enqueue(...)` off the request path with a dedupe key. A job that calls a model carries `@_unless_spend_capped`. |
| A periodic scheduler | A cycle over `background/periodic.py` (`run_locked_cycle` takes the Redis lock so one worker runs each tick; `start_periodic` / `stop_periodic`), and one `(start, stop)` row in `process_bootstrap._schedulers()`. |
| A Redis counter or limit | `core/rate_limit.allow_request` for a windowed limit; a key with a TTL for anything else. Never in-process state when several machines must agree. |
| A per-process cache | `core/ttl_cache.TtlCache` (expiring, size-capped), behind a module whose functions are the interface (`core/user_cache.py` is the example), and a row in SCALING.md saying what being per machine means. |
| A Sentry report from a best-effort path | `core/sentry.report_breadcrumb` / `report_message` / `report_exception`: they never raise. |
| A dependency outage answered as 503 | Its exception type in `core/unavailable.UNAVAILABLE_EXCEPTIONS`. |
| An HTTP route | The module's `api.py`, registered in `main.create_app` (the domain recipe below). |

## Adding a backend domain or endpoint

Every new product surface follows the same recipe; each step is one file, and the composition
roots are the only shared files it touches.

| Step | Where | Notes |
| --- | --- | --- |
| Package | `modules/<domain>/__init__.py` | A docstring. Name any submodule other modules may import beyond `api`, `schemas`, `service` and `crud` in `_MODULE_EXPORTS`; keep the initializer free of service code (lazy `_EXPORTS` only when importing the package must not load the graph). |
| HTTP | `modules/<domain>/api.py` | `router = APIRouter(prefix="/<domain>")`. Thin: validate, call the service, map domain errors to `HTTPException` (one `contextmanager` when several routes share the mapping, as in `attachments/api.py`). |
| Rules and transactions | `modules/<domain>/service.py` | Owns the commit (repository writes with `commit=False`, one commit, roll back on failure), then cache invalidation and job enqueue. |
| Queries | `modules/<domain>/repository.py` | Queries only; writes take `commit`. Tables several domains read stay in `repositories/`. |
| Wire and ORM | `schemas.py`, `models.py` | ORM models are registered in `models/orm/__init__.py`; schema changes are expand-then-contract migrations. |
| Background work | `modules/<domain>/jobs.py` | The handler and its enqueue helper (the payload shape lives in one place); register the job type in `background/handlers.py`. |
| Model tool | `modules/<domain>/tool.py` | A `ToolAdapter`; register it in `services/mcp/__init__.py`. |
| Plan, caps, flags | `modules/billing/entitlements.py`, `services/quota/counters.COUNTERS`, `core/settings/` | A metered feature is an allowance; a daily cap is one `CounterSpec`; a kill switch is one `*_enabled` setting. |
| Registration | `main.py` | `app.include_router(...)`; an upload route also joins `UPLOAD_BODY_PATHS`. |
| Tests | `tests/modules/<domain>/` | Plus an ownership test in `tests/architecture/test_product_module_boundaries.py`. |
| Phone | `features/<feature>/api.ts` | Composed into `lib/api.ts`. |

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
8. AI/model/tool infrastructure. Product chat tools live with their modules (`images/gen_tool.py`, `images/search_tool.py`, `math/tool.py`). Registration stays in `services/mcp/__init__.py`, called from process bootstrap. Tools take the turn's context as an argument, so the tool loop binds no module and lives with chat in `modules/chat/tool_loop/`. Model catalog data stays in `models/model_catalog.py`. Web search lives in `modules/web_search/`, including its chat tool.
9. Home — migrated (`modules/home/`, `features/home/`).
10. Search — migrated (`modules/search/`, drawer search in `features/search/`).
11. Suggestions — migrated (`modules/suggestions/`); its proactive chips were removed from the app. Follow-up questions under a reply come from `modules/chat/related_prompts.py` and render in `features/suggestions/`.
12. Account — migrated (`modules/account/` for `/auth`; sign-in in `features/auth/`, settings screens in
    `features/account/`). Every request still verifies its token in `core/deps.py` through
    `core/access_tokens.py`, so infrastructure never imports the module. Push-token registration is
    `modules/notifications/api.py`.
13. Chat — migrated. History, the WebSocket and SSE transports, turn prep, the stream pipeline and
    post-turn jobs are all `modules/chat/`. Chat reaches other modules only through the submodules
    they declare public (`_MODULE_EXPORTS`), and they reach chat's turn cues, presentation and stream
    status through the `app.modules.chat` package. The tool loop is `modules/chat/tool_loop/`.
    On mobile, the chat screen, its hooks, components, stream/socket model and API slice are
    `features/chat/`; `app/index.tsx` is a one-line route.
14. Product analytics — migrated (`modules/analytics/`: `api.py` serves `/analytics`, `service.py`
    holds the per-event property allowlist). The `product_events` repository stays shared in
    `repositories/` because account export reads it too.
15. Link preview — migrated (`modules/link_preview/`: `api.py` serves `/link-preview`, `service.py`
    fetches through `gateways/safe_fetch.py` and caches the card).

Each migration is its own reviewable change: preserve behavior, establish the public seam, run
the feature tests and architecture checks, then remove compatibility imports in a later cleanup
(done for every domain above).
