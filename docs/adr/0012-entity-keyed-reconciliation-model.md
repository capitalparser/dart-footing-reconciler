# 0012. Entity-keyed reconciliation model — Consolidation Basis / Report Period / Balance Level as first-class dimensions

**Date:** 2026-06-24
**Status:** Accepted (design). Implementation is incremental/strangler, corpus-gated; first slice = B-2b.
**Inputs:** grill-with-docs whole-tool reframe (user: "전체 툴 차원에서 entity/속성/관계 식별 + 룰베이스·데이터드라이븐 하이브리드"). Resolves the ADR-0011 B-2b residual at the model level.
**Companion:** `docs/domain-model.md` (entity catalog + ERD + rule/data boundary); `CONTEXT.md` terms Consolidation Basis, Balance Level, Report Period.

## Context

The reconciliation engine pairs a statement line to a note row per **Account** (`taxonomy`) but otherwise on a **flat** model: `check_fs_note_matches` takes `fs_hits[0]` and one ranked note row. This is arbitrary along three dimensions the documents actually carry:

- **Consolidation Basis** (연결/별도) — a single DART report holds both; the code already stores it as `ReportSection.scope` but pairing does not key on it.
- **Report Period** (당기/전기) — handled only in `checks_prior_*`, not a line/cell attribute.
- **Balance Level** (유동/비유동) — exists only as a *caller intent* (`Target Amount Role.current_/noncurrent_portion`), not as a property of the line.

Consequence (the ADR-0011 B-2b residual): 대한항공/CJ lease pair to the right account but the wrong **level** — `fs_hits[0]` is the current portion while the note row is the total. Verified: 대한항공 note `비유동 리스부채` 8,744,564,000,000 == FS noncurrent 8,744,563,527,885; CJ FS current 465,381,950,000 + noncurrent 1,643,311,460,000 == note 기말 2,108,693,410,000. The fix is structural: pairing must be keyed on these dimensions.

The user reframed this whole-tool: model the domain as explicit entities/attributes/relationships and realize the **rule-based + data-driven hybrid** that `CONTEXT.md` already *designed* (signature-driven triggering + deterministic attempts; "the data-driven form of 성격마다 파싱") but only *partially adopted*.

## Decision

1. **Adopt a four-dimension pairing key:** `(Account × Consolidation Basis × Report Period × Balance Level)`. A `note_to_bs` reconciliation pairs lines/rows agreeing on the key; cross-basis / cross-period / cross-level pairing is forbidden.
2. **Promote Balance Level and Report Period to first-class attributes** of `StatementLine`/`NoteRow` (alongside the already-present Consolidation Basis). Inference is data-driven (label tokens + BS section position); unresolved → `unknown` → **abstain**.
3. **Re-define Target Amount Roles `current_portion`/`noncurrent_portion` as intents resolved against Balance Level** (the line's data), not as the level's home.
4. **Canonicalize "Consolidation Basis"** as the term for the consolidated/separate axis the code's `.scope` field carries (rename `.scope → .consolidation_basis` is deferred, non-blocking). Keep **Company Scope** = {nonfinancial, financial} unchanged (ADR-0003).
5. **Bounded deterministic aggregation** for total-only notes: pair `Σ{current, noncurrent of the same Account+Basis+Period}` to the note `total` row — exactly two levels, one basis, one period; never an open sum.
6. **Formalize the rule/data boundary** (`domain-model.md` §4): declarative knowledge-as-data + input-shape-adaptive deterministic strategy selection + a deterministic rule engine. **Confidence may only downgrade (`matched→parse_uncertain`) or gate (abstain); it can never create a `matched` verdict** → no false match from probability.
7. **Strangler migration, corpus-gated.** The model is the target; `taxonomy.py` + `checks_*.py` stay load-bearing and migrate one slice at a time under the corpus hard gate. No big-bang rewrite.

## Alternatives considered

- **Keep flat + role; handle B-2b only in the locator/check.** Rejected: level stays non-queryable, the arbitrariness recurs for every level-split account, and the entity model stays implicit (weakest against the recurring B-4/B-5/B-2b family).
- **Fully adopt the signature/semantic engine (ADR-0003) now.** Rejected: the accuracy is load-bearing in `taxonomy`+`checks`; a big-bang swap risks regressing the corpus-gated accuracy (the most expensive mistake under `accuracy > elegance`).
- **Data-driven = statistical/ML pairing.** Rejected on doctrine: an audit verdict must be deterministic and never a false match; the corpus is a gate/oracle and a source for *curating* declarative rules, not a training set.

## Consequences

- Enables B-2b *safely* (level-matched pairing + bounded summation + abstain), and gives the B-4/B-5 family a principled home.
- `StatementLine`/`NoteRow` gain `level` (+ explicit `period`) attributes; inference code + tests added incrementally.
- `.scope → .consolidation_basis` rename is owed (deferred refactor; `domain-model.md` notes it).
- Each migration slice must pass the corpus hard gate (matched ↑/flat, gaps fall only from removed FPs, zero genuine destroyed) and cross-model review — same loop as PR #19.
- The signature/semantic layer stays diagnostic until a slice proves a piece gate-positive.
