# Nonfinancial corpus expansion (2026-06-22)

Per the nonfinancial-first scope (CONTEXT.md Company Scope; `docs/adoption-review-2026-06-22-footing-prompt.md`) and `docs/validation/verification-accuracy-strategy.md` (Stratified Smoke = 10–20 nonfinancial filings across industries), the smoke set is extended beyond the original 10-company `manifest_2026-06-10-nonfinancial-industry-10`. **Total now 18 nonfinancial industries.**

> The corpus (manifests + raw HTML under `out/`) is **gitignored / local-only** — same as the original. The committed, durable artifacts are the **per-company baseline** (`tests/baselines/per_company_counts_2026-06-22-expansion.json`) and this reproduction recipe. Re-fetch from the recorded rcp_no's to rebuild the local corpus.

## Expansion set — new nonfinancial industries (not in the original 10)

| # | Company | Industry | 2024 사업보고서 rcp_no | corp_code | induty |
|---|---|---|---|---|---|
| B1 | 삼성전자 | 반도체/전자 | `20250311001085` | 00126380 | 264 |
| B1 | POSCO홀딩스 | 철강 | `20250312001016` | 00155319 | 2411 |
| B1 | SK텔레콤 | 통신 | `20250317000684` | 00159023 | 61220 |
| B2 | CJ제일제당 | 식음료 | `20250317000648` | 00635134 | 108 |
| B2 | NAVER | 인터넷/플랫폼 | `20250318000645` | 00266961 | 63120 |
| B2 | 아모레퍼시픽 | 화장품 | `20250317000429` | 00583424 | 20423 |
| B2 | 대한항공 | 항공운송 | `20250318001334` | 00113526 | 511 |
| B2 | 한국전력공사 | 유틸리티/전력 | `20250318000747` | 00159193 | 35120 |

(Original 10: 배터리·완성차·바이오·유통·건설·에너지·물류·SW·정밀화학·조선.)

## Reproduction (keyless — no DART API key required)

1. **rcp_no discovery** via the kreports MCP local cache (keyless): `search_dataset(dataset="source_documents", company=<name>, year=2024, include_excerpt=false)` → the `business_report` record's `rcept_no`.
2. **Fetch raw DART HTML**: `dart_fetch.fetch_financial_section(rcp_no, out_path)` → `out/corpus/run_2026-06-22-nonfinancial-expansion/raw/{company}_2024_{rcp}.html` (DART viewer scrape; network only).
3. **Manifest**: `out/corpus/manifest_2026-06-22-nonfinancial-expansion.json` (local) — same schema as the 10-company manifest.
4. **Run**: `run_workpaper_corpus(manifest, out_dir, fetch_missing=False, tolerance=1)` → `corpus_result.json`; per-company status counts → the committed baseline.

## Discovery

| Company | matched | unexpl_gap | explain | parse_uncertain | not_tested |
|---|---:|---:|---:|---:|---:|
| 삼성전자 | 246 | 31 | 6 | 48 | 278 |
| POSCO홀딩스 | 483 | 43 | 2 | 25 | 217 |
| SK텔레콤 | 342 | 22 | 6 | 43 | 320 |
| CJ제일제당 | 721 | 66 | — | 46 | 323 |
| NAVER | 486 | 62 | — | 25 | 325 |
| 아모레퍼시픽 | 378 | 13 | — | 39 | 241 |
| 대한항공 | 433 | 38 | — | 49 | 264 |
| 한국전력공사 | 665 | 35 | — | 69 | 398 |

- The engine parses and verifies all 8 new nonfinancial industries end-to-end (no crashes, real matched results), including the 7.8 MB 한국전력 filing.
- `unknown_layout` ≈ 84–87% on the batch-1 sample — consistent with ADR-0003 (most note tables carry no recognized *layout key*; this is not "unverified" — many are still checked via structure/signatures). Long tail for future signature/archetype coverage, not a defect.
- Per-company `unexplained_gap` are **triage candidates** (each must be confirmed genuine vs FP before any rule change — corpus-gate doctrine). Highest: CJ제일제당 (66), NAVER (62). Not yet reviewed; this set is for breadth + regression coverage, not yet a labeled Gold Set.

## Next

- Further distinct nonfinancial industries: 화학-종합(LG화학), 엔터(하이브), 게임(엔씨/크래프톤), 디스플레이(LG디스플레이), 반도체-순수(SK하이닉스), 통신-2위(KT), 종합상사/지주(SK·LG).
- Promote a reviewed subset to a labeled **Gold Set** (expected outcomes per `verification-accuracy-strategy.md`) once breadth stabilizes (~20–30).
- Triage the new `unexplained_gap` clusters per industry (genuine vs FP), starting with CJ제일제당 / NAVER.
