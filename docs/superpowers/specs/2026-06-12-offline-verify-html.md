# Offline Verify HTML — Design Spec

> **⚠️ SUPERSEDED (2026-06-14).** The JS-port architecture below is abandoned in favor of running the
> existing Python engine in-browser via **PyOdide** (single engine, zero divergence, accuracy-first).
> See current `HANDOFF.md` and ADR `docs/adr/0005-pyodide-single-engine-over-js-port.md`.
> Kept for provenance only.

**Date:** 2026-06-12  
**Scope:** Single self-contained `dart-verify.html` — multi-format file upload, client-side
verification engine (JS port of Python core), kreports stub layer, evidence_cockpit UI.

---

## 1. Goal

Replace the CLI-only output model with a browser-runnable single HTML file that:
- Accepts DART HTML / DSD-extracted HTML / electronic PDF uploads (drag-and-drop or picker)
- Runs audit verification logic entirely in-browser (no server)
- Renders results in PAS evidence_cockpit design (verdict banner, dark sidebar, tick-mark overlays, drilldowns)
- Leaves a kreports integration hook open (UI + data interface, API calls stubbed)

---

## 2. Architecture

### 2.1 Component Map

```
File Upload (FileReader API)
    ↓
FormatDetector  →  HTMLParser (DOMParser)
                →  DSDParser  (XML → inner HTML → HTMLParser)
                →  PDFParser  (PDF.js inlined)
    ↓
ReportTable[]   (shared JS struct)
    ↓
VerificationEngine
  ├─ parseAmount()
  ├─ currentPeriodColumns() / priorPeriodColumns()
  ├─ LabelResolver.findRow()         ← 5-tier: EXACT > PREFIX > CONTAINS > POSITION > FUZZY
  ├─ bsEquationCheck()
  ├─ cashTieCheck()
  └─ equityTieCheck()
    ↓                    ↕ (stub, not active)
ResultsRenderer       KreportsPanel
(evidence_cockpit JS)   └─ PriorPeriodOracle interface (no-op impl for now)
```

### 2.2 Data Structures (JS)

```js
// Input
ReportTable {
  index: number,
  rows: string[][],        // rows[0] = header, rows[1..] = data
  caption: string,
  unitMultiplier: number,  // default 1
  reportType: "annual" | "half" | "quarter" | "unknown"
}

ReportSection {
  sectionId: string,
  title: string,
  kind: "statement" | "note",
  noteNo: string,
  tables: ReportTable[]
}

FullReport {
  company: string,
  statements: ReportSection[],
  notes: ReportSection[]
}

// Output
CheckEvidence { label: string, amount: number|null, source: string }

CheckResult {
  checkId: string,
  checkType: string,
  status: "matched" | "unexplained_gap" | "parse_uncertain",
  title: string,
  expected: number|null,
  actual: number|null,
  difference: number|null,
  tolerance: number,
  reason: string,
  evidence: CheckEvidence[],
  parseUncertainReason: string|null
}

// kreports stub
PriorPeriodOracle {
  fetchPriorAmounts(corpCode: string, reportType: string): Promise<PriorPeriodData|null>
}
// Default implementation: returns null (no-op)

PriorPeriodData {
  corpCode: string,
  companyName: string,
  reportType: "annual" | "half" | "quarter",
  periodEnd: string,         // "YYYY-MM-DD"
  amounts: {                 // AccountRole → amount
    asset_total?: number,
    liability_total?: number,
    equity_total?: number,
    cash_end?: number
  }
}
```

---

## 3. Input Format Handling

### 3.1 FormatDetector

Dispatch by file extension + content sniff:

| Extension | Handler |
|---|---|
| `.html` / `.htm` | HTMLParser |
| `.dsd` | DSDParser → HTMLParser |
| `.pdf` | PDFParser |
| other | Error callout, supported format list shown |

### 3.2 HTMLParser (DOMParser native)

- `new DOMParser().parseFromString(text, "text/html")`
- Extract `<table>` elements → `rows: string[][]` (cell text, trimmed)
- Detect `caption` from preceding `<caption>` or nearest heading
- Detect `unit_multiplier` from caption text ("단위: 백만원" → 1_000_000)
- Port of `html_tables.py` logic

### 3.3 DSDParser

DSD files may be ZIP archives containing HTML/doc/toc. Browser cannot unzip natively.

**Strategy:**
1. Attempt XML parse (`DOMParser`, `"text/xml"`) — extract inner `<HTML>` node → HTMLParser
2. If ZIP magic bytes (`PK\x03\x04`) detected → show guidance: "DSD 파일에서 HTML을 먼저 추출해주세요"
3. Accept both `.dsd` and `.htm` from DSD extraction

### 3.4 PDFParser (PDF.js inlined)

- PDF.js bundled inline (minified, pinned to v4.x, ~400KB gzipped ~150KB)
- Per-page text item extraction with `x`, `y`, `width` coordinates
- Column boundary detection: cluster `x`-positions across all pages → column indices
- Row boundary detection: `y`-position gaps > threshold → new row
- Known limitation: complex merged cells may produce `parse_uncertain_reason: "PDF_COLUMN_UNCERTAIN"`
- `reportType` inferred from extracted header keywords

### 3.5 Column Detection Vocabulary

```js
const CURRENT_HEADERS = new Set([
  // Annual
  "당기", "당기말", "당년도", "당해", "당기말현재", "당기현재",
  // Quarter
  "당분기", "당분기말", "당3분기", "당2분기", "당1분기",
  // Half-year
  "당반기", "당반기말",
]);

const PRIOR_HEADERS = new Set([
  // Annual
  "전기", "전기말", "전년도", "전기말현재", "전기현재",
  // Quarter
  "전분기", "전분기말",
  // Half-year
  "전반기", "전반기말",
]);
```

**Detection order:**
1. Explicit header match (CURRENT_HEADERS / PRIOR_HEADERS) → direct map
2. `제N기` pattern → highest N = current period
3. Neither → `COLUMN_NOT_DETECTED` → kreports oracle fallback (no-op stub → `PARSE_UNCERTAIN`)

`reportType` inference:
- Any of 당분기/전분기 in headers → `"quarter"`
- Any of 당반기/전반기 → `"half"`
- Otherwise → `"annual"`

---

## 4. Verification Engine (JS Port)

### 4.1 `parseAmount(cell: string): number | null`

Port of `amounts.py`. Handles:
- `"1,000,000"` → 1000000
- `"(500)"` → -500 (parenthesis = negative)
- `"-"` / `""` / `"—"` → null
- Leading/trailing whitespace stripped

### 4.2 `LabelResolver.findRow(table, role): RowMatch | null`

Port of `label_resolver.py`. 5 tiers, same confidence thresholds:

| Tier | Confidence | Logic |
|---|---|---|
| EXACT | 1.0 | Canonical label set exact match after compact() |
| PREFIX | 0.85 | Canonical label is prefix of cell |
| CONTAINS | 0.70 | Canonical label is substring of cell |
| POSITION | 0.55 | Last row containing 총/합/계 — ASSET_TOTAL only |
| FUZZY | 0.40 | Levenshtein similarity ≥ 0.80 |

Same guard: if `liabilityMatch.row === assetMatch.row` → treat liability as not found.
POSITION restricted to `ASSET_TOTAL` only (as per prior code review decision).

Canonical label sets (same as Python `_CANONICAL_LABELS`):
```js
const CANONICAL_LABELS = {
  asset_total:     ["자산총계","자산합계","자산계","총자산","자본과부채총계","자산총액"],
  liability_total: ["부채총계","부채합계","부채계","총부채"],
  equity_total:    ["자본총계","자본합계","총자본","순자산총계"],
  cash_end:        ["기말현금","기말현금및현금성자산","현금및현금성자산","기말의현금"],
  cash_begin:      ["기초현금","기초현금및현금성자산","기초의현금"],
  profit_loss:     ["당기순이익","당기순손익","당기손익"],
  revenue:         ["매출액","영업수익","수익"],
};
```

### 4.3 Checks (port of `checks_statement_ties.py`)

**`bsEquationCheck(report)`** — 자산총계 = 부채총계 + 자본총계  
**`cashTieCheck(report)`** — BS 현금 ↔ CF 기말 현금  
**`equityTieCheck(report)`** — BS 자본총계 ↔ SCE 기말 자본

All three return `CheckResult[]`, propagate `parseUncertainReason`.

`_currentAmount(table, row)` uses `currentPeriodColumns(table.rows[0])` — **not** naive `row[1]`.

---

## 5. kreports Stub Layer

### 5.1 Interface

```js
class NullPriorPeriodOracle {
  async fetchPriorAmounts(corpCode, reportType) { return null; }
}
```

### 5.2 UI Panel (rendered but inactive)

- Sidebar section: "kreports 연동" toggle (OFF by default)
- When toggled ON: corp_code input + endpoint input + 조회 button
- Button click: shows "연동 준비 중" callout (stub response)
- Panel design matches existing sidebar style
- `data-kreports-status="stub"` attribute for future activation

### 5.3 Future activation path

When kreports integration is live:
- Replace `NullPriorPeriodOracle` with `KreportsApiOracle`
- `KreportsApiOracle.fetchPriorAmounts()` calls kreports FastAPI endpoint
- CORS must be enabled on the kreports server for `localhost` origin
- `COLUMN_NOT_DETECTED` cases pass prior amounts to `LabelResolver` for column pinning

---

## 6. UI / UX

### 6.1 Layout

Single HTML, PAS evidence_cockpit shell:

```
┌──────────────────┬──────────────────────────────────┐
│ sidebar (dark)   │ main                              │
│                  │                                   │
│ [파일 첨부]       │ [verdict-banner]                  │
│  drop zone       │  이상없음 / 검토필요 / 확인필요    │
│  HTML/DSD/PDF    │  matched N  gap N  uncertain N    │
│                  │                                   │
│ ──────────────   │ [statement panels]                │
│ [kreports]  ○    │  재무상태표 원문 + tick overlays   │
│  (stub)          │  drilldown on click               │
│                  │                                   │
│ ──────────────   │ [note panels]  (비어있으면 숨김)  │
│ 재무상태표  ✓    │                                   │
│ 손익계산서       │ [parse-uncertain panel]           │
│ 현금흐름표  ⚠    │                                   │
└──────────────────┴──────────────────────────────────┘
```

### 6.2 State Machine

| State | Trigger | Display |
|---|---|---|
| `empty` | 초기 | 파일 없음 안내, drop zone 강조 |
| `parsing` | 파일 선택됨 | 스피너, 파일명 표시 |
| `results` | 파싱 완료 | verdict-banner + 패널 |
| `error` | 파싱 실패 | 오류 callout, 원인 코드 |
| `kreports-active` | kreports toggle ON + 조회 | "준비 중" callout (stub) |

### 6.3 Design Tokens

Same as existing evidence_cockpit:
- `--sidebar-bg: #0f172a`, `--ok: #16a34a`, `--warn: #f59e0b`, `--down: #dc2626`, `--accent: #3b82f6`
- Pretendard font (fallback to system-ui)
- `letter-spacing: 0`, `line-height: 1.6`
- Tick-mark overlays: `✓` / `⚠` / `?` via CSS `::after`
- No external CDN except PDF.js bundle (inlined)

### 6.4 Security

- All extracted text passed through `escHtml()` before DOM insertion
- `_safeId()` for element IDs (strip non-alphanumeric)
- No `eval()`, no `innerHTML` with raw user data (use `textContent` or escaped string)

---

## 7. File Structure (new files)

```
src/dart_footing_reconciler/
  verify_html/
    __init__.py              (exports build_verify_html())
    builder.py               (assembles final HTML from parts)

static/
  dart-verify-template.html  (base HTML shell)
  js/
    format-detector.js
    html-parser.js
    dsd-parser.js
    pdf-parser.js            (wraps PDF.js)
    verify-engine.js         (parseAmount, LabelResolver, checks)
    kreports-panel.js        (stub oracle + UI)
    results-renderer.js      (evidence_cockpit DOM builder)
  vendor/
    pdf.min.js               (PDF.js, pinned version)

tests/
  js/
    verify-engine.test.js
    html-parser.test.js
    pdf-parser.test.js
  e2e/
    upload-smoke.spec.ts     (Playwright — `file://` 프로토콜로 HTML 직접 로드, 서버 불필요)

CLI addition:
  cli.py  →  `dart-footing-reconciler build-verify-html --output dart-verify.html`
```

---

## 8. Testing Strategy

| Layer | Tool | Key Cases |
|---|---|---|
| `parseAmount()` | Vitest | 숫자/괄호/대시/공백/단위 |
| `currentPeriodColumns()` | Vitest | 당기/당분기/당반기/제N기/감지실패 |
| `LabelResolver.findRow()` | Vitest | 5-tier 전부, 자본과부채총계 guard, POSITION ASSET_TOTAL만 |
| `bsEquationCheck()` | Vitest | matched/gap/parse_uncertain/zero-equity |
| `HTMLParser` | Vitest | 단순 table, 다중 table, unit multiplier |
| `PDFParser` | Vitest + fixture | 전자공시 PDF stub → ReportTable |
| E2E smoke | Playwright | HTML 업로드 → verdict-banner 노출, PDF 업로드 → parse_uncertain |

kreports: `NullPriorPeriodOracle` 주입으로 모든 테스트 독립 실행 가능.

---

## 9. Out of Scope (이번 사이클)

- kreports 실제 API 호출 (stub만)
- 스캔 PDF OCR
- 주석 검증 (BS equation / cash tie / equity tie만)
- 분반기 kreports 조회 (전기 대사 JS 로직은 구현, kreports 데이터는 stub)
- 모바일 최적화 (데스크톱 우선)

---

## 10. Codex 인계 메모

- 구현 담당: Codex (코드 생성·테스트·빌드)
- 검증 담당: Claude (spec 정합성·보안·도메인 정확성)
- Python 원본 참조: `src/dart_footing_reconciler/table_semantics.py`, `label_resolver.py`, `checks_statement_ties.py`, `amounts.py`
- 브랜치: `feat/offline-verify-html` (from `audit-workpaper-note-reconciliation`)
- 독립 테스트 가능성: kreports 없이 모든 검증 로직 동작해야 함
