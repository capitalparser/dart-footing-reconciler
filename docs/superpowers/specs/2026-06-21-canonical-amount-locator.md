# Canonical Amount Locator — Design Spec

**Date:** 2026-06-21 (revised same day after cross-model review)
**ADR:** `docs/adr/0008-canonical-amount-locator.md`; review corrections `docs/adr/0009-locator-review-findings.md`
**Scope:** Introduce `amount_locator.py` as the single source of truth for **cell selection**, then migrate the three existing cell-selection paths onto it strangler-fig, under a hard no-new-false-positives corpus gate.
**Primary executor:** Codex (files + tests + corpus). **Git owner / verifier:** Claude.

> Read `docs/adr/0009-locator-review-findings.md` first — it records why the interface and tests below differ from a naive reading of ADR-0008.

---

## 1. Problem (do not re-derive — see ADR-0008/0009)

"Which `(row, col)` carries this account's amount?" is answered divergently in three places:
- `taxonomy._generic_note_row_amount` (taxonomy.py:864) — rightmost column whose value `_amounts_close(line.amount, …)` (**amount-validated**, F5).
- `reconciliation_inputs._asset_total_balance_amount` (:415), `_asset_family_total_balance_amount` (:427), `_asset_family_total_columns` (:534), `_trade_receivable_current_net_amount` (:374).
- `verification_candidates` — 50+ layout extractors.

Same `(table, account)` → different cells → false matches (B-5) and, downstream, false gaps. **Scope (F2):** the locator owns *cell selection* — its wins are **B-5** (`net_carrying_amount`) and **B-2b** (`current_/noncurrent_portion`). **B-2a/B-4 are check-layer pairing decisions** (`checks_fs_note._select_note_hit_by_label`) and stay there; they benefit from cleaner cells but are not moved.

## 2. The module

### 2.1 Public interface (the only thing callers know)

```python
def locate(
    item: NoteTableInventoryItem,            # title/headers/row_labels — classify_layout needs these (F1)
    table: ReportTable,
    account_key: str,
    role: TargetAmountRole,
    *,
    layout: LayoutClassification | None = None,      # reuse if already computed; else derived from item
    orientation: TableOrientation | None = None,
    scope: str | None = None,                         # "consolidated"|"separate" — DRIVES column choice (F6)
    expected_amount: int | None = None,               # tie-breaker among valid candidates ONLY (F5)
) -> LocatedAmount | Abstain | NotApplicable: ...
```

- `item` is mandatory: `layout_variants.classify_layout(item)` keys off `item.title`/`item.heading`/headers/row_labels, which a bare `ReportTable` cannot produce (F1). Every real call site holds both (`reconciliation_inputs.py:261-263`; `verification_candidates.py:32-38`).
- `expected_amount` breaks ties among structurally-valid candidates; it never fabricates a cell (F5).
- The locator never raises on "can't find it" — it returns `Abstain` or `NotApplicable`.

### 2.2 Return types (three outcomes — F8)

```python
@dataclass(frozen=True)
class LocatedAmount:
    account_key: str
    role: TargetAmountRole
    row_index: int                      # anchor cell (summary row for a row-sum)
    col_index: int
    raw_amount: int
    unit_multiplier: int
    amount: int                         # raw_amount * unit_multiplier, or the row sum
    confidence: float                   # [0.0, 1.0]
    source: str                         # anchor Source Location (reconciliation_inputs._source format)
    component_sources: tuple[str, ...]  # () single-cell; each summed cell for a category-matrix row-sum (F4)
    evidence: tuple[str, ...]           # row label, column header, archetype key, strategy id

@dataclass(frozen=True)
class Abstain:                          # tried-but-ambiguous → caller emits parse_uncertain
    account_key: str
    role: TargetAmountRole
    reason_code: str                    # ∈ PARSE_UNCERTAIN_REASONS
    detail: str

@dataclass(frozen=True)
class NotApplicable:                    # role/account structurally absent → caller emits not_tested
    account_key: str
    role: TargetAmountRole
    detail: str
```

Abstain (→ `parse_uncertain`): `AMBIGUOUS_MULTIPLE` / `COLUMN_NOT_DETECTED` / `LOW_CONFIDENCE_MATCH` / `AMOUNT_PARSE_FAILED`. NotApplicable (→ `not_tested`): the role does not apply to this archetype (e.g. `cash_like_movement` of a pure balance table). Mapping role-inapplicable to parse_uncertain corrupts the honest-coverage signal — do not (F8, backlog §4a).

### 2.3 TargetAmountRole (closed, 7 — CONTEXT.md)

`period_end_balance`, `net_carrying_amount`, `cash_like_movement`, `disclosed_total`, `expense_allocation`, `current_portion`, `noncurrent_portion`. Adding a value requires an ADR amendment. A test pins the set to exactly these 7 and asserts `amount_locator` does not import the three ADR-0006 §S2 role enums for mapping (orthogonality guard, F8).

## 3. Archetype → strategy binding (candidate 2; the "성격마다 파싱" core)

Each `layout_variants` archetype binds, **per role**, a cell-selection strategy returning a `LocateResult`. The binding table is the SSOT; `locate()` is a thin dispatcher.

### 3.0 Phase 0.5 — record the acceptance fixtures' ACTUAL keys FIRST (F3)

Before writing any strategy, run `classify_layout` on the acceptance fixtures and record the keys that actually fire:
- 더존 유형자산 N9, 더존 무형자산 N12, 셀트리온 유형자산 N12-1, 롯데정밀화학 유형자산.
- Expect surprises: 더존 N9 may be `asset_cost_accumulated_grant_total` (conf 0.9, checked first, layout_variants.py:26), **not** `asset_cost_accumulated_summary`. There is currently **no** `category_matrix` key for 더존 무형 N12 (row-sum across 산업재산권/회원권/개발비…); add one or map it to an existing column-summary key. ~13 other asset-family keys exist (`asset_carrying_amount_total`, `asset_measure_summary`, `asset_stacked_measure_summary`, `asset_current_period_carrying_amount`, …) — net carrying can land in any; cover or explicitly document exclusions.

Strategies bind to the keys that fire, not to the spec's archetype names.

### 3.1 `net_carrying_amount` — the B-5 acceptance triad (all must pass)

| Shape | Example | Strategy (net cell) | Never select |
|---|---|---|---|
| net-vs-gross matrix | 더존 유형자산 N9: row "유형자산 합계", cols `[총장부금액 549bn · 감가상각누계 · 정부보조금 · 장부금액합계 361bn]` | account-total row × the **net** column for the requested `scope`; high confidence only if a gross column is also present (disambiguates) | 총장부금액 / 취득원가 column |
| rollforward | 셀트리온 유형자산 N12-1: row "유형자산 합계", cols `[기초 1,214bn · …변동… · 기말]` | account-total row × **기말** column for the requested `scope` | 기초 / movement columns |
| category matrix | 더존 무형자산 N12: row "기말 무형자산 및 영업권" spread across category columns | the ending-balance **row** summed across category columns; populate `component_sources` (F4) | per-category single cell as the total |

Abstain (do not guess): account-total row absent, net column not disambiguable from gross, ≥2 candidate columns tie (`AMBIGUOUS_MULTIPLE`/`COLUMN_NOT_DETECTED`). NotApplicable: table is not an asset note at all.

### 3.2 `period_end_balance` / `current_portion` / `noncurrent_portion` — boundary with the check layer (F2)

The locator is asked about a **specific account/role in a table** and returns the cell or abstains. It does **not** scan a note and skip 유동성 대체/발행차금/음수 rows — that is `checks_fs_note._select_note_hit_by_label` choosing among already-located hits (`checks_fs_note.py:116-219`), which **stays in the check layer**. So:
- `period_end_balance` returns the balance cell for the account; if asked about a contra/재분류 row it returns that value with its sign (the check layer decides whether to pair it). The locator does not own the B-2a filter.
- `current_portion`/`noncurrent_portion` return the matching portion cell when the note discloses a 유동/비유동 split. This enables B-2b: the check layer can then sum FS 단기+장기 or compare portion-to-portion instead of `fs_hit[0]`-only.

### 3.3 Other roles (later phases)

- `disclosed_total` — returns the disclosed total cell; **must call into / share** ADR-0007's total-cell detection in `checks_totals` (single rightmost 합계 column, section subtotals, abstain on multiple 합계), never reimplement it (F9). Arithmetic stays in `checks_totals`.
- `cash_like_movement` — 취득/처분/차입/상환 cell; reuse `formula_discovery`/`note_assertions._movement_amount` sign handling (item-A signed-net rule: do not force-negate 증가/증감 rows).
- `expense_allocation` — 성격별/기능별 비용 배분 cell; fold `FunctionalExpenseInput` selection.

### 3.4 Cross-archetype abstain/NotApplicable rules (F6 edge cases)

- **scope mirror columns:** select the column matching `scope`; abstain `COLUMN_NOT_DETECTED` if it can't be identified. (롯데정밀화학 acceptance is 별도.)
- **기말 absent** (only 기초+증감): abstain `COLUMN_NOT_DETECTED` — do NOT compute 기말 = 기초 + Σ증감.
- **mixed-unit rows** (원/백만원 by row): abstain `AMOUNT_PARSE_FAILED` — a single `table.unit_multiplier` cannot scale them.
- **prior-period mirror tables:** inherit `reconciliation_inputs._is_prior_period_table` (:1752) → NotApplicable/abstain, never locate cells in 전기 tables (keeps §6 "legitimate abstentions stay abstained").
- **multi-row headers:** strategies must scan the header band (cf. `_asset_total_carrying_amount_columns` reads `rows[:4]`), not only `rows[0]`/`item.headers` — net/current labels often live in a super-header.

## 4. Migration (strangler-fig) — one path per corpus-gated phase

| Phase | Scope | Wiring | Corpus expectation |
|---|---|---|---|
| 0.5 | Record acceptance fixtures' actual `classify_layout` keys; add `category_matrix` handling (F3) | none | n/a |
| 1 | Implement `locate()` + strategies for `net_carrying_amount` + `period_end_balance`; unit tests incl. real-fixture regression pins | module only, not called | unchanged (byte-identical 5-status) |
| 1.5 | Route ONE company / ONE account through the locator behind a flag; observe the `_select_note_hit_by_label` coupling (F7/M3) before full cutover | 1 account | per-company snapshot unchanged except the observed account |
| 2 | Route `reconciliation_inputs` balance/net-carrying selection | 1 path | matched ↑ (recover B-5), unexplained_gap not ↑ from FP, **per-company snapshot hard gate** |
| 3 | Route `taxonomy._generic_note_row_amount` (locator proposes, taxonomy validates vs `line.amount` via `expected_amount`, F5) + `verification_candidates` | 2 paths | per-path corpus gate |
| 4 | `current_portion`/`noncurrent_portion` → B-2b level-aware | role extension | corpus gate |

Each phase independently revertible. A phase that cannot pass stays abstained, not forced.

## 5. Tests (TDD — RED before GREEN)

### 5.1 Unit (Phase 1 — the new test surface)

`tests/test_amount_locator.py`:
1. net-vs-gross matrix → net column, not gross.
2. rollforward → 기말 column, not 기초.
3. category matrix → row sum across category columns, `component_sources` populated (F4).
4. Abstain `COLUMN_NOT_DETECTED` when net/gross indistinguishable; when scope column absent; when 기말 absent.
5. Abstain `AMBIGUOUS_MULTIPLE` when ≥2 total rows tie.
6. **NotApplicable** when the role does not apply (cash_like_movement of a balance table) — asserts `not_tested`, not `parse_uncertain` (F8).
7. `current_portion` vs `noncurrent_portion` split selection (B-2b enabler).
8. Source Location + `unit_multiplier` + `component_sources` preserved.
9. **Regression pins (F7):** one assertion per check destroyed by the 2026-06-16 revert — CJ 무형×2, 더존 PPE/투자부동산/리스×2 — built from real parsed fixtures, asserting the located cell equals the known-correct net cell. This, not the synthetic tests, is what locks the "+4 hid 8 destroyed" failure.
10. Orthogonality guard: `set(r.value for r in TargetAmountRole)` is exactly the 7; `amount_locator` does not import `AccountRole`/`_role_for_label` for mapping (F8).

### 5.2 Regression (every phase)

`uv run pytest -q` green; `uv run ruff check` clean on changed files; existing `tests/test_checks_totals*.py`, `test_taxonomy.py`, `test_reconciliation_inputs.py`, `test_verification_candidates.py`, `test_checks_fs_note.py` stay green.

## 6. Corpus gate (mandatory, every wiring phase)

Run `manifest_2026-06-10-nonfinancial-industry-10` before AND after; report the 5-status histogram. Pass criteria:
- `matched` ↑ or flat; **`unexplained_gap` must NOT rise from new false positives** (per-check confirm any net-new gap is genuine);
- `parse_uncertain` falls only where a real cell is now located; legitimate prior-period abstentions stay abstained;
- **`scripts/check_per_company_snapshot.py` is a HARD gate** (not "report", F7) — aggregate gains must not hide per-company destruction;
- spot-acceptance: 더존·셀트리온·롯데정밀화학 net-carrying move B-5 abstain → matched, diff=0 vs FS, **zero genuine matches destroyed**.

## 7. Hard rules (unchanged doctrine)

- Abstain over guess. An audit verdict cannot carry a false match.
- The locator does **not** classify accounts (taxonomy), does **not** run arithmetic (checks_*), and does **not** pick among located hits / filter balance rows (checks_fs_note — F2).
- Do not merge `TargetAmountRole` with the three role vocabularies of ADR-0006 §S2.
- Every located amount preserves Source Location (incl. `component_sources` for row-sums).
- Semantic/signature track is diagnostic-only (ADR-0008 amendment) — do not route locator output through it.
