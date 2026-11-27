# Frontend data audit — 27 November 2026

The running frontend uses the existing backend. No backend code, database,
API contract or RAG implementation was changed.

## Production changes

- Restored **Đồ thị tri thức** in every workspace sidebar. Navigation and graph
  type metadata no longer import development fixtures. Company graph links now
  work for all available companies, retaining their company search context.
- Dashboard watchlists, company catalogs and company details call the existing
  APIs. Removed fabricated dashboard payloads and URL-driven fixture scenarios.
  A missing company is not replaced by an invented company record.
- Research uses the existing authenticated chat API and its stored history.
  Removed unused mock comparison/history code. The client refuses snapshots
  marked non-LIVE, including LIVE snapshots containing a non-LIVE answer.
- Profile shows the account returned by authentication. The backend has no
  profile-update/avatar API or authenticated password-change API; removed the
  preview forms that could not persist changes. Password reset links to the
  existing email verification flow.
- Mascot questions open the real research page; removed simulated answers and
  artificial response delays. Removed sample login credentials and fake Google
  controls. Clock reminders use the device clock, without a URL override.
- Landing now uses the existing authenticated company and market APIs for FPT,
  the interactive PriceHistory component, matching-period report citations and
  a four-index strip (VNINDEX, VN30, HNXINDEX, UPCOMINDEX). There is no captured
  JSON or screenshot fallback. Price polling and index refresh stop off screen
  or in a hidden tab. Signing out hides account-scoped data.
- Removed the laptop, snapshot captions and the English closing eyebrow.
  Anonymous visitors see a sign-in prompt because the existing APIs require
  authentication. Trading dates and stale-provider indicators remain attached
  to the actual data; old provider caches are never presented as current quotes.
- Removed the admin fixture-run launcher. Existing historical job records are
  still read from the real jobs API and truthfully retain their recorded modes.
- Vite includes only route page modules in its lazy page map. A production build
  guard rejects any development mock module in emitted chunks, including lazy
  chunks. Development fixtures and automated test transports remain isolated
  from the running application.

## Sources and limits

| Area | Data source |
| --- | --- |
| Companies / financial statements | `/api/companies`, PostgreSQL queries in `company_facts.py` |
| Market indices / prices / news | Existing `/api/market-data/*` services and provider caches |
| Watchlist | Authenticated `/api/watchlist` |
| Chat / history | `/api/research/chat/sessions`, stored backend sessions; non-LIVE snapshots rejected |
| Knowledge graph | `/api/graph/*`, published versions, entities, relations and evidence |
| Administration | Existing `/api/v1/admin/ingestion/*`, jobs and graph administration endpoints |
| Profile | Current account returned by the authentication API |

API-backed does not establish that every persisted database record is genuine,
or that a provider cache is fresh. Verification status, publication period,
source and unavailable states remain visible. No fallback generates financial
values when a service fails.

## Verification

- Production Vite build passes the real-data module guard.
- 169 Node tests pass, including non-LIVE chat rejection, the removed graph
  fixture switch and detection of development mocks in lazy production chunks.
- 24 public browser checks use actual HTTP responses: no API interception or
  fabricated authentication session. Responsive landing, auth forms, model
  attribution, protected-route redirects and mascot navigation are covered.
- Backend `/api/health` returns ready research, router and intent services.
  Ten protected endpoints checked through the frontend proxy return HTTP 401
  without credentials, including companies, watchlist, graph, chat, market data
  and administration. Subsequent authenticated checks with the supplied user
  and admin accounts cover 59 browser groups and 171 Node tests. See
  `QA-REPORT-20261127.md` for live chat/admin results and remaining data issues.
  Two confirmed Alpha/Beta seed graph versions are now blocked in the frontend;
  their backend records remain intact. API-backed is not proof that every stored
  record is genuine or fresh.

The standalone `design-review/FinMind-Full-UI-Review.html` remains an offline
design reference and is not imported or served by the production frontend.

## Landing API follow-up

176 Node tests pass. The production build passes. Public responsive checks and
embedded-chart controls were verified independently; chart-component regression
uses an earlier real OHLC capture only inside the test browser. No capture is
imported into the application. After restoring the PostgreSQL/Neo4j SSH tunnels,
eight fresh browser groups passed against the actual authenticated APIs. These
cover API-to-screen values, matching report periods, chart controls, mobile,
off-screen polling, logout cleanup, plus an isolated transport-failure/retry
check. No generated prices or authentication fixtures were used.

The API currently returns FPT prices through 26 November 2026. VNINDEX history
ends on 7 October; VN30/HNXINDEX end on 8 October; UPCOMINDEX has no saved bars.
The strip retains those actual trading dates and displays missing UPCOM data
without inventing a quote. These are provider/backend data limits.
