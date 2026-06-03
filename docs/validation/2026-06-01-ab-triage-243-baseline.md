# A/B Triage Remap — 243 Baseline (2026-06-01)

Baseline corpus: `out/corpus/run_2026-06-01-codex-243-baseline-remap-default`
from `out/corpus/manifest_2026-05-27-hundred-asset-note-bridges.json`
with cached raw disclosures and no external fetch.

- Generated reports: 100/100
- Primary checks: 243
- Primary matched: 190
- Primary unresolved: 53
- Primary unresolved types: `primary_balance_reconciliation` 51,
  `expense_allocation` 2
- 243-baseline effect: no `cashflow_reconciliation` primary check IDs are
  present in the regenerated local primary set, so 575-baseline cash-flow
  triage rows cannot be accepted as local primary targets without first
  restoring target extraction coverage.

| triage_id | 회사 | check_type | status | 금액 차이 | 재매핑 결정 | 근거 |
|---|---|---|---|---:|---|---|
| B01 | 현대건설 | cashflow_reconciliation | not_in_243_primary | -3,636M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대건설 PPE 처분; local unresolved equivalent not generated. |
| B02 | 현대건설 | primary_balance_reconciliation | unexplained_gap | 334,479M | keep | Local 243 unresolved ID `reconciliation:intangible_assets.balance`; difference `334,479,000,000`. |
| B03 | 현대건설 | cashflow_reconciliation | not_in_243_primary | 933M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대건설 무형 취득. |
| B04 | 현대건설 | cashflow_reconciliation | not_in_243_primary | -4,929M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대건설 무형 처분. |
| B05 | 풍산 | primary_balance_reconciliation | unexplained_gap | -7,831M | keep | Local 243 unresolved ID `reconciliation:property_plant_equipment.balance`; difference `-7,831,431,401`. |
| B06 | 풍산 | cashflow_reconciliation | not_in_243_primary | -176M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 풍산 PPE 처분. |
| B07 | 풍산 | cashflow_reconciliation | not_in_243_primary | 409M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 풍산 무형 취득. |
| B08 | 풍산 | cashflow_reconciliation | not_in_243_primary | +100,000M | drop_575_only | 243 primary unresolved taxonomy has no financing cash-flow primary ID for 풍산 차입금. |
| B09 | 풍산 | cashflow_reconciliation | not_in_243_primary | -100,001M | drop_575_only | 243 primary unresolved taxonomy has no financing cash-flow primary ID for 풍산 사채. |
| B10 | 롯데하이마트 | cashflow_reconciliation | not_in_243_primary | -1,761M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 롯데하이마트 PPE 취득. |
| B11 | 롯데하이마트 | cashflow_reconciliation | not_in_243_primary | 1,482M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 롯데하이마트 PPE 처분. |
| B12 | 롯데하이마트 | primary_balance_reconciliation | absent_after_t5 | 572,900M | drop_575_only | Wrong-row balance case is no longer an unresolved local primary ID after T5 guard; current 243 taxonomy has no 롯데하이마트 primary unresolved rows. |
| B13 | 롯데하이마트 | cashflow_reconciliation | not_in_243_primary | 1,734M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 롯데하이마트 무형 취득. |
| B14 | 더존비즈온 | cashflow_reconciliation | not_in_243_primary | 1,186M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 더존비즈온 PPE 취득. |
| B15 | 더존비즈온 | cashflow_reconciliation | not_in_243_primary | 1,020M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 더존비즈온 PPE 처분. |
| B16 | 더존비즈온 | cashflow_reconciliation | not_in_243_primary | 6.9M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 더존비즈온 무형 취득. |
| B17 | 더존비즈온 | cashflow_reconciliation | not_in_243_primary | -400M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 더존비즈온 무형 처분. |
| B18 | 현대모비스 | cashflow_reconciliation | not_in_243_primary | -14,786M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대모비스 PPE 취득. |
| B19 | 현대모비스 | cashflow_reconciliation | not_in_243_primary | 77,715M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대모비스 PPE 처분. |
| B20 | 현대모비스 | cashflow_reconciliation | not_in_243_primary | -200M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대모비스 무형 취득. |
| B21 | 현대자동차 | cashflow_reconciliation | not_in_243_primary | 350,093M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대자동차 PPE 취득. |
| B22 | 현대자동차 | cashflow_reconciliation | not_in_243_primary | -18,239M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 현대자동차 무형 취득. |
| B23 | 지누스 | cashflow_reconciliation | not_in_243_primary | 1,210M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 지누스 PPE 취득. |
| B24 | 지누스 | cashflow_reconciliation | not_in_243_primary | 807M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 지누스 PPE 처분. |
| B25 | 지누스 | cashflow_reconciliation | not_in_243_primary | 8.1M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 지누스 무형 취득. |
| B26 | GS리테일 | cashflow_reconciliation | not_in_243_primary | 8,412M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for GS리테일 PPE 취득. |
| B27 | GS리테일 | cashflow_reconciliation | not_in_243_primary | 13,966M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for GS리테일 무형 처분. |
| B28 | 한화시스템 | cashflow_reconciliation | not_in_243_primary | 13.2M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 한화시스템 PPE 처분. |
| B29 | 한화시스템 | cashflow_reconciliation | not_in_243_primary | 15,175M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 한화시스템 무형 취득. |
| B30 | 한화시스템 | expense_allocation | unexplained_gap | 596M | keep | Local 243 unresolved ID `reconciliation:intangible_assets.amortization_expense_allocation`; difference `595,633,000`. |
| B31 | 해성디에스 | cashflow_reconciliation | not_in_243_primary | 17,306M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 해성디에스 PPE 취득. |
| B32 | 해성디에스 | cashflow_reconciliation | not_in_243_primary | 587M | drop_575_only | 243 primary unresolved taxonomy has no cash-flow primary ID for 해성디에스 무형 취득. |
| B33 | 해성디에스 | cashflow_reconciliation | not_in_243_primary | -15,913M | drop_575_only | 243 primary unresolved taxonomy has no financing cash-flow primary ID for 해성디에스 차입금. |

## Priority Queue

Keep/drop counts under the accepted 243-baseline: keep 3,
drop_575_only 30, replace_with_local_equivalent 0. Updated queue:
T6 first (`B02` 현대건설 무형 balance, `B05` 풍산 PPE balance) because these are
the only Stream 1 rows still present as local 243 primary unresolved IDs;
then S2-1 materiality to rank the remaining 53 unresolved primary rows; then
S2-2 cross-statement ties. T1/T2/T3/T4 are blocked as primary corpus targets
on this cached 243-baseline until cash-flow primary target extraction is
restored or an explicit local-equivalent artifact is adopted.
