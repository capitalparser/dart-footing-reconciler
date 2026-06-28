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

### Consolidation Basis (연결기준)

The **reporting basis** of a statement/note section: `consolidated` (연결) or `separate` (별도; 개별). A single DART business report contains BOTH bases — consolidated financial statements followed by separate ones — so every **StatementLine** and **NoteRow** belongs to exactly one basis, and a reconciliation must never pair a `consolidated` line to a `separate` note.

This is a **structural dimension of the document**, orthogonal to **Company Scope**. The word "scope" is overloaded: the code field `ReportSection.scope ∈ {consolidated, separate}` actually carries **Consolidation Basis**, while the glossary's **Company Scope** is `{nonfinancial, financial, unknown}`. Canonical entity-attribute name is **Consolidation Basis**; the `.scope` field rename to `.consolidation_basis` is deferred refactor work (do not block on it).

Resolution (2026-06-24, grill Q1): introduce **Consolidation Basis** as the canonical term for consolidated/separate; keep **Company Scope** for financial/nonfinancial. The `ReportSection.scope` field stores Consolidation Basis today.

_Avoid_: "scope" alone for consolidated/separate (collides with Company Scope); "individual" (ambiguous — use **separate** / 별도).

### Balance Level (유동/비유동)

The intrinsic balance-sheet level a **StatementLine** or **NoteRow** sits at: `current` (유동), `noncurrent` (비유동), `total` (유동+비유동 합계 / 단일 미분할 잔액), or `unknown`. It is a **property of the line itself** (what the line *is*), determined data-driven from the label (`유동성`/`유동`→current, `비유동`/`장기`→noncurrent, an explicit 합계/기말 total→total) and, when the label is level-silent, from BS section position (lines in the 유동부채/유동자산 section are current). When neither label nor position resolves it → `unknown`.

**Balance Level (the line's data) is distinct from Target Amount Role (the caller's intent).** The roles `current_portion`/`noncurrent_portion` are *resolved against* Balance Level: "give me the current portion" is satisfied by the line/row whose Balance Level is `current`. A **note_to_bs** reconciliation pairs a StatementLine to a NoteRow of the **same Balance Level**; when the note discloses only a `total` row, the engine sums exactly the `current` + `noncurrent` StatementLines of the **same Account + Consolidation Basis + Report Period** to match it (no cross-level, cross-basis, or cross-period summation). If the level cannot be resolved on either side, the engine **abstains** (never guesses a level).

Resolution (2026-06-24, grill Q2): Balance Level is a first-class line/row attribute; Target Amount Roles resolve to it; pairing keys on it; ambiguity → abstain. Enables B-2b (ADR-0011 residual).

_Avoid_: "term" / "maturity" (those are maturity-bucket concepts, not the BS current/noncurrent split); "portion" alone (collides with the role names).

### Report Period (당기/전기)

The reporting period a line or cell belongs to: `current` (당기) or `prior` (전기, comparative). A DART BS/note column set carries both; a reconciliation pairs **same-period to same-period** only (prior-year ties are a separate Reconciliation Attempt handled in `checks_prior_*`). Report Period is a dimension of the **pairing key** `(Account × Consolidation Basis × Report Period × Balance Level)`, ensuring a current-year statement line never pairs to a prior-year note amount.

_Avoid_: reusing `current` without qualification — it is overloaded between **Report Period** `current` (당기) and **Balance Level** `current` (유동). Always qualify in code: `period == "current"` vs `level == "current"`.

A signature emission carries a numeric confidence in `[0.0, 1.0]` derived from how unambiguously the data exhibits the pattern (e.g. exact `취득원가` header match = 0.95; partial `취득` substring with siblings = 0.6). Each **Verification Attempt** declares its own acceptance thresholds against the *combined* confidence of its required signatures:

| Threshold | Default | Effect |
|---|---|---|
| `matched_minimum` | 0.70 | Below this, an exact arithmetic closure is downgraded to `parse_uncertain` |
| `attempt_minimum` | 0.40 | Below this, the attempt is not run; outcome is `no_signature_matched_*` |

Per-attempt overrides are allowed (e.g. cross-statement cash tie may require `matched_minimum = 0.90` because the source statements are non-negotiable). Overrides live in the attempt registry, not in signature emitters.

_Avoid_: "score" (overloaded with classifier scoring in `layout_variants.py`); use **confidence** consistently.

### Target Amount Role

The **caller's verification intent** when asking "which amount of this **Core Account** do I need from this table?" — *not* a row classifier. It is a **fourth, orthogonal axis** layered on top of the three intentionally-distinct role vocabularies that ADR-0006 §S2 forbids merging:

- `semantic_layer._role_for_label` — a row's rollforward role (기초/기말/합계/증감);
- `label_resolver.AccountRole` — which statement account a row is (ASSET_TOTAL/CASH_END/…);
- `orientation` MOVEMENT/MEASURE/PERIOD groups — table *structure* detection.

A **Target Amount Role** is resolved into a concrete cell by *composing* those three (account identity × movement role × structure) against the table's archetype. V0 closed vocabulary (7, ratified 2026-06-21):

| Role | 의미 | Primary consumer (Reconciliation/Footing Axis) |
|---|---|---|
| `period_end_balance` | 기말 잔액 (재무상태표 잔액 계정의 마감 잔액) | `note_to_bs` |
| `net_carrying_amount` | 순장부금액 (감가/상각/손상 차감 후; ≠ 취득원가·총장부금액) | `note_to_bs` (B-5 family) |
| `cash_like_movement` | 현금 유발 증감 (취득/처분/차입/상환) | `note_to_cf` |
| `disclosed_total` | 공시된 합계/소계 | `internal` (Footing Axis) |
| `expense_allocation` | 비용의 성격별/기능별 배분액 | `note_to_pl` |
| `current_portion` | 유동분 | `note_to_bs` level-aware (B-2b) |
| `noncurrent_portion` | 비유동분 | `note_to_bs` level-aware (B-2b) |

The set is closed: a new role is added only with an ADR amendment, never ad hoc inside a caller. `net_carrying_amount` ≠ `disclosed_total` is the load-bearing distinction (B-5: "{계정} 합계" is often *gross*, not net).

_Avoid_: "amount type", "value kind" (collide with measure/role terms above).

### Canonical Amount Locator

The single **Module** that answers "which cell carries the `<Target Amount Role>` amount for `<Core Account>` in `<this table>`?" — replacing the row/column-selection logic currently scattered across `taxonomy.py`, `reconciliation_inputs.py`, and `verification_candidates.py`. Interface (the **Seam**): `locate(table, account_key, role) → LocatedAmount | Abstain`.

- `LocatedAmount` carries the chosen `(row, col)`, raw + scaled amount, confidence, and **Source Location**.
- `Abstain` carries one `parse_uncertain_reason` (the existing closed `PARSE_UNCERTAIN_REASONS` vocabulary) — abstain maps to the `parse_uncertain` **Outcome Label**, honoring abstain-over-guess.
- Per-archetype cell-selection strategy (net-vs-gross matrix → net column; rollforward → 기말 column; category matrix → row sum) lives *behind* the seam, bound to each `layout_variants` archetype — the data-driven form of "성격마다 파싱". See `docs/adr/0008-canonical-amount-locator.md`.

The locator is the SSOT for **cell selection**; it does not classify accounts (taxonomy) or run arithmetic (checks_*). One deep module, small interface.

## Module Responsibilities (engine layer, post-ADR-0003)

| Module | Responsibility |
|---|---|
| `note_inventory.py` | Catalog every note table; no classification |
| `amount_locator.py` (new, ADR-0008) | **Canonical Amount Locator** — SSOT for cell selection: `locate(table, account_key, role) → LocatedAmount \| Abstain`. Per-archetype strategy behind the seam. No account classification, no arithmetic |
| `signatures.py` | Partial (emits 3 of the 17 planned signatures). **Demoted to a diagnostic/coverage-discovery emitter** consumed only by the semantic track; not a verification gate (ADR-0003 status amended, see ADR-0008) |
| `semantic_layer.py` / `semantic_attempts.py` / `semantic_validation.py` | **Diagnostic overlay only** — feeds `verify_app` display/placement, contributes **zero** to the 5-status verification output (deletion-test confirmed). Not the verification front door (ADR-0006 §C2; ADR-0003 amendment) |
| `essential_notes.py` | **Not built** — the Audit Cycle × Core Account × Essential Note grid lives implicitly in `taxonomy.py` + `reconciliation_inputs.py`. Documented as deferred, not a current module |
| `taxonomy.py` | Atomic label↔acode + account↔note *classification*. Hands cell selection to `amount_locator.py`; do **not** re-implement row/column picking here |
| `verification_candidates.py` | Candidate-amount extraction *after* an attempt is triggered; **routes cell selection through `amount_locator.py`** as the strangler migration proceeds |
| `reconciliation_inputs.py` | Builds `*Input` rows for the axes; **routes balance/net-carrying/portion cell selection through `amount_locator.py`** |
| `layout_variants.py` | Archetype classifier; each archetype binds a locator cell-selection strategy. New code never adds flat `_is_X` branches |
| `checks_*.py` | Stay separated by axis (totals, fs↔note, note↔note, cfs↔note, reconciliation, prior-year) |

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

**Single source of truth: `checks.ALL_STATUSES` (5 values).** Every summary, KPI strip, and JSON payload counts exactly these; `not_tested` is surfaced as coverage, never dropped (ADR-0006 §C1):

- `matched`
- `explainable_gap`
- `unexplained_gap`
- `parse_uncertain`
- `not_tested`

The 6-value **Outcome Label** set above (`matched / unresolved_with_signature / parse_uncertain / no_signature_matched_*`) was *designed* under ADR-0003 for a signature-dispatch engine that was **only partially adopted**. It is **not** the runtime status vocabulary — treat it as a statistics/diagnostic view, not a code contract. When the two disagree, `checks.ALL_STATUSES` wins.

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

## Report Validation Result Ledger & Cross-Module Orchestration (2026-06-27, ADR-0015 + ADR-0016)

09 *is* the report-validation engine for the financial-statement/note tie-out domain (the "보고서 검증 툴" plan folds into 09; it is not a new project). This layer adds **persistence, cross-module routing, and a qualitative retrieval boundary** *around* the deterministic core — the core (parse → classify → 4 Harnesses → 5-status `CheckResult`) is unchanged. The check arithmetic stays deterministic Python; the ledger only persists and reviews. **The one load-bearing rule: the core verdict is sealed into an immutable run artifact, and the ledger / findings / signals / RAG are all downstream projections of that artifact — never inputs to it** (ADR-0016).

### Responsibility Triad

Three legs, kept separate by rule (the RAG-vs-SQL framing is sharpened to a triad because 09's arithmetic is Python, not SQL):

| Leg | Does | Unit |
|---|---|---|
| **Deterministic engine** (Python) | arithmetic, closure, abstain — produces `CheckResult` | the verdict |
| **Ledger** (SQL/SQLite) | persist runs, aggregate, cross-run review VIEWs | normalized facts/findings rows |
| **Retrieval** (RAG/MCP) | qualitative, source, peer, standard-basis context | text / structured peer rows |

The LLM is confined to **narrative** (finding writeup, follow-up, workpaper) and receives **summaries, never raw tables**. SQL never executes the primary arithmetic; retrieval never enters the arithmetic and can never promote a `matched`.

### Result Ledger (not "Finding Ledger")

The SQLite store that **materializes a sealed run artifact after the engine has run**. Its centre is **`check_results` — all 5 statuses** (matched/explainable_gap/unexplained_gap/parse_uncertain/not_tested), preserving 09's "`not_tested` is coverage, never dropped" doctrine. `findings` is the **exception projection** over it; `coverage_observations` is the matched/not_tested/aggregate view. It is a sink/review surface, not the check substrate: the deterministic core runs without it (ADR-0001), and **the materializer reads the sealed artifact only and never mutates a `CheckResult`** — verdict-immutability is enforced by a **canonical full-result fingerprint diff** (ledger-disabled vs enabled NDJSON byte-identical), not a 5-status count diff (counts hide offsetting swaps — already 09's reason for its check-level corpus gate). SQL is for review/aggregation VIEWs only and never re-computes amount/tolerance/gap; amounts are scaled-integer/decimal-string (SQLite `REAL` forbidden).

_Avoid_: "Finding Ledger" (the ledger's centre is the full 5-status result set, not findings); "validation DB" as the place checks *run* (checks run in Python; the DB only records them).

### Finding

The **exception projection of a `CheckResult`** persisted in the ledger — `finding ⊂ CheckResult`. A finding exists only when a result is an exception or data gap (status ∈ {`unexplained_gap`, `parse_uncertain`}, or a disclosure gap). `matched` and `not_tested` results are **never** findings. A finding carries the result's source-location evidence (`fact_id`s), at least one suggested follow-up, and any cross-module signals; it never asserts misstatement or control deficiency without a recorded `reviewer_decision` (evidence, not conclusion). An exception is **never dropped** if its follow-up generation fails (that is a `followup_generation_error`, not a missing finding). Non-exception results are not silent: `matched`/`not_tested` live in **`coverage_observations`** (an aggregate digest), so downstream modules can request positive tie-out evidence or coverage gaps without inflating the finding queue.

_Avoid_: treating every `CheckResult` as a finding (only exceptions are); "exception" alone (collides with `unresolved_with_signature`); emitting per-row `matched` signals (use the coverage digest).

### Cross-Module Signal

A **durable handoff envelope** emitted from a finding to a sibling audit engine via an **outbox + ack contract** (not a bare YAML): a `cross_module_signals` outbox row (09-local source of truth) **plus** a `Harness/queue/{date}_{slug}.yaml` envelope (PAS §5.0 async-handoff), with the consumer writing ack/reject to `Harness/ack/`. The `signal_id` is **content-addressed** (hash, never a SQLite autoincrement); the envelope carries `idempotency_key`, `schema_version`, `stale_after`, `payload_hash`, and `supersedes_signal_id` so a later run that resolves a gap (e.g. a parser fix → `matched`) **retracts/supersedes** the prior signal. Delivery is **at-least-once + idempotent consumer**; 09 **never imports** a consumer. The schemas are shared at vault level (`02_Areas/Shared_Audit_Kernel/`, schema-only). Routing is **conservative**: `parse_uncertain` → parser/data-quality queue (no auto ERP/KSOX); KSOX only on **repeated + human-confirmed** gaps; a **consolidated-basis** gap routes as a `consolidation_bridge_drilldown_candidate` (component mapping / consolidation adjustments), not a direct GL mismatch; every signal carries the **full entity key**. The external event taxonomy splits **finding_signal** (exceptions) from **coverage/observation** (matched digest, not_tested gaps).

_Avoid_: "router call" / "trigger" (implies a synchronous in-process call — it is an envelope); routing to a module as if it were present (the signal is durable precisely because the target may be absent); routing a single raw gap as a control-deficiency (over-interpretation).

### Retrieval Layer (RAG/MCP boundary)

The **qualitative/source/peer context source**, outside the verdict and deferred behind the ledger. 09 builds **no own vector index**; peer/standard retrieval is **kreports-MCP-backed** (`compare_peer_accounting_policies`, `compare_peer_kam_topics`, `search_audit_procedures`, `get_accounting_policy`). It serves the checks Python cannot do — disclosure-completeness candidates and policy-adequacy review — and lives in the **Reviewer Lens Extension** (hypothesis language, never a conclusion). Note: locating an amount's originating page/table is **not** a retrieval problem in 09 — every amount already carries its **Source Location** deterministically.

_Avoid_: "RAG validates the amounts" (the engine does; retrieval only enriches/contextualizes); building an embedding index inside the core.

### Ledger Schema Mapping (core ↔ persisted contract)

The core domain vocabulary is unchanged; the ledger/external contract uses the plan's audit-orchestration names. Canonical bidirectional map:

| Ledger / cross-module contract | 09 core domain (canonical) |
|---|---|
| `validation_rule` (+ `check_logic_ref`) | **Verification Attempt** (+ its registered Python check) |
| `report_fact` | **LocatedAmount** / extracted amount with **Source Location** |
| `validation_run` | one `assemble_report_checks` execution / corpus run |
| `finding` | **`CheckResult`** where status ∈ {`unexplained_gap`, `parse_uncertain`} (exception projection); all 5 statuses live in `check_results` |
| `operational_priority` (NOT `severity`) | two axes — `impact_magnitude` × `evidence_reliability` — plus a `triage_reason` that selects a **queue**. **Never** an audit-risk conclusion |
| `cross_module_signal` | (new — no core equivalent; emitted by the outbox adapter) |
| `reviewer_decision` | mutable **overlay** on an immutable `core_status`; never overwrites the verdict |

_Avoid_: the name `severity` and any single `amount × confidence` score (it mis-ranks large-amount/low-confidence, which is a high parse-review priority, not a low one); letting `operational_priority` drift into a risk/likelihood judgment — 09 doctrine is "evidence, not audit conclusions."
