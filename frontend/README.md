# CodeSentinel Dashboard

Frontend for the CodeSentinel AI code review dashboard.

## Stack

- Vue 3 + TypeScript
- Vite
- Vue Router
- Element Plus (on-demand components via `unplugin-vue-components`)
- Axios
- Vitest + Vue Test Utils

Charts are rendered with native SVG/CSS; ECharts is not a dependency.

## Requirements

- Node.js `^22.18.0 || >=24.12.0` (verified with Node `24.14.0`)
- npm 11+

`package.json` contains a narrow npm override that pins `js-beautify`'s CLI-only
`nopt` dependency to `8.0.0`. Upstream `nopt@10` requires Node
`^22.22.2 || ^24.15.0 || >=26.0.0`, which conflicts with this project's declared
Node range. `@vue/test-utils` imports the js-beautify library rather than its
CLI, and both the library and CLI are smoke-tested with the override.

## Commands

```bash
npm install
npm ci               # reproducible install from package-lock.json
npm run dev          # http://localhost:5173
npm run type-check
npm run test:unit
npm run build
npm run lint         # auto-fixes
npm run lint:check   # non-mutating validation
```

## Environment

Copy `.env.example` to `.env` when overrides are needed:

```text
VITE_API_BASE_URL=          # empty = same origin
DEV_PROXY_TARGET=http://localhost:8080
```

During development Vite proxies `/api` to the Spring Boot service configured by
`DEV_PROXY_TARGET`, so no backend CORS configuration is required for local work.

The dev server binds explicitly to `127.0.0.1` and is not reachable from other
machines. Do not run `vite --host 0.0.0.0` or otherwise expose the dev server to
the LAN. Because the proxy connects to Spring Boot from loopback, any same-host
reverse proxy must enforce its own authentication before exposing the dashboard.

## Structure

```text
src/
├── api/          # Axios client and browser-safe API modules
├── assets/       # global styles
├── components/   # shared and insight presentational components
├── config/       # non-secret application constants
├── layouts/      # dashboard shell (sidebar + top bar)
├── router/       # route table and document title handling
├── test/         # Vitest setup
├── types/        # shared TypeScript types
├── utils/        # normalized API errors
└── views/        # dashboard, review history/detail, insights, 404
```

## Security boundary

The Phase 10 service-to-service review history API remains protected by a
service-level `X-Internal-Token`. That credential is never embedded in browser
code. Review History, Review Detail, and Review Insights read from the
same-origin Dashboard BFF under `/api/dashboard/**`, which is restricted to
loopback peers at the application level and does not accept or forward
`X-Internal-Token`. No internal token is stored in browser storage or sent by
this frontend.

## Scope

The dashboard currently provides:

- Dashboard home with backend health, pipeline overview, and environment details
- Review History with filters, pagination, and sorting
- Review Detail with report, finding, and comment views
- Review Insights with summary metrics, distributions, and data-quality disclosure
- Review / Finding / High + Critical trends
- Bug / Security / Performance / Quality / Unknown category trends with DAY/WEEK switching
- Native SVG/CSS charts; no ECharts dependency

Custom Rules and authentication remain out of scope.
