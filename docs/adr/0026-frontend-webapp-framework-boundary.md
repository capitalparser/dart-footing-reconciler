# 0026. Frontend webapp framework boundary

**Date:** 2026-06-30
**Status:** Accepted

## Context

The project currently has two user-facing surfaces:

- `static/dart-verify/`: local browser shell for file upload and PyOdide execution.
- `report_html.py`: generated validation report with source evidence, drilldowns, and confirmation queues.

The user-facing direction is moving toward a webapp, but the adoption criterion is user convenience,
not framework preference. The validation engine must remain Python-owned and accuracy-first. ADR-0005
already rejected a JavaScript verification-engine port because it would create duplicate logic and
accuracy drift.

## Decision

Do not migrate the current verification report output wholesale to React or Next.js now.

Use this boundary:

- Keep Python as the validation engine and source-of-truth renderer for standalone HTML report export.
- Keep the current static browser shell for offline single-file verification while it only needs upload,
  local execution state, and a generated report preview.
- Introduce a React webapp layer when users need an interactive workbench: multi-report dashboard,
  saved review state, reviewer assignments, issue triage, cross-report comparison, or persistent
  drilldown navigation.
- Prefer Vite React for the first webapp layer because it is simpler, can remain local/offline-friendly,
  and matches the current PyOdide/static asset delivery model.
- Consider Next.js only when the product explicitly needs server-backed convenience: authenticated
  users, shared workspaces, database-backed run history, server-side ingestion, or hosted deployment.

## Dashboard UI rule

The front dashboard should be card-first and low-text:

- Cards represent destinations, not decoration.
- Each card maps to a concrete page or panel such as dashboard, progress status, confirmation queue,
  financial statements, notes, or next tasks.
- The dashboard should expose counts and status labels first; explanatory text belongs in drilldowns
  or detail pages.
- Desktop is the primary target for now. Mobile layout can stay usable but is not an optimization
  priority in this phase.

## Consequences

- Short term: improve the existing HTML and static shell without adding build complexity.
- Medium term: add `apps/workbench/` or equivalent as a React/Vite app only when the workflow needs
  stateful review and cross-page navigation.
- Long term: move to Next.js only if the deployment model becomes a hosted, multi-user product rather
  than a local verification tool.
