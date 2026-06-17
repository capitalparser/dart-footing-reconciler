# HANDOFF — parse_uncertain reason-code instrumentation

**Author (design):** Claude (Opus 4.8) · **Implementer:** Codex · **Date:** 2026-06-17
**Tier:** 3 (multi-file, ~8 files). **Risk:** low (additive metadata) IF the invariant holds.

## Goal

Every check that abstains with `status == PARSE_UNCERTAIN` must carry a machine
`parse_uncertain_reason` **code** so the 파싱 진단 panel and any triage can tell
*legitimate abstention* (e.g. prior-period mirror tables) apart from *recoverable
parser gaps*. Today all 500 corpus parse_uncertain render `UNKNOWN`: the literal
`status=PARSE_UNCERTAIN` is set at 3 sites and reason codes at only 4 sites
(`checks_statement_ties.py`), while the real producers compute status as a
variable and pass **free-text** reasons.

This is the prerequisite that unblocks `accuracy-backlog.md` §4a — do NOT try to
*reduce* parse_uncertain in this task. Just classify.

## Reason code enum (use these; they already drive `report_html._uncertain_reason_text`)

- `LABEL_NOT_FOUND` — account/label not located in the filing.
- `LOW_CONFIDENCE_MATCH` — a candidate was found but confidence is low (e.g.
  `candidate.confidence < 0.7`, ambiguous layout/orientation).
- `AMBIGUOUS_MULTIPLE` — multiple equally-confident candidates.
- `COLUMN_NOT_DETECTED` — current/prior column could not be distinguished.
- `TABLE_NOT_FOUND` — the statement/note section/table is absent.
- `AMOUNT_PARSE_FAILED` — row found but a required amount is missing/unparseable
  (e.g. "missing beginning or ending candidate", blank subcolumn).

Add a NEW code only if a site genuinely fits none of these; if you add one, also
extend `report_html._uncertain_reason_text` with its Korean gloss and say why in
the PR.

## Where parse_uncertain originates (the work map)

Confirmed by grep on `src/dart_footing_reconciler/`:

- **`formula_discovery.py` (~44 sites — the bulk).** Returns `VerificationFormula`
  with `PARSE_UNCERTAIN` and an existing free-text `reason` (last positional arg),
  e.g. `"low-confidence layout or orientation evidence blocks matched formula"` →
  `LOW_CONFIDENCE_MATCH`; `"missing beginning or ending candidate"` →
  `AMOUNT_PARSE_FAILED`. Map each site's free-text to a code. Thread the code from
  `VerificationFormula` through to the `CheckResult.parse_uncertain_reason` at the
  conversion boundary (find where VerificationFormula → CheckResult happens).
- **`checks_totals.py:38`** — `status = PARSE_UNCERTAIN if _requires_total_check(table) else NOT_TESTED`.
  Reason: a total check is required but the total could not be footed/parsed →
  pick `AMOUNT_PARSE_FAILED` or `TABLE_NOT_FOUND` per the local condition.
- **`checks_note_note.py`, `checks_reconciliation.py`, `footing.py`, `scan.py`,
  `label_resolver.py`** — 2 occurrences each (an import + one assignment/return).
  Inspect each, map to a code.
- **`checks_statement_ties.py`** — already instrumented (LABEL_NOT_FOUND + a
  computed `uncertain_reason`). Leave as the reference pattern; only touch if a
  branch still leaks an unset reason.

## Hard invariant (this is the gate — do not merge if it fails)

This task changes ONLY the reason field. The five status counts must be byte-identical.

```
uv run dart-footing workpaper-corpus \
  out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json \
  out/corpus/run_pu_after
```

Then compare `out/corpus/run_pu_after/corpus_result.json` to baseline
`out/corpus/run_b5_before/corpus_result.json`. These MUST be unchanged:

| metric | required |
|---|---|
| matched | 4739 |
| explainable_gap | 10 |
| unexplained_gap | 460 |
| parse_uncertain | 500 |
| not_tested | 2966 |
| failed_samples | 0 |
| primary_matched | 110 |
| note_assertion_matched | 863 |

If any count moves, you changed behavior, not just metadata — stop and report.

## Deliverable (what "done" means)

1. Every PARSE_UNCERTAIN raise site sets a `parse_uncertain_reason` code.
2. Corpus invariant above holds exactly.
3. The 500 are now classified. Produce the distribution and put it in the PR body:
   ```
   grep -ohE 'badge badge-unc">[A-Z_]+' out/corpus/run_pu_after/reports/*.html \
     | sed 's/.*">//' | sort | uniq -c | sort -rn
   ```
   `UNKNOWN` should be near zero (ideally 0). Any residual UNKNOWN must be named
   (which site, why unmapped).
4. TDD: add tests under `tests/` asserting representative sites emit the right
   code (e.g. low-confidence rollforward → `LOW_CONFIDENCE_MATCH`; missing
   beginning/ending → `AMOUNT_PARSE_FAILED`; required-but-unfootable total →
   its code). Keep the existing `checks_statement_ties` tests green.

## Tooling rules (non-negotiable)

- Use `uv run` for ALL python/pytest/ruff. Bare `pytest` hits a leaked sibling
  venv and gives false lxml import failures.
- Filter `uv` noise with `| grep -v "^warning:"` when reading output.
- Branch `feat/parse-uncertain-reason-codes`; open a PR; do NOT merge until the
  invariant gate passes and tests are green.

## Out of scope

- Reducing parse_uncertain (that is a later, per-code triage — §4a).
- Any change to the 5-status logic, matching thresholds, or taxonomy.
- report_html structure (cockpit compliance already merged in PR #9).
