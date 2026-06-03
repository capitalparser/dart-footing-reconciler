# Agent Work Integration Ledger - 2026-06-03

## Purpose

This ledger records recent agent-produced work as feature units so future work
can consider related changes together without applying the same behavior twice.

The branch is currently `audit-workpaper-note-reconciliation`, ahead of origin
by 25 commits at `c61e669`.

## Current Git Hygiene Findings

- Main worktree is clean at the time this ledger was created.
- A stale prunable worktree registration exists:
  `/private/tmp/dfr-head-compare`.
- A zero-byte `.git/objects/maintenance.lock` exists. This is distinct from
  `index.lock` and `HEAD.lock`; it does not currently block status or commits.
- Multiple background tools inspect this repo with Git commands, including
  editor/Codex/Claude status scans and Git fsmonitor. Future commit work should
  check for stale locks before assuming an agent explicitly created them.

## Canonical Feature Units

| Feature key | Status | Canonical commits | Primary files | Notes |
|---|---|---|---|---|
| `local-report-footing-input` | reflected | `3ba7ba0` | `src/dart_footing_reconciler/local_report.py`, `src/dart_footing_reconciler/cli.py`, `tests/test_cli.py`, `tests/test_package.py` | Local DSD/HTML attachment loading, Korean encoding decode, PDF/network rejection, package export. Do not add a second local loader; extend this module. |
| `reconciliation-cashflow-evidence-tightening` | reflected | `f40abd2` | `src/dart_footing_reconciler/checks_reconciliation.py`, `src/dart_footing_reconciler/reconciliation_inputs.py`, `tests/test_checks_reconciliation.py` | Covers implausible balance candidates as `parse_uncertain`, accumulated depreciation disposal adjustments, and combined PPE/ROU CFS acquisition handling. Future cash-flow fixes must check movement roles here first. |
| `footing-evidence-source` | reflected | `7c3c612` | `src/dart_footing_reconciler/footing.py`, `tests/test_footing.py`, `docs/superpowers/plans/2026-06-02-footing-evidence-source.md` | Footing results now preserve deterministic table/row/column evidence coordinates. Parser line locations remain a separate future feature. |
| `leadsheet-ui-advisory` | reflected | `fc327ea`, `f5a66b6` | `src/dart_footing_reconciler/report_html.py`, `tests/test_cli_workpaper.py`, `docs/adr/0002-claude-direct-html-ui-implementation.md` | Note-number hover triggers and validation advisory are already implemented. ADR records that direct UI implementation was a one-time exception. |
| `243-baseline-remap` | reflected | `7e72416`, `344d796`, `3408fd8`, `4713478`, `02bd868` | `docs/work-orders/2026-05-31-codex-handoff-reconciliation-logic.md`, `docs/validation/2026-06-01-ab-triage-243-baseline.md`, `HANDOFF.md` | The accepted reproducible local baseline is 243 primary checks / 190 matched / 53 unresolved. The historical 575 baseline is documentation context, not the current acceptance baseline. |
| `audit-worksheet-reporting-core` | reflected, broad | `796f8d5` | many modules under `src/dart_footing_reconciler/`, many tests, report/work-order docs | Large integration commit that introduced reviewer-facing workpaper corpus/reporting and many reconciliation modules. Treat as a broad baseline, not as a model for future mixed-scope commits. |
| `superpowers-artifact-ignore` | reflected | `c61e669` | `.gitignore` | `.superpowers/` is ignored as local agent workspace state. Do not commit generated brainstorm/session state. |
| `election-workpaper-split` | reverted / do not merge here | `d5760b1` through `15e03d1`, reverted by `c8ed18d` | removed `src/election_workpaper/`, removed related tests/docs | This domain was intentionally removed from the DART reconciler repo. Do not reintroduce election workpaper files into this project. |

## Duplicate-Risk Map

| Area | Risk | Guardrail |
|---|---|---|
| Local report input | Another agent may add a separate CLI-only HTML/DSD loader. | Route through `load_local_report()` and `foot_local_report()` in `local_report.py`. |
| Footing source locations | Parser line/DOM source work could duplicate footing coordinate evidence. | Keep `FootingEvidence.source` as local table coordinates until parser-level source locations exist; then bridge rather than replace. |
| Cash-flow movement roles | Different agents may add new role names for the same adjustment. | Before adding roles, search `checks_reconciliation.py`, `reconciliation_inputs.py`, and tests for equivalent semantics. |
| PPE/ROU acquisition | Plain PPE acquisition and combined PPE+ROU CFS acquisition intentionally differ. | Only include ROU acquisition when `_is_combined_ppe_rou_acquisition_cfs_line()` is true. |
| Baseline metrics | 575-check historical artifacts can be mistaken for current acceptance data. | Use 243-check reproducible local baseline for current acceptance unless cash-flow primary extraction is restored and revalidated. |
| UI/report work | Prior direct UI implementation created process risk. | Future UI changes should be planned and reviewed separately; keep report HTML changes test-backed. |
| Cross-domain work | Non-DART domains can leak into this repo. | Treat `c8ed18d` as the boundary: election workpaper belongs elsewhere. |

## Integration Rules For Future Agents

1. Start by assigning a feature key before editing.
2. Search for the feature key's behavioral surface:
   `rg "<check_id>|<movement_role>|<cli command>|<field name>" src tests docs`.
3. If equivalent behavior already exists, add tests or refine the canonical
   implementation instead of creating a parallel module or role.
4. Keep commits scoped to one feature key. If a file change serves two feature
   keys, split the patch or commit the parts separately.
5. Do not revive reverted cross-domain work in this repository.
6. Before committing, check `git status --short --branch`, `find .git -maxdepth 2
   -name '*.lock' -print`, and `git worktree list --porcelain`.
7. For docs-only diagnostics, keep code untouched and make a docs-only commit.

## Open Cleanup Items

- Prune stale worktree registration for `/private/tmp/dfr-head-compare`.
- Decide whether to remove stale `.git/objects/maintenance.lock` after checking
  whether Git maintenance is currently active.
- Consider adding a lightweight `docs/validation/current-feature-ledger.md`
  pointer if this ledger becomes the ongoing coordination artifact.

