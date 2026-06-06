# Context

## Project Profile
- 개요: DART 공시의 주석 수치, 현금흐름, 증감표를 파싱해 footing과 reconciliation 차이를 점검하는 도구입니다.
- 목적: 감사/분석 과정에서 수치 검산과 설명 가능한 차이 분류를 자동화해 사람의 검토 시간을 줄입니다.

This project builds an audit-grade footing and cash flow reconciliation engine for Korean DART DSD/HTML filings.

## Ubiquitous Language

### DART DSD/HTML

The primary source format for Korean regulatory filings. The project starts from DSD/HTML because table structure is more reliable than PDF OCR for audit-style reconciliation.

### Footing

An internal arithmetic check inside one table. The canonical movement formula is:

```text
beginning balance + increases - decreases +/- transfers +/- other movements = ending balance
```

Footing proves table arithmetic only. It does not prove cash flow statement agreement.

### Cash Flow Reconciliation

Comparison between note-derived cash-like movements and statement of cash flows line items. The comparison must consider non-cash movements and classification differences.

### Cash-Like Movement

A movement in a note table that is expected to correspond to a cash flow statement line item, such as cash acquisition of PPE, proceeds from sale of assets, borrowing proceeds, or borrowing repayments.

### Non-Cash Movement

A movement that changes note balances but should not be treated as cash flow. Examples include depreciation, amortization, transfers, foreign exchange, lease additions, reclassifications, fair value movements, and unpaid acquisitions.

### Explainable Gap

A difference between note-derived amount and cash flow statement amount that can be tied to disclosed adjustment candidates.

### Unexplained Gap

A difference that remains after available adjustment candidates and tolerance are considered.

### Parse Uncertainty

A condition where document structure, row labels, column labels, signs, or section boundaries are ambiguous enough that the tool should not make a strong reconciliation assertion.

### Source Location

Traceable reference to the originating filing, section, table, row, column, and raw label/text. Every material amount in a reconciliation result should preserve source location.

### Core Account

A financial statement primary line that meets at least one of: (i) appears as a BS asset/liability subtotal carrier or exceeds an absolute/relative materiality threshold, (ii) belongs to a PL operating subtotal (revenue, cost of sales, SG&A, income tax expense), (iii) belongs to a CF operating/investing/financing subtotal line. Core accounts are the *starting point* for essential note enumeration; they are not themselves notes.

_Avoid_: "main account", "key item" (English equivalents are loose); use **Core Account** consistently.

### Essential Note

A note disclosure that is (i) mapped 1:1 or 1:N from a **Core Account**, and (ii) closes at least one **Verification Axis** at audit grade (exact or within disclosed display-unit tolerance, no LLM judgment). A note that is K-IFRS mandatory but cannot be reconciled to any statement or peer note is *not* an essential note for this engine — it is recorded as `non_validation_note_table` with rationale.

Resolution of Q1 (2026-06-06): essential is defined by **core-account derivation + verification closeability**, not by K-IFRS standard authority alone, not by corpus frequency alone. K-IFRS standard and corpus frequency act as candidate sources but neither is sufficient.

_Avoid_: "mandatory note", "must-have note" (both ambiguous between regulatory and engine meaning).

### Audit Cycle

A grouping of **Core Accounts** that share a transaction lifecycle and are typically audited together. The engine recognizes six cycles for the **nonfinancial company scope**:

| Cycle | Core Account candidates (2026-06-06 v0) |
|---|---|
| `operating` | 매출액, 매출원가, 매출채권, 재고자산, 매입채무, 판관비, 비용 성격별 분류 |
| `investing` | 유형자산(PPE), 무형자산, 투자부동산, 금융자산 |
| `financing` | 차입금, 사채, 리스부채, 자본금/자본잉여금/이익잉여금 |
| `tax` | 법인세비용, 이연법인세자산/부채 |
| `employee` | 종업원급여(단기), 퇴직급여(확정급여채무), 주식기준보상 |
| `other` | 현금및현금성자산, 충당부채, EPS, 배당, 자본변동 |

Resolution of Q2 (2026-06-06): cycle enumeration follows the **audit work-program standard**, not K-IFRS statement classification (too abstract) and not corpus frequency (belongs to validation, not enumeration). The six cycles above form the v0 grid; cycle boundary rules for ambiguous accounts (e.g. 이연법인세 = `tax`, 영업권 손상 = `investing`) are decided per ADR-0003.

_Avoid_: "category", "section" (overloaded with disclosure section concepts).

### Reconciliation Axis

The direction along which a **Verification Attempt** runs. Six axes for the v0 nonfinancial scope:

| Axis key | Meaning |
|---|---|
| `note_to_note` | Two notes are tied to each other (e.g. PPE roll-forward ending ↔ depreciation expense allocation source) |
| `note_to_bs` | A note amount ties to a 재무상태표 line |
| `note_to_pl` | A note amount ties to a 손익계산서 line |
| `note_to_sce` | A note amount ties to a 자본변동표 line |
| `note_to_cf` | A note amount ties to a 현금흐름표 line |
| `statement_to_statement` | Two statement bodies tie directly without a note bridge (BS 기말 현금 ↔ CF 기말 현금; BS 자본총계 ↔ SCE 기말 자본총계). work-order S2-2 |

The earlier user-stated five-axis sketch (note↔note, note↔BS, note↔PL, note↔SCE, note↔CF) is extended to six by `statement_to_statement` because cross-statement ties are mandatory audit checks that do not involve a note bridge.

_Avoid_: "verification direction", "reconciliation type" (ambiguous with `assertion_type` already used in `reconciliation_targets.py`).

### Footing Axis

The direction along which a **Footing** check runs. One axis for v0:

| Axis key | Meaning |
|---|---|
| `internal` | A table closes against itself (component sum = displayed total; row math = column math) |

**Footing Axis** and **Reconciliation Axis** stay separate by domain rule. A `Verification Attempt` declares which axis it belongs to; mixing is rejected at registry registration time. This enforces the existing doctrine that footing and reconciliation are different checks.

_Avoid_: collapsing "footing" and "reconciliation" into a single "check direction" — the doctrine collapses with the term.

### Verification Signature

A directly observable property of a note table that triggers one or more **Verification Attempts**. Signatures are derived from headers, row labels, cell types, units, table shape, and `taxonomy.py` matches — *never* from company name, industry code, or layout key. A table can carry multiple signatures simultaneously; each match adds an attempt to the verification queue. Signatures replace **LayoutClassification** as the entry gate of the verification pipeline (ADR-0003).

V0 signature library (17 after merging from 22 candidates, 2026-06-06):

| Group | Signatures |
|---|---|
| Axis | `row_oriented_movement`, `column_oriented_measure`, `period_columns`, `classification_columns`, `maturity_buckets`, `qualitative_text_only` |
| Role | `rollforward_axis` (with degree meta: `complete` ∨ `minimal`), `balance_only`, `component_total_pair`, `acquisition_disposal_pair` |
| Account | `statement_core_match` (with statement meta: `BS` ∨ `PL` ∨ `CF` ∨ `SCE`), `note_topic_match` |
| Unit/Precision | `declared_multiplier`, `unit_mixed_per_row` |
| Closure | `internal_closure` (with level meta: `subtotal` ∨ `grand_total`), `component_sum_eq_total` |
| Cross-reference | `explicit_section_pointer`, `acode_match` |

_Avoid_: "layout key" (legacy of category dispatch), "table type" (ambiguous).

### Verification Attempt

A single arithmetic check the engine runs against one or more tables to produce an **Outcome Label**. An attempt is triggered when its required **Verification Signature** combination is present. The same attempt may be triggered by multiple distinct signature combinations (path multiplicity is intentional — one path failing must not block the others).

V0 attempt registry includes: asset roll-forward footing, roll-forward minimal, BS↔note balance, PL↔note expense allocation, CF↔note cashflow bridge, SCE↔note equity, internal table total, maturity profile internal, prior-year tie, cross-statement cash tie, cross-statement equity tie. New attempts are added by extending the attempt registry, not by adding layout-name branches.

_Avoid_: "check" (used in code for `CheckResult` already; "attempt" is the *trigger*, "check" is the *result row*).

### Outcome Label

The post-verification label attached to a table or table-attempt pair. Labels are **observed outcomes**, not pre-classification routing. Six values:

| Label | Meaning |
|---|---|
| `matched` | Attempt closed exactly or within disclosed display-unit tolerance |
| `unresolved_with_signature` | Attempt was triggered but arithmetic did not close (replaces earlier `unexplained_gap` framing where signature was present) |
| `parse_uncertain` | Signature matched at low confidence; attempt result not promotable |
| `no_signature_matched_qualitative` | Zero signatures matched; cells are predominantly qualitative text |
| `no_signature_matched_industry_terms` | Zero signatures matched; industry-specific vocabulary dominates (out of v0 nonfinancial scope) |
| `no_signature_matched_unknown` | Zero signatures matched; cells are quantitative but no recognized pattern (true backlog) |

The earlier 5-category sketch (disclosure-only, cross-cycle bridge, industry-specific, internal-only, informational) survives only as a **statistics view** over these labels — never as a verification gate (ADR-0003).

### Company Scope

A per-company label in `{nonfinancial, financial, unknown}` that tunes verification *confidence and statistics view*, **not** verification dispatch. ADR-0003 forbids using scope as a routing key; scope therefore appears as:

- A `scope` field on each corpus manifest entry (primary source of truth).
- A `--scope` CLI flag for single-company ad-hoc runs without a manifest.
- An `inferred_scope` metadata field populated by post-run signature statistics when manifest scope is `unknown` (e.g. when industry-specific signatures dominate, the run output records `inferred_scope=financial`).
- A confidence modifier on attempt registration: for `scope=financial`, attempts targeted at nonfinancial signatures (`note_to_cf` cashflow bridge against PPE/intangible/borrowing patterns) receive a 0.5× confidence multiplier, which usually downgrades `matched` to `parse_uncertain` without blocking the attempt.

DART industry codes (`induty_code`) are a *labeling aid* for manifest authors, never a runtime branching key.

Resolution of Q5 (2026-06-06): scope is a manifest-first label with signature-based inference as backup. The v0 100-company corpus is labeled by hand on first slice (well-known cases: DB손해보험, KB금융, 삼성생명, 한화손해보험, 현대해상, 대신증권 → `financial`; rest → `nonfinancial` by default; ambiguous → `unknown`).

_Avoid_: "industry", "sector" (overloaded with DART standard classifications); "financial vs nonfinancial mode" (implies dispatch).

A signature emission carries a numeric confidence in `[0.0, 1.0]` derived from how unambiguously the data exhibits the pattern (e.g. exact `취득원가` header match = 0.95; partial `취득` substring with siblings = 0.6). Each **Verification Attempt** declares its own acceptance thresholds against the *combined* confidence of its required signatures:

| Threshold | Default | Effect |
|---|---|---|
| `matched_minimum` | 0.70 | Below this, an exact arithmetic closure is downgraded to `parse_uncertain` |
| `attempt_minimum` | 0.40 | Below this, the attempt is not run; outcome is `no_signature_matched_*` |

Per-attempt overrides are allowed (e.g. cross-statement cash tie may require `matched_minimum = 0.90` because the source statements are non-negotiable). Overrides live in the attempt registry, not in signature emitters.

_Avoid_: "score" (overloaded with classifier scoring in `layout_variants.py`); use **confidence** consistently.

## Module Responsibilities (engine layer, post-ADR-0003)

| Module | Responsibility |
|---|---|
| `note_inventory.py` | Catalog every note table; no classification |
| `signatures.py` (new) | Emit **Verification Signatures** from inventory items; no verification arithmetic |
| `essential_notes.py` (new) | Hold **Audit Cycle** × **Core Account** × **Essential Note** mappings; expose `essential_notes_for(cycle)` and `attempt_registry_for(essential_note)` |
| `taxonomy.py` | Stay focused on atomic label↔acode normalization; do **not** absorb cycle/essential-note semantics |
| `verification_candidates.py` | Stay focused on candidate-amount extraction *after* an attempt is triggered; do **not** absorb signature emission |
| `layout_variants.py` | Demoted to a signature emitter; new code never adds to it |
| `checks_*.py` | Stay separated by axis (totals, fs↔note, note↔note, cfs↔note, reconciliation, prior-year); attempt registry wires them |

These are easy-to-reverse module placement decisions; no separate ADR.

## Core Domain Rules

- Footing and cash flow reconciliation are separate checks.
- Differences are classified, not automatically treated as errors.
- Label mapping is probabilistic in practice but must be represented explicitly through confidence and source evidence.
- The core reconciliation engine must run without MCP.
- MCP should expose the engine to agents after the CLI/package contract is stable.

## Initial Check Families

### Investing Activities

- Property, plant and equipment acquisitions and disposals
- Intangible asset acquisitions and disposals
- Investment property acquisitions and disposals

### Financing Activities

- Borrowing proceeds and repayments
- Bond issuance and redemption
- Lease liability principal payments

## Result Statuses

- `matched`
- `explainable_gap`
- `unexplained_gap`
- `parse_uncertain`

## Reviewer Lens Extension

The reconciliation report can be extended into a reviewer-facing interpretation
layer, but this must remain separate from the footing engine.

### Product Boundary

Footing and reconciliation results are evidence, not audit conclusions. The
next layer should generate reviewer questions and follow-up prompts from
evidence patterns. It should not assert that fraud, error, or audit risk exists.

Canonical chain:

```text
DART footing
→ report structuring
→ financial statement / note / business section extraction
→ account movement analysis
→ business-model-based risk hypotheses
→ key account review points
→ reviewer question list
```

### Layer Model

1. Footing and extraction: structure financial statements, notes, business
   content, audit report text, KAM, and account-level evidence.
2. Accounting interpretation: translate account changes, ratios, trends, and
   note keywords into business-model-aware signals.
3. Reviewer coach: draft risk hypotheses, key account review points, request
   lists, and manager/partner questions.

### Required Tone

Use hypothesis language:

```text
매출채권 증가율이 매출 증가율을 크게 상회하고 영업현금흐름이 악화되어,
기말 판매조건 완화 또는 채널 밀어내기 가능성을 후속 확인할 필요 있음.
```

Avoid assertion language:

```text
매출 밀어내기 있음.
```

### MVP Scope

Target: one listed manufacturing company with three years of annual
reports/audit reports.

Output:

- Business model summary
- Key account movement table
- Five anomaly signals
- Five risk hypotheses
- Key-account reviewer questions
- Required request list

Initial account families:

- Revenue
- Trade receivables
- Inventory
- Cost of sales
- Property, plant and equipment
- Depreciation
- Operating cash flow
- Provisions, returns, rebates, and sales incentives
