\# docs/PRODUCT-SPEC.md — StockPilot Frontend (ERP)



\# 



\*\*What this document is:\*\* the Product Requirements Document for the StockPilot ERP Frontend. It defines \_what\_ the application does and \_why\_ — behavior, scope, and rules a user or a reviewer would recognize. It contains no implementation detail; anything about how a requirement is built belongs in `docs/ARCHITECTURE.md` (system design) or `CLAUDE.md` (engineering rules). Build order lives in `BUILD.md`.



This is a living document, superseding the version merged into it. Existing content (roles, journeys, functional requirements, page specs, roadmap) is preserved below and extended with the sections listed in this revision's brief: vision, goals, personas, KPI definitions, workflows, business rules, reporting, notifications, error/empty states, export, search/filter behavior, mobile expectations, and accessibility.



\* \* \*



\## 1\\. Product vision



\# 



StockPilot is the operational system of record for a small-to-mid-size retail or e-commerce business — inventory, products, suppliers, purchasing, and sales — with an AI assistant (RetailOps AI) available everywhere in it to explain what's happening and recommend what to do next, without ever acting on the business's behalf without a human decision. The ERP tells you the state of the business; the AI Assistant helps you understand and act on it faster. Neither ever fabricates a number to make itself more useful.



\## 2\\. Product goals



\# 



\-   Give an operator a single place to see and manage inventory, purchasing, and sales — replacing spreadsheets and disconnected tools.

\-   Make every figure in the system traceable to its source, so trust in the dashboard doesn't erode the way trust in a black-box report does.

\-   Make the AI Assistant genuinely useful for daily decisions (reorder, investigate a metric, review a supplier) without letting it become a second, unverifiable source of truth.

\-   Demonstrate, as a portfolio artifact, a production-quality enterprise UI built to the density and precision bar of the tools it's modeled on (Fiori, NetSuite, Stripe Dashboard, Linear) rather than a template.



\## 3\\. Business objectives



\# 



\-   Reduce time-to-decision on inventory questions (e.g. "what's at risk of stocking out this week") from a manual spreadsheet lookup to a single dashboard glance or AI query.

\-   Reduce the chance of a stockout or overstock going unnoticed by surfacing it proactively (Dashboard, Notifications) rather than requiring a scheduled manual review.

\-   Provide an auditable trail (Audit Logs, recommendation log) sufficient to answer "why did this change happen and who approved it" without needing to check a separate system.

\-   Establish one product family (StockPilot + RetailOps AI) that reads as a coherent platform rather than two disconnected tools, so future capacity (a mobile app, additional modules) has a consistent base to extend.



\## 4\\. Target users



\# 



Small-to-mid-size retail/e-commerce operations teams: the people who manage stock, place orders with suppliers, and review business performance day to day — not end consumers, and not a large enterprise's dedicated IT/ops department. The application assumes a lean team where one person may hold more than one of the roles in §6.



\## 5\\. User personas



\# 



\*\*Priya — Inventory Manager.\*\* Checks stock levels every morning before anything else. Cares most about not being surprised by a stockout. Wants the dashboard to tell her what needs attention today without her having to go looking for it. Trusts a number more if she can see where it came from — has been burned before by a reporting tool that silently used stale data.



\*\*Daniel — Procurement Lead.\*\* Manages relationships with a dozen suppliers and juggles purchase order timing against cash flow and lead times. Wants to move fast between "decide to reorder" and "PO is submitted," and wants receiving to be accurate down to partial-shipment quantities, because reconciling receiving errors by hand is his least favorite part of the job.



\*\*Amara — Owner/Admin.\*\* Reviews the business monthly at a high level (Analytics, Reports), and otherwise mostly stays out of day-to-day operations. Cares about the system being trustworthy enough to make a real decision from, and about being able to see who did what if something looks wrong later (Audit Logs). Manages who has access to what (Settings, Users, Roles).



\*\*Sam — Analyst (internal or contracted).\*\* Pulls together periodic performance reviews. Wants clean exports and reliable period-over-period comparisons more than day-to-day operational features. Never mutates data — read-only by role and by habit.



\## 6\\. User roles



\# 



\*\*Decided role set, not provisional\*\* — this table is now the spec for real backend functionality (`BUILD.md` Backend Module 10: Administration), not an aspiration checked against a backend that lacks it. `docs/ARCHITECTURE.md` § Authorization defines the concrete data model (a many-to-many `roles`/`user\_roles` design, since §4 above already assumes one person may hold more than one role) and exactly what's server-enforced. `lib/rbac/permissions.ts` in the frontend already implements this table's permission intent in code — that file, not a fresh redesign, is the vocabulary the backend model mirrors.



| Role | Description | Broad access |

| --- | --- | --- |

| \*\*Admin\*\* | Full system access, tenant configuration | Everything, including Settings/Users/Roles |

| \*\*Inventory Manager\*\* | Owns stock accuracy | Inventory, Products, Purchase Orders (create/receive), Suppliers, read-only Analytics |

| \*\*Procurement\*\* | Owns supplier relationships and ordering | Suppliers, Purchase Orders (full), read-only Inventory/Forecasts |

| \*\*Sales\*\* | Owns customer/order side | Sales, Customers, read-only Products/Inventory |

| \*\*Analyst\*\* | Read-only, cross-cutting | Dashboard, Analytics, Reports, Forecasts — no mutations anywhere |

| \*\*Viewer\*\* | Minimal, e.g. an external stakeholder | Dashboard only, read-only |



Every role can use the AI Assistant sidebar, scoped to what that role can already see — the AI never surfaces data or recommendations a role couldn't otherwise access. This is a functional requirement, not just a UI nicety: the sidebar's queries carry the same auth context and must be denied server-side the same as a direct API call would be.



\## 7\\. User journeys



\# 



\*\*Journey 1 — Morning check-in (Priya, Inventory Manager).\*\* Log in → Dashboard shows low-stock count and revenue-at-risk → click into low-stock panel → Inventory filtered to at-risk items → open one product's AI-surfaced reorder recommendation → Accept → recommendation logged, item flagged pending in the recommendation log → move to next item.



\*\*Journey 2 — Receiving a delivery (Priya or Daniel).\*\* Purchase Orders → find the PO for today's delivery (search/filter by supplier or status) → open detail → Receive → enter actual received quantities per line (may be partial) → confirm → inventory levels update immediately → PO status reflects Partially Received or Received.



\*\*Journey 3 — Investigating a revenue dip (Sam, Analyst).\*\* Dashboard → revenue KPI shows a drop vs. prior period → click "Explain this metric" → AI sidebar opens with dashboard/revenue context pre-filled → answer streams in with citation chips → click a chip → provenance drawer shows the underlying tool call and raw figures → navigate to Analytics for the fuller breakdown the answer referenced.



\*\*Journey 4 — Onboarding a new supplier (Daniel, Procurement).\*\* Suppliers → New → fill contact and terms → save → immediately create a first Purchase Order against that supplier from the supplier detail page's "New PO" action, pre-filled with the supplier selected.



\*\*Journey 5 — Admin sets up a new team member (Amara, Admin).\*\* Settings → Users → Invite → assign role → new user receives access, scoped by role from first login → Admin checks Audit Log a day later to confirm the new user's actions are visible and correctly attributed.



\*\*Journey 6 — Executive review (Amara or Sam, monthly).\*\* Dashboard → Analytics → Reports → export the executive rollup for a meeting; no mutation actions taken, this journey is read-only end to end.



\## 8\\. Functional requirements



\# 



Numbered per resource area; each maps to a `BUILD.md` stage.



\*\*FR-1 Authentication\*\* — user can log in with StockPilot Core credentials, session persists across reload, expired sessions redirect to login and return the user to their original destination after re-auth.



\*\*FR-2 Dashboard\*\* — user sees, without navigating, current revenue trend, inventory value, low-stock count, open PO count, and a recent-activity feed, each figure traceable to a real source. See §11 for KPI definitions.



\*\*FR-3 Products\*\* — user can list, search, filter, create, edit, and (where no dependent records block it) delete products, including category/ brand assignment, images, and pricing.



\*\*FR-4 Inventory\*\* — user can view current stock across locations, search and filter (category, warehouse, status, supplier), export the current view, perform bulk actions, and drill into per-item history.



\*\*FR-5 Suppliers\*\* — user can manage supplier records, contacts, view linked purchase history, and (where the backend supports it) performance metrics.



\*\*FR-6 Purchase Orders\*\* — user can create a PO, move it through its status workflow (§12), and receive stock (full or partial) with inventory updating immediately on confirmation.



\*\*FR-7 Sales\*\* — user can view orders, customers and their order history, and revenue reporting broken out by product/category/period.



\*\*FR-8 Forecasts\*\* — user can view demand forecasts per product/category with explicitly labeled prediction intervals.



\*\*FR-9 Analytics\*\* — user can view executive-level rollups: turnover, ABC classification, dead stock, supplier analytics.



\*\*FR-10 Reports\*\* — user can generate/export a defined set of standard reports. See §15.



\*\*FR-11 Notifications\*\* — user sees system-generated notices in a notification center, markable as read. See §16.



\*\*FR-12 Audit Logs\*\* — user with permission can see who changed what business record, when, filterable by user/resource/date.



\*\*FR-13 Settings / Users / Roles\*\* — admin can manage users, define roles and permissions, manage API keys, and configure tenant-level system settings.



\*\*FR-14 Profile\*\* — any user can view/edit their own profile and preferences.



\*\*FR-15 AI Assistant\*\* — user can open a context-aware sidebar from any page, ask questions, receive cited answers, drill into provenance, and see/act on inline recommendations. See §14 for full behavioral rules.



\## 9\\. Non-functional requirements



\# 



\-   \*\*Performance:\*\* the app must feel immediate on the highest-traffic pages (Dashboard, Inventory) — no visible jank scrolling a large table, no long blank-screen wait on navigation. Precise budgets and how they're enforced live in `CLAUDE.md` and `docs/ARCHITECTURE.md`.

\-   \*\*Accessibility:\*\* WCAG 2.1 AA as the floor. See §19.

\-   \*\*Security:\*\* a user can only see and do what their role permits, and that boundary holds even if the UI is bypassed (direct URL, direct API call) — not just hidden by the interface. Full mechanism in `docs/ARCHITECTURE.md` § Authorization.

\-   \*\*Reliability:\*\* every mutating action gives specific success/failure feedback; no silent failures.

\-   \*\*Honesty:\*\* no figure displayed without a traceable source; no recommendation worded as an action taken; no fabricated metric, confidence value, or outcome claim anywhere in the app. See §13.

\-   \*\*One product family:\*\* the two frontends (StockPilot ERP, RetailOps AI) must read as one platform — shared visual identity and a single login wherever technically achievable (see `docs/ARCHITECTURE.md` § Session Management for the current status of that goal).



\## 10\\. Product workflows



\# 



\*\*Purchase Order lifecycle\*\* — the central stateful workflow in the product: Draft → Submitted → Approved → Partially Received → Received → Closed. A PO can only move forward, never skip a state, and receiving can happen incrementally across multiple deliveries against the same PO until its lines are fully received. See §12 for the business rules governing each transition.



\*\*Reorder recommendation → action\*\* — the AI Assistant identifies a reorder candidate (Inventory Details or Dashboard) → user reviews the recommendation's impact fields → user Accepts (which does \_not\_ create a PO automatically — it logs the decision and, at the user's discretion, they proceed to create the PO themselves) or Rejects or Snoozes. Automatic PO creation from an accepted recommendation is explicitly out of scope (§20) — the human remains the one who initiates the actual order.



\*\*User onboarding\*\* — Admin invites → user receives access scoped to an assigned role from first login → no self-service signup exists; all access is admin-granted.



\## 11\\. Dashboard KPIs and definitions



\# 



| KPI | Definition | Source |

| --- | --- | --- |

| \*\*Revenue\*\* | Total sales value over the selected period, compared to the immediately preceding period of equal length | Sales/Orders data |

| \*\*Revenue at risk\*\* | Value of inventory currently below its reorder threshold, priced at expected sale value, that could be lost to a stockout if not reordered in time | Inventory + pricing data, computed |

| \*\*Inventory value\*\* | Sum of on-hand quantity × cost price across all products and locations, as of now | Inventory + Products data |

| \*\*Low-stock count\*\* | Number of distinct products currently below their defined reorder threshold | Inventory data |

| \*\*Open PO count\*\* | Number of purchase orders not yet in a terminal state (Received or Closed) | Purchase Orders data |

| \*\*Open Actions Needed\*\* | Count of AI recommendations awaiting a decision (not yet accepted, rejected, or snoozed) | Recommendation log |



Any KPI that is computed (not a direct database value — e.g. Revenue at risk, Inventory value) is disclosed as computed wherever the design system's provenance pattern is visible on that KPI, per §13. A KPI definition change (e.g. what counts as "low stock") is a product decision recorded here, not a silent code change.



\## 12\\. Business rules



\# 



\-   A Purchase Order cannot be edited once Submitted — only its status can advance, or it can be cancelled from Draft/Submitted (not from Approved onward, where a supplier commitment may already exist — confirm this cancellation boundary against actual business need before Stage 5).

\-   A Purchase Order line cannot receive more than its ordered quantity without an explicit over-receipt confirmation step (flagged distinctly, not silently accepted).

\-   A Product cannot be deleted while it has open PO lines, existing sales order history, or non-zero on-hand inventory — deletion is blocked with a specific reason, not a generic error.

\-   A Supplier cannot be deleted while it has open Purchase Orders referencing it.

\-   Reorder threshold, once set on a product, determines the "low stock" and "at risk" classifications used across Dashboard, Inventory, and Notifications — one definition, used consistently everywhere it appears.

\-   A recommendation, once accepted or rejected, is immutable in the log — a user can act on a \_new\_ recommendation but cannot retroactively alter the record of a prior decision.

\-   Role permissions determine visibility and mutation rights per §6; a role change takes effect on the user's next authenticated action.



\## 13\\. Data provenance rules



\# 



Anywhere this app displays a figure, recommendation, or explanation that originated from RetailOps AI (not directly from StockPilot Core), it is visually distinguished so a user never has to guess whether a number came from the business database or from an AI inference. Every metric carries one of four provenance classes — \*\*Observed\*\* (directly recorded), \*\*Derived\*\* (deterministic calculation over recorded data), \*\*Predicted\*\* (model output, e.g. a forecast), or \*\*Inferred\*\* (an AI-generated estimate or judgment, the least certain class) — and confidence values are always Derived or Predicted, never Observed. This rule applies with equal weight across the whole app, not only on AI-sourced screens — a computed KPI on the plain Dashboard follows the same disclosure standard as an AI answer in the sidebar.



\## 14\\. AI Assistant behavior



\# 



\-   The assistant explains and recommends; it never performs a mutating action on its own. Every recommendation requires an explicit human Accept before any downstream action (like creating a PO) is taken by the user themself — the assistant does not create, edit, or delete records.

\-   Every factual claim or figure in an assistant response is traceable to a citation; an assistant response that cannot support a figure this way flags it rather than presenting it as fact (see §13).

\-   The assistant is context-aware: opening it from a specific page or record means it already knows what the user is looking at, so the user doesn't have to restate it.

\-   Wording never implies autonomous action: "Recommended," "Pending review," "Accepted by you" — never a checkmark or past-tense verb suggesting the system already did something.

\-   The assistant is scoped to what the current user's role permits (§6) — it never becomes a way to see data a direct page view wouldn't show that user.

\-   On a static historical dataset, the assistant does not claim to learn from real-world outcomes of past recommendations (§20) — its recommendations are generated fresh from current data each time, not from a feedback loop that doesn't honestly exist yet.



\## 15\\. Reporting requirements



\# 



Standard, exportable reports — confirm the exact set against what StockPilot Core can actually produce before building; this is the intended set:



\-   \*\*Inventory valuation\*\* — on-hand value by product/category/location as of a chosen date.

\-   \*\*Sales summary\*\* — revenue and order count by period, product, or category.

\-   \*\*Supplier performance\*\* — delivery timeliness and order accuracy per supplier over a period.

\-   \*\*Dead stock\*\* — products with no sales activity over a defined lookback window.



Each report: has a defined date range or as-of date, is exportable (CSV at minimum; PDF where feasible), and states its generation timestamp so a user knows how current it is.



\## 16\\. Notification requirements



\# 



\-   \*\*Triggers:\*\* stock crosses below its reorder threshold; a Purchase Order is awaiting the current user's approval; a forecast is significantly revised for a product the user has previously interacted with; a new AI recommendation is generated for a resource in the user's scope.

\-   \*\*Delivery:\*\* in-app notification center only for the initial scope — email/push notification channels are future roadmap (§20).

\-   \*\*State:\*\* read/unread, markable individually or in bulk; clicking a notification navigates to the relevant resource.

\-   \*\*Retention:\*\* notifications remain visible for a defined trailing window (confirm retention period against backend capability); they are not permanently deleted from the audit trail even once dismissed from the notification center, since the underlying event may still be relevant to Audit Logs.



\## 17\\. Error state behavior



\# 



Every error a user can encounter states, in the interface's own voice, plain sentence-case wording:



\-   \*\*What happened\*\* — specific to the situation, never a bare "Something went wrong."

\-   \*\*Why, if useful to the user\*\* — e.g. "this supplier has 3 open purchase orders" rather than just "cannot delete."

\-   \*\*What to do next\*\* — retry, adjust input, or contact support, as appropriate.



Errors never apologize on the interface's behalf and are never vague about what failed. A validation error appears next to the field it concerns, not as a disconnected banner. A system-level failure the user can't fix themselves (e.g. a downstream service outage) still gets a specific, honest message plus a reference the user can quote if they contact support.



\## 18\\. Empty states



\# 



Every list, table, or panel that can have zero items defines what a user sees and can do about it — never a bare "No data":



\-   A genuinely empty resource (e.g. no suppliers yet) invites the first action: one sentence plus a clear create/add control.

\-   A filtered view with zero matches is distinguished from a genuinely empty resource — it explains that filters are active and offers to clear them, rather than implying nothing exists at all.

\-   A new tenant's Dashboard shows a short setup checklist instead of blank charts.



\## 19\\. Search and filtering behavior



\# 



\-   Every list page's search is a live query against the full dataset, not a client-side filter over an already-loaded page — a search for a product not on the currently visible page still finds it.

\-   Filters combine (AND, not OR, unless a specific field is explicitly multi-select) and can be applied together — e.g. category + low-stock status + supplier simultaneously.

\-   The current search/filter/sort state of a list is reflected in the page's URL, so a view can be bookmarked, shared, or returned to via the browser back button without losing state.

\-   Clearing filters is a single, obvious action, not a per-filter chore.



\## 20\\. Export functionality



\# 



\-   \*\*Inventory, Products, Sales/Orders, Reports (§15):\*\* exportable as CSV from the current filtered/sorted view — what's on screen is what's exported, not a silent full-dataset dump that ignores active filters.

\-   \*\*PDF export\*\* is offered where a formatted document genuinely adds value (the standard Reports in §15); not required for raw data tables.

\-   Every export includes a generation timestamp so a downloaded file's currency is unambiguous later.



\## 21\\. Mobile responsiveness expectations



\# 



\-   The application is a responsive web app, not a native mobile app (native mobile is future roadmap, §22).

\-   \*\*Fully usable at tablet width (≈768px):\*\* Dashboard, all detail pages, forms, the AI sidebar (as a full-screen overlay rather than a persistent side panel at this width).

\-   \*\*Usable but not optimized for dense interaction below tablet width:\*\* the heaviest data tables (Inventory, Purchase Orders) — these remain functional (scrollable, filterable) on a phone-width screen but are not the primary design target; a power user managing inventory day to day is expected to be on a laptop or tablet, not a phone.

\-   No feature is desktop-only in a way that silently breaks below desktop width — at minimum, every action remains reachable, even if the layout is denser or requires more scrolling.



\## 22\\. Accessibility requirements



\# 



\-   WCAG 2.1 AA as the floor across every page, not just the primary flows.

\-   Full keyboard operability for every action, including table row actions, bulk-select, and multi-step forms — a mouse is never required.

\-   Every icon-only control has an accessible label; every form field has an associated label and, on error, an announced, field-associated message.

\-   Status and provenance are never conveyed by color alone — always paired with text or shape (§13).

\-   Contrast: at least 4.5:1 for text, 3:1 for non-text UI elements, in both light and dark themes.

\-   Data tables use correct semantics (native `<table>` or an equivalent ARIA grid pattern) so they're navigable by screen reader — verified specifically on the Inventory and Purchase Order tables, the densest surfaces in the app.



\## 23\\. Acceptance criteria (product-level)



\# 



The full product (both StockPilot Core backend and StockPilot Frontend, per `BUILD.md`'s module order) is acceptance-ready when:



\-   Every FR in §8 is demonstrably working end-to-end against real StockPilot Core data, not mocked data or a placeholder endpoint left in place.

\-   Every user journey in §7 relevant to the shipped scope can be walked start to finish without a dead end or console error.

\-   Every page in scope passes the Definition of Done in `CLAUDE.md`.

\-   The README states plainly which FRs/pages are live vs. roadmap-only — no feature is silently absent without being called out.



\## 24\\. Page-by-page specification



\# 



Each entry: purpose, primary user, core content, key actions, empty-state behavior. Detailed component/layout decisions belong in `docs/DESIGN-SPEC.md` and in-repo Storybook (if added), not duplicated here.



\*\*Dashboard\*\* — Purpose: daily status at a glance. Primary user: all roles (content scoped by role). Core content: KPI cards per §11, revenue chart, activity feed. Key actions: drill into any KPI, "Explain this metric." Empty state: per §18, a setup checklist for a new tenant.



\*\*Products\*\* — Purpose: catalog management. Primary user: Inventory Manager, Admin. Core content: searchable/filterable list, detail with pricing/images/category/brand/history. Key actions: create, edit, delete (blocked per §12 if dependent records exist). Empty state: "No products yet — add your first product," with the create action inline.



\*\*Inventory\*\* — Purpose: stock visibility and action. Primary user: Inventory Manager. Core content: dense table (location, quantity, status, supplier), per-item detail with history. Key actions: search, filter, export, bulk actions, drill to product/supplier. Empty state: per-filter ("no items match these filters," with a clear-filters action), not conflated with a genuinely empty catalog.



\*\*Inventory Details\*\* — Purpose: single-item deep dive. Primary user: Inventory Manager. Core content: stock history chart, per-location levels, linked supplier(s), linked forecast, AI reorder recommendation if one exists. Key actions: adjust reorder threshold (if backend supports), accept/reject AI recommendation.



\*\*Suppliers\*\* — Purpose: vendor relationship management. Primary user: Procurement. Core content: list, detail with contacts/purchase history/performance. Key actions: create, edit, add contact, new PO from this supplier. Empty state: "No suppliers yet."



\*\*Purchase Orders\*\* — Purpose: procurement workflow (§10, §12). Primary user: Procurement, Inventory Manager. Core content: list by status, detail with line items and status history. Key actions: create, submit, approve, receive (full/partial). Empty state: "No purchase orders" with create action; per-status tabs show their own empty state ("No POs awaiting approval").



\*\*Sales\*\* — Purpose: revenue visibility. Primary user: Sales, Analyst. Core content: sales dashboard, order list, revenue breakdowns. Key actions: filter by period/product/category, drill to order/customer.



\*\*Customers\*\* — Purpose: customer relationship visibility. Primary user: Sales. Core content: list, detail with order history. Key actions: search, drill to order history.



\*\*Forecasts\*\* — Purpose: demand visibility. Primary user: Inventory Manager, Analyst. Core content: forecast chart with labeled prediction intervals, per product/category. Key actions: change period/granularity, compare forecast vs. actual where history allows. Empty state: "Not enough history yet to forecast this product," not a blank chart.



\*\*Analytics\*\* — Purpose: executive rollup. Primary user: Analyst, Admin. Core content: turnover, ABC classification, dead stock, supplier analytics. Key actions: change period, drill into any panel's underlying list. Every figure provenance-labeled per §13.



\*\*Reports\*\* — Purpose: exportable standard reports (§15). Primary user: Analyst, Admin. Key actions: generate, export (CSV/PDF).



\*\*Notifications\*\* — Purpose: system-generated alerts (§16). Primary user: all roles. Key actions: mark read, click through to the relevant resource. Empty state: "You're all caught up."



\*\*Audit Logs\*\* — Purpose: accountability. Primary user: Admin. Core content: chronological, filterable (user/resource/date) log of business- record changes. Key actions: filter, view a specific change's detail (before/after where the backend provides it).



\*\*Settings\*\* — Purpose: tenant configuration. Primary user: Admin. Core content: system-level preferences (currency, timezone, notification defaults) exposed by StockPilot Core — nothing invented beyond what the backend persists.



\*\*User Management\*\* — Purpose: team access control. Primary user: Admin. Core content: user list, invite flow, deactivate. Key actions: invite, assign role, deactivate/reactivate.



\*\*Role Management\*\* — Purpose: permission definition. Primary user: Admin. Core content: role list, permission matrix editor. Key actions: create role, edit permissions, assign default role for new invites.



\*\*Profile\*\* — Purpose: self-service account management. Primary user: all roles. Core content: name, contact info, password/security, notification preferences. Key actions: edit, save.



\*\*AI Assistant\*\* — Purpose: context-aware explanation and recommendation surface, embedded everywhere rather than a standalone page (§14). Primary user: all roles. Key actions: ask, drill into a citation, accept/reject/ snooze a recommendation.



\## 25\\. Future roadmap



\# 



Recorded so it isn't quietly forgotten or quietly built by accident:



\-   Multi-currency support (currently GBP-only, matching the source dataset).

\-   Multi-tenancy — a real architectural change, see `docs/ARCHITECTURE.md` § Future Scalability Considerations.

\-   Native mobile app (responsive web only for now, §21).

\-   Email/push notification channels (in-app only for now, §16).

\-   Real-time collaborative editing on POs/records.

\-   Outcome-tracking on AI recommendations — deliberately not built. This is a static historical dataset, and claiming to learn from real-world outcomes on it would be dishonest, not just unbuilt.

\-   Automated reordering — recommendations remain human-approved by design (§14), not a future toggle to remove that gate.

\-   Advanced report builder beyond the fixed set in §15.

\-   SSO/SAML (StockPilot Core JWT auth only, for now).



\## Keeping this document honest



\# 



If a page ships with reduced scope relative to what's written here, update this document in the same PR rather than letting it silently overstate what exists — this file is what a reviewer or a future session should trust as ground truth for intended behavior.

