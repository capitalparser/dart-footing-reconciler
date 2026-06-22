# Nonfinancial corpus expansion — batch 1 (2026-06-22)

Per the nonfinancial-first scope (CONTEXT.md Company Scope; `docs/adoption-review-2026-06-22-footing-prompt.md`) and `docs/validation/verification-accuracy-strategy.md` (Stratified Smoke = 10–20 nonfinancial filings across industries), the smoke set is extended beyond the original 10-company `manifest_2026-06-10-nonfinancial-industry-10`.

> The corpus (manifests + raw HTML under `out/`) is **gitignored / local-only** — same as the original. The committed, durable artifacts are the **per-company baseline** (`tests/baselines/per_company_counts_2026-06-22-expansion.json`) and this reproduction recipe. Re-fetch from the recorded rcp_no's to rebuild the local corpus.

## Batch 1 — new nonfinancial industries (not in the original 10)

| Company | Industry | 2024 사업보고서 rcp_no | corp_code |
|---|---|---|---|
| 삼성전자 | 반도체/전자 | `20250311001085` | 00126380 |
| POSCO홀딩스 | 철강 | `20250312001016` | 00155319 |
| SK텔레콤 | 통신 | `20250317000684` | 00159023 |

(Original 10: 배터리·완성차·바이오·유통·건설·에너지·물류·SW·정밀화학·조선.)

## Reproduction (keyless — no DART API key required)

1. **rcp_no discovery** via the kreports MCP local cache (keyless): `search_dataset(dataset="source_documents", company=<name>, year=2024)` → the `business_report` record's `rcept_no`.
2. **Fetch raw DART HTML**: `dart_fetch.fetch_financial_section(rcp_no, out_path)` → `out/corpus/run_2026-06-22-nonfinancial-expansion/raw/{company}_2024_{rcp}.html` (DART viewer scrape; network only).
3. **Manifest**: `out/corpus/manifest_2026-06-22-nonfinancial-expansion.json` (local) — same schema as the 10-company manifest.
4. **Run**: `run_workpaper_corpus(manifest, out_dir, fetch_missing=False, tolerance=1)` → `corpus_result.json`; per-company status counts → the committed baseline.

## Discovery (batch 1)

| Company | stmts | notes | note_tables | matched | unexpl_gap | parse_uncertain | not_tested | unknown_layout |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 | 8 | 64 | 397 | 246 | 31 | 48 | 278 | 84% |
| POSCO홀딩스 | 9 | 77 | 417 | 483 | 43 | 25 | 217 | 87% |
| SK텔레콤 | 10 | 82 | 454 | 342 | 22 | 43 | 320 | 85% |

- The engine parses and verifies new nonfinancial industries end-to-end (no crashes, real matched results).
- `unknown_layout` ≈ 84–87% — consistent with ADR-0003 (most note tables carry no recognized *layout key*; this is not "unverified" — many are still checked via structure/signatures). It marks the long tail for future signature/archetype coverage, not a defect.
- The per-company `unexplained_gap` (31 / 43 / 22) are **triage candidates** — each must be confirmed genuine vs FP before any rule change (corpus-gate doctrine). Not yet reviewed; this batch is for breadth + regression coverage, not yet a labeled Gold Set.

## Next

- Batch 2 candidates (further distinct nonfinancial industries): 식음료(CJ제일제당), 인터넷/플랫폼(NAVER), 화장품(아모레퍼시픽), 항공(대한항공), 유틸리티(한국전력), 화학-종합(LG화학), 엔터(하이브).
- Promote a reviewed subset to a labeled **Gold Set** (expected outcomes per `verification-accuracy-strategy.md`) once breadth stabilizes.
- Triage the new `unexplained_gap` clusters per industry (genuine vs FP).
