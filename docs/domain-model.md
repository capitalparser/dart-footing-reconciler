# Domain Model — entities, attributes, relationships, rule/data boundary

**Date:** 2026-06-24 (grill-with-docs, whole-tool reframe)
**Status:** Living artifact. Makes the *load-bearing* entity-relationship model explicit and maps the rule-based ↔ data-driven boundary. **Documentation only — no code change.** Terms are defined in `CONTEXT.md`; this file shows their structure and relationships. Migration onto this model is incremental and corpus-gated (strangler); the first slice is B-2b (see ADR-0012, ADR-0011).

> Doctrine guardrails (load-bearing): `domain accuracy > technical elegance`, `abstain over guess`, **an audit verdict must never carry a false match**, `all arithmetic deterministic Python (no LLM judgment)`, `every change corpus-gated`. The model below must never enable a probabilistic *verdict*.

## 1. Dimensions (value objects — the pairing key)

These four are the axes that make a reconciliation pairing well-defined. The flat model lost them, which is why `fs_hits[0]` was arbitrary.

| Dimension | Values | Source (data-driven inference) | Code today |
|---|---|---|---|
| **Account** | taxonomy keys (리스부채, 차입금, 무형자산, …) | `taxonomy.py` alias match | `account_key` on lines/notes |
| **Consolidation Basis** (연결기준) | `consolidated` / `separate` | TOC heading / section markers (연결·별도) | `ReportSection.scope` (rename → `.consolidation_basis` deferred) |
| **Report Period** (당기/전기) | `current` / `prior` | column position (당기 vs 전기) | implicit in `checks_prior_*`; to be made a line/cell attribute |
| **Balance Level** (유동/비유동) | `current` / `noncurrent` / `total` / `unknown` | label tokens (유동성/비유동) + BS section position | `Target Amount Role` (current_/noncurrent_portion) only — to become a line attribute |

**Pairing key = `(Account × Consolidation Basis × Report Period × Balance Level)`.** A `note_to_bs` check pairs lines/rows that agree on the key; cross-basis / cross-period / cross-level pairing is forbidden.

Orthogonal labels (not pairing keys): **Company Scope** `{nonfinancial, financial, unknown}` (confidence/statistics only, never dispatch — ADR-0003); **Confidence** `[0,1]`; **Source Location**.

## 2. Entities & attributes

### Instance entities (per-filing data, parsed)
| Entity | Key attributes | Notes |
|---|---|---|
| **Filing / FullReport** | company, source, sections[] | one DART business report (holds BOTH bases) |
| **ReportSection** | section_id, kind(statement\|note), note_no, **consolidation_basis** | `document.py:ReportSection` |
| **StatementLine** | account, label, amount, **basis, period, level**, source, confidence | FS row (BS/PL/CF/SCE) |
| **NoteRow** | account, note_no, label, amount, unit, role, **basis, period, level**, source, confidence | note table row |
| **LocatedAmount** | (row,col), raw+scaled amount, component_sources, confidence, source | Canonical Amount Locator output |

### Reference / knowledge entities (declarative data — the "data-driven" knowledge base)
| Entity | Holds | Code today |
|---|---|---|
| **Account (taxonomy entry)** | key, display_name, aliases, note_title_aliases, note_amount_aliases, is_balance_sheet, signed | `taxonomy.py:TAXONOMY` |
| **Layout Archetype** | classify key + bound cell-selection strategy | `layout_variants.py` |
| **Verification Signature** | observable table property + confidence emitter | `signatures.py` (3/17 emitted) |
| **Verification Attempt** | required signatures + thresholds → an arithmetic check | registry (partially built) |
| **Target Amount Role** | caller intent (7, closed): period_end_balance, net_carrying_amount, cash_like_movement, disclosed_total, expense_allocation, current_portion, noncurrent_portion | `amount_locator.TargetAmountRole` |
| **Reconciliation/Footing Axis** | direction of a check (note_to_bs, note_to_cf, internal, …) | `CONTEXT.md` |

### Result entities
| Entity | Attributes | Notes |
|---|---|---|
| **ReconciliationCheck** (CheckResult) | check_id, type, **status**, expected, actual, difference, tolerance, evidence[], source | one result row |
| **Status** | `matched / explainable_gap / unexplained_gap / parse_uncertain / not_tested` | SSOT = `checks.ALL_STATUSES` |

## 3. Relationships (ERD)

```
Filing ─1:N─ ReportSection
   ReportSection{kind=statement} ─1:N─ StatementLine
   ReportSection{kind=note}      ─1:N─ NoteRow
   ReportSection ─has─ ConsolidationBasis

StatementLine ─N:1─ Account            NoteRow ─N:1─ Account
StatementLine ─has─ {Basis, Period, Level, SourceLocation, Confidence}
NoteRow       ─has─ {Basis, Period, Level, Role, SourceLocation, Confidence}

ReconciliationCheck
   ─pairs─ StatementLine(aggregate)  ⇄  NoteRow(aggregate)
   ─keyed on─ (Account, Basis, Period, [Level])
   ─runs along─ ReconciliationAxis
   ─produces─ Status (+ evidence, source)

Account ─1:N─ TargetAmountRole (reconciliation intents)
VerificationAttempt ─triggered by─ VerificationSignature(s)
LayoutArchetype ─binds─ cell-selection strategy → LocatedAmount
TargetAmountRole ─resolved against─ BalanceLevel (current_/noncurrent_portion → Level)
```

**Pairing cardinality.** `note_to_bs` is normally 1:1 on the full key. The level dimension introduces a **1:N aggregate** case: when the note discloses only a `total` row, the check pairs `Σ{StatementLine | same Account+Basis+Period, Level∈{current,noncurrent}}` to that one NoteRow — a *bounded, deterministic* aggregation (exactly the two levels of one basis+period), never an open sum.

## 4. Rule-based ↔ data-driven boundary (the hybrid)

Three doctrine-safe meanings of "data-driven"; **none** is ML/probabilistic verdict.

| Layer | Kind | What | Examples |
|---|---|---|---|
| **Knowledge-as-data** | declarative DATA, corpus-curated by humans | the reference entities in §2 | taxonomy aliases, layout archetypes, signature library, attempt registry, level/basis tokens |
| **Input-shape-adaptive** | deterministic strategy selection | pick the deterministic strategy from the *structure of this filing* | locator per-archetype strategy; B-2b: level-split note → level-match, total-only note → bounded sum |
| **Rule engine** | deterministic Python | the actual arithmetic & decisions | footing, pairing-by-key, bounded summation, tolerance compare, abstain |

**Confidence** is the only probabilistic element and it is *constrained*: it can only **downgrade** (`matched → parse_uncertain`) or **gate** (`attempt_minimum → abstain`). It can never *create* a `matched` verdict. → no false match from probability.

**Explicitly out of bounds:** statistical/ML inference of pairings or amounts; the corpus is the **gate/oracle** + a **source for curating declarative rules**, never a training set for runtime decisions.

## 5. How B-2b consumes the model (first entity-keyed slice)

`note_to_bs` for level-split liability accounts (lease, borrowings, bonds):
1. Group StatementLines by `(Account, Basis, Period)`; resolve each line's `Balance Level`.
2. Inspect the note's disclosure shape (input-shape-adaptive):
   - **level-split note** (유동 리스부채 + 비유동 리스부채 rows): pair `current↔current`, `noncurrent↔noncurrent` (direct, no sum).
   - **total-only note** (기말 / single total): pair `Σ(current+noncurrent of same Basis+Period) ↔ total`.
3. If a line/row's level is `unknown`, or the same-key group is incomplete/ambiguous → **abstain** (not_tested), never guess.

False-match guard: summation is bounded to exactly the two levels of one (Account, Basis, Period); it never spans bases, periods, or pulls extra lines. Every change corpus-gated (matched ↑/flat, gaps fall only from removed FPs, zero genuine destroyed).

## 6. Migration stance

This model is the **target**, reached by strangler migration. `taxonomy.py` + `checks_*.py` remain load-bearing; each slice migrates one axis/account onto the entity-keyed pairing under the corpus hard gate. The signature/semantic engine (ADR-0003) stays diagnostic until a slice proves a piece of it gate-positive. No big-bang rewrite (would risk the accuracy the corpus baselines protect).
