# Approved FinMind UI

Visual baseline: `../design-review/FinMind-Full-UI-Review.html`.
The standalone review remains unchanged. The application uses React routes and
the existing API clients; no prototype router, fake sessions or fixture network
handlers are included in the production bundle.

## Components

- `src/pages/home/HomePage.jsx`: approved landing sections and internal links.
- `src/pages/home/hero/`: locally loaded MacBook, 360-degree drag, accessible
  rotation buttons, reset, reduced motion, capability and error fallbacks.
- `src/shared/ui/approvedReference.css`: namespaced styles and local fonts from
  the approved review. `approvedApp.css` binds the existing React components.
- `src/shared/ui/WorkspaceBar.jsx`: shared navigation and company search.
- Dashboard: session summary and index cards above the chart. Market news is
  below the chart in a two-column article grid; watchlist and Copilot stay in
  the short personal rail.
- Companies: searchable table/cards; overview, news, finance and report tabs.
- `CompanyFinancialSummary.jsx`: KPI and trend presentation of existing API
  facts, restricted to comparable periods and confirmed monetary units.
- `NewsList.jsx`: shared article presentation, original source and publication
  time. Prototype headlines are not used as live news.
- Auth: centered forms without a promotional panel; existing sessions return
  directly to their workspace. Google sign-in sizes to the form width.
- Research: existing send/stop/history/citation logic with compact messages.
- Watchlist: existing server persistence, remove/undo and add dialog.
- Admin, graph, profile and document routes share the approved shell and tokens.
  Existing unavailable or preview-only features retain their current status.

The optional mascot starts minimized and remains available through its button.
The backend, database, API contracts and RAG implementation are unchanged.

## Verification

Validated with the production Vite build, strict TypeScript checks for the 3D
components, and all 164 existing frontend Node tests. Browser checks cover 59
route/viewport combinations, nine interaction groups and four production-build
smoke groups. Authenticated browser checks use intercepted API fixtures in an
isolated test browser; they do not write to the team's databases.

The laptop screen and fallback poster now show an unsigned-in empty workspace
without financial values. The latest production data audit and remaining live
verification limits are documented in REAL-DATA-AUDIT.md. Model credit is in
the landing footer and public/models/laptop.LICENSE.txt.

Follow-up verification: 32 compound 3D orientations, real touch scroll/rotation,
five hero widths and three dashboard widths. Both rotation axes pass complete
turn and long-use normalization tests. The canvas is transparent and fitted to
the full model envelope, with a centered pivot and no floor-plane clipping.

Local development remains at `http://localhost:5174/`.
