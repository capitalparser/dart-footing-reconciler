# P0 Safety and Runtime Integrity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Follow red-green-refactor for every behavior change and do not update corpus baselines without explicit acceptance of the delta.

**Goal:** Close the confirmed false-match and browser-runtime P0 holes before resuming the existing Phase 3 statement-footing plan.

**Architecture:** Add narrow `note_relations` and `prior_matcher` seams for engine identity decisions. Keep P0-B display-only, and execute the full generated report as an isolated iframe `srcdoc` document rather than an inert HTML fragment.

**Tech Stack:** Python 3, dataclasses, pytest, uv, Ruff, vanilla ES modules, Vitest/jsdom, Playwright/Chromium.

---

## Task 1: Note Relation RED pins

**Branch:** `fix/p0-engine-safety`

**Files:**
- Modify: `tests/test_checks_note_note.py`

- [ ] Add a single-cell temporary-difference fixture whose section matches both rule sides; assert no `tax_temporary_difference` result is emitted.
- [ ] Add a lease fixture containing only a `비유동` row; assert it cannot satisfy the `유동` side and emits no lease relation.
- [ ] Add a lease fixture with a `유동성 대체`/`재분류` movement row; assert it cannot satisfy a balance-level side.
- [ ] Add a lease fixture with distinct `유동` and `비유동` source cells; assert any emitted evidence pair uses different sources.
- [ ] Add a valid two-note tax fixture to pin the genuine relation path.
- [ ] Run the focused tests and confirm the new tests fail for the expected same-source/boundary reasons:

```bash
UV_CACHE_DIR=/tmp/ruffe-uv-cache uv run pytest tests/test_checks_note_note.py -v
```

## Task 2: Note Relation minimal implementation

**Files:**
- Create: `src/dart_footing_reconciler/note_relations.py`
- Modify: `src/dart_footing_reconciler/checks_note_note.py`
- Test: `tests/test_checks_note_note.py`

- [ ] Define frozen relation term/rule/candidate records and move the rule registry into the new module.
- [ ] Classify `유동`/`비유동` only when exactly one level is proven, and apply the explicit `법인세`/`이연법인세` section exclusion.
- [ ] Construct only distinct-source pairs and return no candidates if no valid pair exists.
- [ ] Make `_candidate_match` select a deterministic distinct pair while retaining the existing conservative all-candidates-agree rule.
- [ ] Run focused tests to GREEN, then the note/check pipeline regression group.

## Task 3: Prior basis RED pins

**Files:**
- Modify: `tests/test_check_pipeline.py`

- [ ] Add a synthetic current-consolidated/prior-separate fixture with otherwise matching prior disclosure values.
- [ ] Assert the mismatched fixture emits no `prior_year_*` result.
- [ ] Add or retain a same-basis control and assert a matched prior result is emitted.
- [ ] Confirm the mismatch test fails because the current fallback passes the entire prior report.

```bash
UV_CACHE_DIR=/tmp/ruffe-uv-cache uv run pytest tests/test_check_pipeline.py -k prior -v
```

## Task 4: Prior Matcher minimal implementation

**Files:**
- Create: `src/dart_footing_reconciler/prior_matcher.py`
- Modify: `src/dart_footing_reconciler/check_pipeline.py`
- Test: `tests/test_check_pipeline.py`

- [ ] Implement concrete-basis derivation and compatible prior slicing.
- [ ] Return `None` for a proven opposite-basis prior report.
- [ ] Abstain whenever either side's basis is unknown; only a proven same concrete basis reaches the prior harness.
- [ ] Replace `_matching_prior_slice` and `_slice_consolidation_basis` duplication with the new module interface.
- [ ] Run focused and pipeline tests to GREEN.

## Task 5: Explicit snapshot baseline option

**Files:**
- Modify: `tests/test_per_company_snapshot.py`
- Modify: `scripts/check_per_company_snapshot.py`

- [ ] RED: call `main()` with `--baseline <tmp path> --update`, prove the selected path changes and the monkeypatched default does not; then compare against the selected path.
- [ ] GREEN: add `--baseline PATH`, defaulting to the existing `BASELINE`, and route every read/write/message through `baseline_path`.
- [ ] Confirm the legacy invocation still passes.

```bash
UV_CACHE_DIR=/tmp/ruffe-uv-cache uv run pytest tests/test_per_company_snapshot.py -v
```

## Task 6: P0-A corpus hard gate

- [ ] Run both manifests after implementation in `/tmp` with `--no-fetch --results-only`.
- [ ] Compare post-change note-relation fingerprints to the stored pre-change capture.
- [ ] Triage every removed/changed item; specifically confirm the known same-cell matched result is removed and no genuine match is destroyed.
- [ ] Run the 10-company default snapshot:

```bash
UV_CACHE_DIR=/tmp/ruffe-uv-cache uv run python scripts/check_per_company_snapshot.py /tmp/ruffe-p0a-after-10/corpus_result.json
```

- [ ] Run the expansion snapshot with the new option:

```bash
UV_CACHE_DIR=/tmp/ruffe-uv-cache uv run python scripts/check_per_company_snapshot.py \
  /tmp/ruffe-p0a-after-expansion/corpus_result.json \
  --baseline tests/baselines/per_company_counts_2026-06-22-expansion.json
```

- [ ] If the intentional false-match removal changes a committed count, report the delta; do not rewrite a baseline in this task.
- [ ] Run `pytest -q` twice and Ruff.

## Task 7: First-class explainable status RED pins

**Branch:** `fix/p0-surface-runtime-integrity`, stacked after P0-A is cleanly recorded.

**Files:**
- Modify: `tests/test_report_html_evidence.py`

- [ ] Add a row covered by both `matched` and `explainable_gap`; assert the explainable result owns the row.
- [ ] Assert the rendered row, account state, summary badge, and drilldown use explainable-specific classes/text rather than uncertain styling.
- [ ] Confirm the tests fail under the current partial severity map and fallback badge helpers.

## Task 8: First-class explainable status implementation

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`

- [ ] Complete the severity map without changing any `CheckResult`.
- [ ] Add explainable row, badge, account, sidebar, and callout mappings plus CSS.
- [ ] Keep the attention queue definition unchanged.
- [ ] Run renderer tests and a status-fingerprint identity assertion.

## Task 9: Executable verify-app mount RED pin

**Files:**
- Modify: `tests/js/dart_verify_app.test.js`

- [ ] Expect verification to create one titled, sandboxed iframe whose `srcdoc` equals the returned complete HTML.
- [ ] Assert the raw `__dartVerifyLastHtml` parity value remains unchanged.
- [ ] Confirm the test fails because the current code uses `innerHTML`.

## Task 10: Executable verify-app mount implementation

**Files:**
- Modify: `static/dart-verify/app.js`
- Modify: `static/dart-verify/index.html`
- Create: `package.json`
- Create: `package-lock.json`
- Modify: `.gitignore`

- [ ] Export the narrow `mountReportHtml` interface.
- [ ] Mount a `sandbox="allow-scripts"` iframe with `srcdoc` and replace the placeholder atomically.
- [ ] Route `verifyFile()` through the mount function while retaining the raw parity global.
- [ ] Add responsive iframe sizing in the shell.
- [ ] Stop ignoring the manifests and pin the JS test commands/dependencies in `package.json` plus `package-lock.json`.
- [ ] Run Vitest to GREEN.

## Task 11: Real-click Playwright E2E

**Files:**
- Modify: `tests/e2e/dart-verify-parity.spec.js`
- Modify only if required: `playwright.config.ts`

- [ ] Generate a tiny interactive HTML report through the real Python renderer.
- [ ] Serve repository static assets on loopback and disable app auto boot.
- [ ] Mount through `mountReportHtml`, then click a report nav control and an audited row.
- [ ] Assert the requested panel and drilldown become visible inside the iframe.
- [ ] Keep this test independent from the optional PyOdide distribution assets.
- [ ] Run the focused E2E and the existing parity spec (the latter may remain explicitly skipped when assets are absent).

## Task 12: Final verification and review

- [ ] Run focused Python, JS, and E2E suites.
- [ ] Run full `pytest -q` twice and `ruff check`.
- [ ] Render one real cached report and manually/automatically inspect the explainable badge and iframe interactions.
- [ ] Dispatch a spec-compliance review and an adversarial code-quality review; resolve all P0 findings.
- [ ] Report branches, changed files, intentional corpus deltas, test tails, and any remaining Phase 3 work. Do not push or merge without a separate explicit request.
