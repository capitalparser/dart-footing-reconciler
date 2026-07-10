# P0 Safety and Runtime Integrity — Design Spec

**Date:** 2026-07-10
**Status:** Approved by the user request on 2026-07-10
**Scope:** P0-A engine safety, the small snapshot baseline option, and P0-B display/runtime integrity. Existing Phase 3 statement-footing work remains untouched.

## 1. Outcome

Ship the two P0 slices before resuming Phase 3:

1. `fix/p0-engine-safety`
   - a note-to-note verdict must never compare a cell to itself;
   - `유동` must not consume a `비유동` row;
   - a current report with a concrete consolidation basis must not be paired to a prior report with the opposite concrete basis;
   - the per-company snapshot script accepts an explicit baseline path.
2. `fix/p0-surface-runtime-integrity`, stacked on P0-A
   - `explainable_gap` has its own badge, row treatment, and deterministic row priority;
   - verify-app mounts the complete generated report in an isolated executable document;
   - a non-PyOdide Playwright test proves real report navigation and drilldown clicks work.

Phase 3 (statement footing + R.5, including the metric-semantics correction) is deliberately not implemented in these slices.

## 2. Design Choice

Three approaches were considered:

- inline conditionals in the existing check functions;
- targeted domain seams for note relations and prior matching;
- a full entity-identity rewrite.

The targeted seam is selected. It closes the confirmed P0 holes while creating the natural module boundaries requested for later Note Relation and Prior Matcher deepening. A full identity rewrite would expand the change surface beyond the safety fix; inline guards would leave the same ambiguity distributed across callers.

## 3. P0-A Architecture

### 3.1 Note Relation resolver

Create `note_relations.py` as the single source for note-to-note relation definitions and source-pair eligibility.

Each relation term records:

- section keyword;
- row keyword;
- the optional balance-level intent and explicit exclusions needed to disambiguate nested Korean labels.

The initial disambiguation is intentionally explicit and auditable:

- a balance-level classifier removes `비유동` before looking for a remaining `유동` token; a label containing evidence for both levels is `unknown` and is not a candidate;
- labels containing movement/reclassification terms (`대체`, `재분류`) are `unknown` even when only one level token is present, because they describe a movement rather than a closing balance;
- the generic `법인세` side of the temporary-difference relation excludes sections containing `이연법인세`.

Resolution order:

1. collect candidates through the existing amount extractor;
2. apply the relation term's structural level/exclusion policy;
3. build only `(left, right)` pairs whose `source` values differ;
4. emit no relation when either side is absent or no distinct-source pair exists;
5. leave the existing conservative multiple-candidate agreement policy in `checks_note_note.py`.

The resolver does not change arithmetic, statuses, check IDs, or ordering for valid existing relations. It only controls whether two facts are eligible to be compared.

### 3.2 Prior Matcher

Create `prior_matcher.py` with two responsibilities:

- derive the report's concrete basis (`consolidated`, `separate`) or `unknown`;
- select the compatible prior slice.

Contract:

- concrete current + same concrete prior basis: run the prior harness on that slice;
- concrete current + opposite concrete prior basis: return `None`, so `PriorReportHarness` abstains;
- mixed prior report: select only sections with the current concrete basis;
- current or prior basis `unknown`: abstain;
- only the same proven concrete basis may reach `PriorReportHarness`.

This follows ADR-0012's identity rule that unresolved pairing dimensions become `unknown` and abstain. It is an abstention guard, not a new status; no synthetic `parse_uncertain` result is added.

### 3.3 Synthetic prior regression pin

The workpaper corpus does not provide a prior file, so the corpus gate cannot exercise the mismatch. A synthetic pipeline-level fixture must contain:

- a current consolidated note with a comparative-period amount;
- a prior separate note with the same title/amount;
- a same-basis control case.

The mismatch case must emit zero `prior_year_*` checks; the control must continue to emit its matched prior check.

### 3.4 Snapshot baseline selection

`check_per_company_snapshot.py` gains `--baseline PATH`.

- omitted: use the existing 10-company baseline;
- supplied: both compare and `--update` use exactly that path;
- do not infer the baseline from a manifest or company count.

Explicit selection prevents a wrong corpus/baseline pair from being silently accepted.

## 4. P0-B Architecture

### 4.1 First-class `explainable_gap`

Renderer severity is total and deterministic:

1. `unexplained_gap`
2. `parse_uncertain`
3. `explainable_gap`
4. `matched`
5. `not_tested` / no covering result

`explainable_gap` gets a distinct summary badge, statement row class, account-state badge, sidebar badge, and drilldown callout. It remains outside the “확인 필요” queue; that queue continues to mean unexplained differences plus parse uncertainty.

This is display-layer only. `CheckResult` values, counts, IDs, evidence, order, and engine fingerprints must remain unchanged.

### 4.2 Executable report document in verify-app

The Python engine returns a complete HTML document with its own CSS and inline interaction script. Assigning that string to `innerHTML` parses markup but does not execute inserted scripts.

Add a small `mountReportHtml(resultElement, html, documentRef)` interface that:

- replaces the placeholder with one titled iframe;
- sets `sandbox="allow-scripts"` so the report can run its own interaction code without parent-page authority;
- assigns the complete document to `iframe.srcdoc`;
- returns the iframe for testability.

`verifyFile()` keeps `globalThis.__dartVerifyLastHtml` as the raw Python output for the existing parity contract and delegates visual mounting to this function. The shell gives the iframe a usable responsive height and no border.

### 4.3 Real-click E2E

The new Playwright test must not depend on PyOdide assets. It will:

1. generate a small report with the real Python renderer;
2. serve the repository over loopback HTTP;
3. disable verify-app auto boot;
4. import `app.js` and mount the generated HTML;
5. click a real report navigation item;
6. click a real verified row;
7. assert the target panel and drilldown become visible.

The existing full PyOdide parity test remains conditional on its vendored assets. The new runtime-click test is unconditional when the repository's pinned JS test dependencies and browser are installed.

## 5. Safety and Compatibility

- Footing and reconciliation remain separate harnesses.
- All surviving evidence retains its original source location.
- No MCP dependency is introduced.
- The default snapshot CLI remains backward compatible.
- P0-B cannot mutate engine verdicts.
- No baseline JSON is updated unless an intentional delta is separately accepted.

### Deferred mixed-scope risk

`split_report_by_scope()` intentionally keeps a single concrete scope together with unscoped statement sections so statement-to-note checks can use unscoped financial statements. A blanket split would destroy that established path. Consequently, a report containing concrete and unscoped notes can still expose a cross-scope note-relation candidate. This pre-existing case is not changed in P0-A; it requires a scope-aware fact identity that distinguishes genuinely shared unscoped statements from note candidates, with its own corpus gate.

## 6. Gates

P0-A requires:

- focused RED/GREEN tests;
- full `pytest` twice and Ruff;
- before/after 10-company and expansion-corpus runs;
- check-level `note_note_match` fingerprint review;
- per-company snapshot checks against both explicit baselines;
- zero destroyed genuine matches and zero new false matches.

P0-B requires:

- focused Python renderer tests;
- Vitest for the mount contract;
- Playwright real-click E2E;
- full Python suite and Ruff;
- engine fingerprint identity, because this slice is presentation/runtime only.
