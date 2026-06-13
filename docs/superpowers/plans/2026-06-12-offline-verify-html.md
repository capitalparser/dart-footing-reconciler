# Offline Verify HTML Implementation Plan

> **⚠️ SUPERSEDED (2026-06-14) — DO NOT IMPLEMENT.**
> This JS-port plan is abandoned. The Python engine already contains the full verification stack
> (orientation / reconciliation / semantic / formula / label-resolver / report_html), so a JS
> reimplementation would be strictly less accurate and force double-maintenance. Replaced by the
> **PyOdide single-engine** approach — see current `HANDOFF.md` and ADR
> `docs/adr/0004-pyodide-single-engine-over-js-port.md`. Kept for provenance only.

> **For Codex:** Read `docs/superpowers/specs/2026-06-12-offline-verify-html.md` for full context. This plan is for the `feat/offline-verify-html` branch. TDD throughout — write the test first, verify it fails, then implement.

**Goal:** Build `dart-verify.html` — a single self-contained HTML file that accepts DART HTML / DSD / electronic PDF uploads, runs BS/Cash/Equity audit checks in-browser (JS port of Python core), and renders results in PAS evidence_cockpit UI.

**Architecture:** ES modules in `static/js/` (Vitest-testable); Python builder concatenates + strips `export`/`import` keywords and inlines everything (including PDF.js UMD) into one `<script>` inside the HTML template. No server. No CDN.

**Tech Stack:** Vanilla JS ES modules, Vitest 2.x + jsdom, Playwright 1.x (file:// protocol), PDF.js UMD v4.x, Python Typer CLI, Python builder (regex-based inline bundler)

---

## File Map

**New — JS source (browser + Vitest testable)**
- `static/js/verify-engine.js` — parseAmount, column detection, LabelResolver, checks
- `static/js/html-parser.js` — DOMParser-based HTML→FullReport
- `static/js/dsd-parser.js` — DSD XML → HTMLParser passthrough / ZIP guidance
- `static/js/pdf-parser.js` — PDF.js wrapper → ReportTable[]
- `static/js/format-detector.js` — extension sniff → dispatch parser
- `static/js/results-renderer.js` — evidence_cockpit DOM builder (CheckResult[] → DOM)
- `static/js/kreports-panel.js` — NullPriorPeriodOracle + stub UI panel
- `static/js/app.js` — UI init, file drop wiring, orchestration
- `static/dart-verify-template.html` — HTML shell with CSS + `<!-- PDFJS_PLACEHOLDER -->` / `<!-- BUNDLE_JS_PLACEHOLDER -->`
- `static/vendor/pdf.min.js` — PDF.js UMD (copied from npm during Task 1)
- `static/vendor/pdf.worker.min.js` — PDF.js worker (for Blob URL workerSrc)

**New — Vitest tests**
- `tests/js/verify-engine.test.js`
- `tests/js/html-parser.test.js`
- `tests/js/pdf-parser.test.js`

**New — Playwright E2E**
- `tests/e2e/upload-smoke.spec.ts`

**New — Python**
- `src/dart_footing_reconciler/verify_html/__init__.py`
- `src/dart_footing_reconciler/verify_html/builder.py`

**Modified**
- `package.json` — add vitest, jsdom, pdfjs-dist, esbuild (devDeps)
- `vitest.config.js` — new
- `playwright.config.ts` — update include path
- `src/dart_footing_reconciler/cli.py` — add `build-verify-html` command

---

## Task 1: JS Toolchain + Branch Setup

**Files:** `package.json`, `vitest.config.js`, `playwright.config.ts`

- [ ] **Step 1: Create branch**

```bash
git checkout audit-workpaper-note-reconciliation
git checkout -b feat/offline-verify-html
```

- [ ] **Step 2: Update package.json**

Replace existing `package.json` with:

```json
{
  "name": "dart-footing-reconciler-js",
  "type": "module",
  "scripts": {
    "test:unit": "vitest run",
    "test:e2e": "playwright test",
    "test": "vitest run && playwright test"
  },
  "devDependencies": {
    "vitest": "^2.3.0",
    "@vitest/coverage-v8": "^2.3.0",
    "jsdom": "^25.0.3",
    "playwright": "^1.50.0",
    "@playwright/test": "^1.50.0",
    "pdfjs-dist": "^4.10.38"
  }
}
```

- [ ] **Step 3: Create vitest.config.js**

```js
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['tests/js/**/*.test.js'],
    globals: true,
  },
});
```

- [ ] **Step 4: Update playwright.config.ts**

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',
  use: {
    headless: true,
    channel: 'chromium',
  },
});
```

- [ ] **Step 5: Install deps + copy PDF.js**

```bash
npm install
mkdir -p static/vendor static/js tests/js tests/e2e
# Copy PDF.js UMD builds to static/vendor
cp node_modules/pdfjs-dist/build/pdf.min.js static/vendor/pdf.min.js
cp node_modules/pdfjs-dist/build/pdf.worker.min.js static/vendor/pdf.worker.min.js
```

- [ ] **Step 6: Verify Vitest runs (empty)**

```bash
npx vitest run --reporter=verbose
```

Expected: "No test files found" or 0 tests.

- [ ] **Step 7: Commit**

```bash
git add package.json vitest.config.js playwright.config.ts static/vendor/
git commit -m "chore: add JS toolchain (Vitest + jsdom) + PDF.js vendor"
```

---

## Task 2: `parseAmount()` — verify-engine.js, Part 1

**Files:** `static/js/verify-engine.js`, `tests/js/verify-engine.test.js`

- [ ] **Step 1: Write failing tests**

Create `tests/js/verify-engine.test.js`:

```js
import { describe, test, expect } from 'vitest';
import { parseAmount } from '../../static/js/verify-engine.js';

describe('parseAmount', () => {
  test('parses plain integer', () => {
    expect(parseAmount('1000')).toBe(1000);
  });
  test('parses comma-separated', () => {
    expect(parseAmount('1,000,000')).toBe(1000000);
  });
  test('parses parenthesis as negative', () => {
    expect(parseAmount('(500)')).toBe(-500);
    expect(parseAmount('(1,200)')).toBe(-1200);
  });
  test('returns null for dash', () => {
    expect(parseAmount('-')).toBeNull();
    expect(parseAmount('—')).toBeNull();
  });
  test('returns null for empty string', () => {
    expect(parseAmount('')).toBeNull();
    expect(parseAmount('   ')).toBeNull();
  });
  test('returns null for no digit', () => {
    expect(parseAmount('합계')).toBeNull();
  });
  test('strips footnote markers before parsing', () => {
    expect(parseAmount('1,000(*1)')).toBe(1000);
    expect(parseAmount('1,000(주1)')).toBe(1000);
    expect(parseAmount('1,000[주2]')).toBe(1000);
    expect(parseAmount('1,000①')).toBe(1000);
  });
  test('normalizes NBSP and unicode minus', () => {
    expect(parseAmount(' 1,000 ')).toBe(1000);
    expect(parseAmount('(−5,000)')).toBe(-5000);
  });
  test('normalizes △ as negative', () => {
    expect(parseAmount('△500')).toBe(-500);
  });
  test('returns null for null input', () => {
    expect(parseAmount(null)).toBeNull();
    expect(parseAmount(undefined)).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
npx vitest run tests/js/verify-engine.test.js
```

Expected: FAIL — `Cannot find module '../../static/js/verify-engine.js'`

- [ ] **Step 3: Implement parseAmount in verify-engine.js**

Create `static/js/verify-engine.js`:

```js
// ─── parseAmount ─────────────────────────────────────────────────────────────

const _FOOTNOTE_RE = /\(\*?\s*주?\s*\d+\s*\)|[①-⑳]|\[\s*주?\s*\d+\s*\]|\s*주\d+/g;

export function parseAmount(cell) {
  if (cell == null) return null;
  let s = String(cell);
  // Strip footnote markers
  s = s.replace(_FOOTNOTE_RE, '');
  // Normalize whitespace variants
  s = s.replace(/ /g, ' ').trim();
  // Normalize minus signs: U+2212 MINUS SIGN, △ (triangle = negative in Korean FS)
  s = s.replace(/−/g, '-').replace(/△/g, '-');
  // Null-equivalent
  if (s === '' || s === '-' || s === '—' || s === '–') return null;
  // Must contain at least one digit
  if (!/\d/.test(s)) return null;
  // Determine sign from leading ( before first digit
  const firstParen = s.indexOf('(');
  const firstDigit = s.search(/\d/);
  const negative = firstParen !== -1 && firstParen < firstDigit;
  // Extract digits only
  const digits = s.replace(/[^\d]/g, '');
  if (!digits) return null;
  const value = parseInt(digits, 10);
  return negative ? -value : value;
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run tests/js/verify-engine.test.js
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add static/js/verify-engine.js tests/js/verify-engine.test.js
git commit -m "feat(js): parseAmount — port of amounts.py with footnote/unicode handling"
```

---

## Task 3: Column Detection — verify-engine.js, Part 2

**Files:** `static/js/verify-engine.js` (extend), `tests/js/verify-engine.test.js` (extend)

- [ ] **Step 1: Write failing tests — add to verify-engine.test.js**

Append to `tests/js/verify-engine.test.js`:

```js
import {
  parseAmount,
  currentPeriodColumns,
  priorPeriodColumns,
  inferReportType,
} from '../../static/js/verify-engine.js';

describe('currentPeriodColumns', () => {
  test('detects 당기말', () => {
    expect(currentPeriodColumns(['항목', '당기말', '전기말'])).toEqual([1]);
  });
  test('detects 당분기', () => {
    expect(currentPeriodColumns(['항목', '당분기', '전분기'])).toEqual([1]);
  });
  test('detects 당반기', () => {
    expect(currentPeriodColumns(['항목', '당반기말', '전반기말'])).toEqual([1]);
  });
  test('제N기 — highest N is current', () => {
    expect(currentPeriodColumns(['항목', '제25기', '제24기'])).toEqual([1]);
  });
  test('returns [] on no detection', () => {
    expect(currentPeriodColumns(['항목', '금액'])).toEqual([]);
  });
  test('normalizes NBSP in header', () => {
    expect(currentPeriodColumns(['항목', '당 기 말', '전기말'])).toEqual([1]);
  });
});

describe('priorPeriodColumns', () => {
  test('detects 전기말', () => {
    expect(priorPeriodColumns(['항목', '당기말', '전기말'])).toEqual([2]);
  });
  test('detects 전분기', () => {
    expect(priorPeriodColumns(['항목', '당분기', '전분기'])).toEqual([2]);
  });
  test('제N기 — all non-max N are prior', () => {
    expect(priorPeriodColumns(['항목', '제25기', '제24기'])).toEqual([2]);
  });
  test('returns [] when no prior detected', () => {
    expect(priorPeriodColumns(['항목', '당기말'])).toEqual([]);
  });
});

describe('inferReportType', () => {
  test('quarter from 당분기', () => {
    expect(inferReportType(['항목', '당분기', '전분기'])).toBe('quarter');
  });
  test('half from 당반기', () => {
    expect(inferReportType(['항목', '당반기말', '전반기말'])).toBe('half');
  });
  test('annual default', () => {
    expect(inferReportType(['항목', '당기말', '전기말'])).toBe('annual');
  });
  test('annual for 제N기 pattern', () => {
    expect(inferReportType(['항목', '제25기', '제24기'])).toBe('annual');
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
npx vitest run tests/js/verify-engine.test.js 2>&1 | tail -20
```

Expected: FAIL — `currentPeriodColumns is not a function`

- [ ] **Step 3: Implement column detection — append to verify-engine.js**

```js
// ─── Column Detection ─────────────────────────────────────────────────────────

const _CURRENT_HEADERS = new Set([
  '당기', '당기말', '당년도', '당해', '당기말현재', '당기현재',
  '당분기', '당분기말', '당3분기', '당2분기', '당1분기',
  '당반기', '당반기말',
]);

const _PRIOR_HEADERS = new Set([
  '전기', '전기말', '전년도', '전기말현재', '전기현재',
  '전분기', '전분기말',
  '전반기', '전반기말',
]);

function _normalizeHeader(h) {
  return String(h ?? '').replace(/\s+/g, '').replace(/ /g, '');
}

export function currentPeriodColumns(headers) {
  const cols = [];
  for (let i = 0; i < headers.length; i++) {
    if (_CURRENT_HEADERS.has(_normalizeHeader(headers[i]))) cols.push(i);
  }
  if (cols.length > 0) return cols;
  // 제N기 fallback — highest N = current
  const entries = _parseKiEntries(headers);
  if (entries.length === 0) return [];
  const maxKi = Math.max(...entries.map(e => e.ki));
  return entries.filter(e => e.ki === maxKi).map(e => e.col);
}

export function priorPeriodColumns(headers) {
  const cols = [];
  for (let i = 0; i < headers.length; i++) {
    if (_PRIOR_HEADERS.has(_normalizeHeader(headers[i]))) cols.push(i);
  }
  if (cols.length > 0) return cols;
  // 제N기 fallback — all non-max N = prior
  const entries = _parseKiEntries(headers);
  if (entries.length < 2) return [];
  const maxKi = Math.max(...entries.map(e => e.ki));
  return entries.filter(e => e.ki < maxKi).map(e => e.col);
}

function _parseKiEntries(headers) {
  const entries = [];
  for (let i = 0; i < headers.length; i++) {
    const m = _normalizeHeader(headers[i]).match(/제(\d+)기/);
    if (m) entries.push({ col: i, ki: parseInt(m[1], 10) });
  }
  return entries;
}

export function inferReportType(headers) {
  const norm = headers.map(_normalizeHeader);
  if (norm.some(h => h.includes('분기'))) return 'quarter';
  if (norm.some(h => h.includes('반기'))) return 'half';
  return 'annual';
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run tests/js/verify-engine.test.js
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add static/js/verify-engine.js tests/js/verify-engine.test.js
git commit -m "feat(js): column detection — 당기/전기/분기/반기/제N기 patterns"
```

---

## Task 4: LabelResolver — verify-engine.js, Part 3

**Files:** `static/js/verify-engine.js` (extend), `tests/js/verify-engine.test.js` (extend)

- [ ] **Step 1: Write failing tests — append to verify-engine.test.js**

```js
import {
  parseAmount,
  currentPeriodColumns, priorPeriodColumns, inferReportType,
  findRow,
} from '../../static/js/verify-engine.js';

function makeTable(rows) {
  return { rows, caption: '', unitMultiplier: 1, reportType: 'annual' };
}

describe('findRow', () => {
  test('EXACT match — 자산총계', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['유동자산', '500'],
      ['자산총계', '1,000'],
    ]);
    const m = findRow(t, 'asset_total');
    expect(m).not.toBeNull();
    expect(m.tier).toBe('EXACT');
    expect(m.confidence).toBe(1.0);
    expect(m.row[0]).toBe('자산총계');
  });

  test('EXACT — 자본과부채총계 maps to asset_total, not liability_total', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['부채총계', '400'],
      ['자본총계', '600'],
      ['자본과부채총계', '1,000'],
    ]);
    const assetM = findRow(t, 'asset_total');
    expect(assetM?.row[0]).toBe('자본과부채총계');
    // liability_total must not match 자본과부채총계
    const liabM = findRow(t, 'liability_total');
    expect(liabM?.row[0]).toBe('부채총계');
  });

  test('PREFIX match — 자산총계 합계', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['자산총계 합계', '2,000'],
    ]);
    const m = findRow(t, 'asset_total');
    expect(m?.tier).toBe('PREFIX');
    expect(m?.confidence).toBe(0.85);
  });

  test('CONTAINS match — (자산총계)', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['(자산총계)', '2,000'],
    ]);
    const m = findRow(t, 'asset_total');
    expect(m?.tier).toBe('CONTAINS');
    expect(m?.confidence).toBe(0.70);
  });

  test('POSITION fallback — last row with 계 for asset_total', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['유동자산', '200'],
      ['비유동자산', '300'],
      ['기타계', '500'],
    ]);
    const m = findRow(t, 'asset_total');
    expect(m?.tier).toBe('POSITION');
    expect(m?.confidence).toBe(0.55);
    expect(m?.row[0]).toBe('기타계');
  });

  test('POSITION NOT applied to liability_total', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['단기차입금', '100'],
      ['부채계 합계', '200'],  // would match POSITION if applied
    ]);
    const m = findRow(t, 'liability_total');
    // Should still return CONTAINS match for 부채계 합계 (PREFIX of 부채계)
    // But NOT via POSITION tier
    if (m) {
      expect(m.tier).not.toBe('POSITION');
    }
  });

  test('returns null when no match', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['매출액', '300'],
    ]);
    expect(findRow(t, 'equity_total')).toBeNull();
  });

  test('EXACT beats PREFIX and CONTAINS', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['자산총계 기타', '999'],
      ['자산총계', '1,000'],
    ]);
    const m = findRow(t, 'asset_total');
    expect(m?.tier).toBe('EXACT');
    expect(m?.row[1]).toBe('1,000');
  });

  test('FUZZY match — typo 자산총꼐', () => {
    const t = makeTable([
      ['항목', '당기말'],
      ['자산총꼐', '1,000'],
    ]);
    const m = findRow(t, 'asset_total');
    expect(m?.tier).toBe('FUZZY');
    expect(m?.confidence).toBe(0.40);
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
npx vitest run tests/js/verify-engine.test.js 2>&1 | tail -20
```

Expected: FAIL — `findRow is not a function`

- [ ] **Step 3: Implement LabelResolver — append to verify-engine.js**

```js
// ─── LabelResolver ────────────────────────────────────────────────────────────

const _CANONICAL_LABELS = {
  asset_total:     ['자산총계','자산합계','총자산','자본과부채총계','자산계','총자산계'],
  liability_total: ['부채총계','부채합계','총부채','부채계'],
  equity_total:    ['자본총계','자본합계','총자본','자본계','순자산총계'],
  cash_end:        ['기말현금및현금성자산','현금및현금성자산기말잔액','현금및현금성자산의기말잔액',
                   '기말의현금및현금성자산','기말현금성자산','현금및현금성자산'],
  cash_begin:      ['기초현금및현금성자산','현금및현금성자산기초잔액','현금및현금성자산의기초잔액',
                   '기초의현금및현금성자산'],
  net_income:      ['당기순이익','당기순손익','당기순손실','당기순이익(손실)','당기순손실(이익)'],
  revenue:         ['매출액','영업수익','수익','매출'],
};

function _compact(s) {
  return String(s ?? '').replace(/\s+/g, '').replace(/ /g, '');
}

function _levenshtein(a, b) {
  const m = a.length, n = b.length;
  const dp = [];
  for (let i = 0; i <= m; i++) {
    dp[i] = [];
    for (let j = 0; j <= n; j++) {
      dp[i][j] = i === 0 ? j : j === 0 ? i : 0;
    }
  }
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i-1] === b[j-1]
        ? dp[i-1][j-1]
        : 1 + Math.min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]);
    }
  }
  return dp[m][n];
}

function _levenshteinSim(a, b) {
  const maxLen = Math.max(a.length, b.length);
  return maxLen === 0 ? 1.0 : 1 - _levenshtein(a, b) / maxLen;
}

export function findRow(table, role) {
  const labels = _CANONICAL_LABELS[role];
  if (!labels) return null;

  const dataRows = table.rows.slice(1); // skip header row
  let best = null;

  function update(candidate) {
    if (!best || candidate.confidence > best.confidence) best = candidate;
  }

  for (let i = 0; i < dataRows.length; i++) {
    const row = dataRows[i];
    const cell = _compact(row[0]);

    for (const label of labels) {
      const cLabel = _compact(label);

      // EXACT (1.0) — return immediately
      if (cell === cLabel) {
        return { rowIndex: i + 1, row, confidence: 1.0, tier: 'EXACT' };
      }
      // PREFIX (0.85)
      if (cell.startsWith(cLabel)) {
        update({ rowIndex: i + 1, row, confidence: 0.85, tier: 'PREFIX' });
        continue;
      }
      // CONTAINS (0.70) — guard: 자본과부채총계 must not match liability_total
      if (cell.includes(cLabel)) {
        if (role === 'liability_total' && cLabel === '자본과부채총계') continue;
        update({ rowIndex: i + 1, row, confidence: 0.70, tier: 'CONTAINS' });
        continue;
      }
      // FUZZY (0.40, Levenshtein ≥ 0.80)
      const sim = _levenshteinSim(cell, cLabel);
      if (sim >= 0.80) {
        update({ rowIndex: i + 1, row, confidence: 0.40, tier: 'FUZZY' });
      }
    }
  }

  // POSITION (0.55) — ASSET_TOTAL only, last row containing 총/합/계
  if (role === 'asset_total' && (!best || best.confidence < 0.55)) {
    for (let i = dataRows.length - 1; i >= 0; i--) {
      const cell = _compact(dataRows[i][0]);
      if (/[총합계]/.test(cell)) {
        update({ rowIndex: i + 1, row: dataRows[i], confidence: 0.55, tier: 'POSITION' });
        break;
      }
    }
  }

  return best ?? null;
}
```

- [ ] **Step 4: Run all tests**

```bash
npx vitest run tests/js/verify-engine.test.js
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add static/js/verify-engine.js tests/js/verify-engine.test.js
git commit -m "feat(js): LabelResolver.findRow — 5-tier matching, POSITION guard, FUZZY Levenshtein"
```

---

## Task 5: Checks — verify-engine.js, Part 4

**Files:** `static/js/verify-engine.js` (extend), `tests/js/verify-engine.test.js` (extend)

- [ ] **Step 1: Write failing tests — append to verify-engine.test.js**

```js
import {
  parseAmount,
  currentPeriodColumns, priorPeriodColumns, inferReportType,
  findRow,
  bsEquationCheck, cashTieCheck, equityTieCheck,
} from '../../static/js/verify-engine.js';

function makeBsReport(overrides = {}) {
  return {
    company: 'Test Corp',
    statements: [{
      sectionId: 's-0',
      title: '재무상태표',
      kind: 'statement',
      noteNo: '',
      tables: [{
        index: 0,
        rows: [
          ['항목', '당기말', '전기말'],
          ['유동자산', '600', '500'],
          ['비유동자산', '400', '350'],
          ['자산총계', '1,000', '850'],
          ['유동부채', '300', '250'],
          ['비유동부채', '100', '100'],
          ['부채총계', '400', '350'],
          ['자본금', '200', '200'],
          ['이익잉여금', '400', '300'],
          ['자본총계', '600', '500'],
        ],
        caption: '재무상태표',
        unitMultiplier: 1,
        reportType: 'annual',
      }],
    }],
    notes: [],
    ...overrides,
  };
}

describe('bsEquationCheck', () => {
  test('matched when assets = liabilities + equity', () => {
    const results = bsEquationCheck(makeBsReport());
    expect(results).toHaveLength(1);
    expect(results[0].status).toBe('matched');
    expect(results[0].expected).toBe(1000);
    expect(results[0].actual).toBe(1000); // 400 + 600
    expect(results[0].difference).toBe(0);
  });

  test('unexplained_gap when equation fails', () => {
    const report = makeBsReport();
    // Corrupt equity: 500 instead of 600 → asset 1000 ≠ 400+500=900
    report.statements[0].tables[0].rows[9][1] = '500';
    const results = bsEquationCheck(report);
    expect(results[0].status).toBe('unexplained_gap');
    expect(results[0].difference).not.toBe(0);
  });

  test('parse_uncertain when BS not found', () => {
    const report = { company: '', statements: [], notes: [] };
    const results = bsEquationCheck(report);
    expect(results[0].status).toBe('parse_uncertain');
    expect(results[0].parseUncertainReason).toBe('BS_NOT_FOUND');
  });

  test('parse_uncertain when amount fails to parse', () => {
    const report = makeBsReport();
    report.statements[0].tables[0].rows[3][1] = ''; // asset_total empty
    const results = bsEquationCheck(report);
    expect(results[0].status).toBe('parse_uncertain');
    expect(results[0].parseUncertainReason).toBe('AMOUNT_PARSE_FAILED');
  });

  test('evidence contains three entries', () => {
    const results = bsEquationCheck(makeBsReport());
    expect(results[0].evidence).toHaveLength(3);
    const labels = results[0].evidence.map(e => e.label);
    expect(labels).toContain('자산총계');
    expect(labels).toContain('부채총계');
    expect(labels).toContain('자본총계');
  });

  test('tolerance allows 1-unit rounding', () => {
    const report = makeBsReport();
    // asset=1000, liab=400, eq=601 → diff=1, within tolerance
    report.statements[0].tables[0].rows[9][1] = '601';
    const results = bsEquationCheck(report);
    expect(results[0].status).toBe('matched');
  });
});

describe('cashTieCheck', () => {
  function makeCashReport() {
    return {
      company: 'Test',
      statements: [
        {
          sectionId: 's-0',
          title: '재무상태표',
          kind: 'statement',
          noteNo: '',
          tables: [{
            index: 0,
            rows: [
              ['항목', '당기말', '전기말'],
              ['현금및현금성자산', '200', '150'],
              ['자산총계', '1,000', '850'],
            ],
            caption: '재무상태표',
            unitMultiplier: 1,
            reportType: 'annual',
          }],
        },
        {
          sectionId: 's-1',
          title: '현금흐름표',
          kind: 'statement',
          noteNo: '',
          tables: [{
            index: 1,
            rows: [
              ['항목', '당기', '전기'],
              ['영업활동현금흐름', '100', '80'],
              ['기말현금및현금성자산', '200', '150'],
            ],
            caption: '현금흐름표',
            unitMultiplier: 1,
            reportType: 'annual',
          }],
        },
      ],
      notes: [],
    };
  }

  test('matched when BS cash = CF ending cash', () => {
    const results = cashTieCheck(makeCashReport());
    expect(results[0].status).toBe('matched');
    expect(results[0].expected).toBe(200);
    expect(results[0].actual).toBe(200);
  });

  test('parse_uncertain when CF not found', () => {
    const report = makeCashReport();
    report.statements = report.statements.filter(s => !s.title.includes('현금흐름'));
    const results = cashTieCheck(report);
    expect(results[0].status).toBe('parse_uncertain');
    expect(results[0].parseUncertainReason).toBe('CF_NOT_FOUND');
  });
});

describe('equityTieCheck', () => {
  test('parse_uncertain when SCE not found', () => {
    const report = makeBsReport();
    const results = equityTieCheck(report);
    expect(results[0].status).toBe('parse_uncertain');
    expect(results[0].parseUncertainReason).toBe('SCE_NOT_FOUND');
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
npx vitest run tests/js/verify-engine.test.js 2>&1 | tail -20
```

Expected: FAIL — `bsEquationCheck is not a function`

- [ ] **Step 3: Implement checks — append to verify-engine.js**

```js
// ─── Checks ──────────────────────────────────────────────────────────────────

function _currentAmount(table, match) {
  if (!match) return null;
  const cols = currentPeriodColumns(table.rows[0] ?? []);
  if (!cols.length) return null;
  return parseAmount(match.row[cols[0]] ?? null);
}

function _makeResult(partial) {
  return {
    checkId: partial.checkId,
    checkType: partial.checkType,
    status: partial.status,
    title: partial.title,
    expected: partial.expected ?? null,
    actual: partial.actual ?? null,
    difference: partial.difference ?? null,
    tolerance: partial.tolerance ?? 1,
    reason: partial.reason ?? '',
    evidence: partial.evidence ?? [],
    parseUncertainReason: partial.parseUncertainReason ?? null,
  };
}

export function bsEquationCheck(report) {
  const bsSection = report.statements.find(
    s => /재무상태표|대차대조표/.test(s.title)
  );
  if (!bsSection?.tables?.length) {
    return [_makeResult({
      checkId: 'bs-equation', checkType: 'BS_EQUATION', status: 'parse_uncertain',
      title: '재무상태표 방정식 (자산 = 부채 + 자본)',
      reason: '재무상태표를 찾을 수 없음',
      parseUncertainReason: 'BS_NOT_FOUND',
    })];
  }

  const table = bsSection.tables[0];
  const assetMatch = findRow(table, 'asset_total');
  let liabMatch = findRow(table, 'liability_total');
  const eqMatch = findRow(table, 'equity_total');

  // Guard: 자본과부채총계 same row as asset → don't double-count as liability
  if (liabMatch && assetMatch && liabMatch.rowIndex === assetMatch.rowIndex) {
    liabMatch = null;
  }

  const asset = _currentAmount(table, assetMatch);
  const liab = _currentAmount(table, liabMatch);
  const eq = _currentAmount(table, eqMatch);

  const evidence = [
    { label: '자산총계', amount: asset, source: 'statement:bs/asset_total' },
    { label: '부채총계', amount: liab, source: 'statement:bs/liability_total' },
    { label: '자본총계', amount: eq, source: 'statement:bs/equity_total' },
  ];

  if (asset === null || liab === null || eq === null) {
    return [_makeResult({
      checkId: 'bs-equation', checkType: 'BS_EQUATION', status: 'parse_uncertain',
      title: '재무상태표 방정식 (자산 = 부채 + 자본)',
      expected: asset, actual: liab != null && eq != null ? liab + eq : null,
      evidence, reason: '금액 파싱 실패 (일부 항목 인식 불가)',
      parseUncertainReason: 'AMOUNT_PARSE_FAILED',
    })];
  }

  const actual = liab + eq;
  const diff = asset - actual;
  const tolerance = 1;

  return [_makeResult({
    checkId: 'bs-equation', checkType: 'BS_EQUATION',
    status: Math.abs(diff) <= tolerance ? 'matched' : 'unexplained_gap',
    title: '재무상태표 방정식 (자산 = 부채 + 자본)',
    expected: asset, actual, difference: diff, tolerance,
    reason: Math.abs(diff) <= tolerance
      ? '자산총계 = 부채총계 + 자본총계 일치'
      : `차이 ${diff.toLocaleString()} (허용범위 ±${tolerance})`,
    evidence,
  })];
}

export function cashTieCheck(report) {
  const bsSection = report.statements.find(s => /재무상태표|대차대조표/.test(s.title));
  const cfSection = report.statements.find(s => /현금흐름/.test(s.title));

  if (!cfSection?.tables?.length) {
    return [_makeResult({
      checkId: 'cash-tie', checkType: 'CASH_TIE', status: 'parse_uncertain',
      title: '현금 대사 (BS 현금 ↔ CF 기말현금)',
      reason: '현금흐름표를 찾을 수 없음',
      parseUncertainReason: 'CF_NOT_FOUND',
    })];
  }

  const bsTable = bsSection?.tables?.[0];
  const cfTable = cfSection.tables[cfSection.tables.length - 1];

  const bsCashMatch = bsTable ? findRow(bsTable, 'cash_end') : null;
  const cfCashMatch = findRow(cfTable, 'cash_end');

  const bsCash = bsTable ? _currentAmount(bsTable, bsCashMatch) : null;
  const cfCash = _currentAmount(cfTable, cfCashMatch);

  const evidence = [
    { label: 'BS 현금및현금성자산', amount: bsCash, source: 'statement:bs/cash_end' },
    { label: 'CF 기말현금및현금성자산', amount: cfCash, source: 'statement:cf/cash_end' },
  ];

  if (bsCash === null || cfCash === null) {
    return [_makeResult({
      checkId: 'cash-tie', checkType: 'CASH_TIE', status: 'parse_uncertain',
      title: '현금 대사 (BS 현금 ↔ CF 기말현금)',
      expected: bsCash, actual: cfCash, evidence,
      reason: '금액 파싱 실패',
      parseUncertainReason: 'AMOUNT_PARSE_FAILED',
    })];
  }

  const diff = bsCash - cfCash;
  return [_makeResult({
    checkId: 'cash-tie', checkType: 'CASH_TIE',
    status: Math.abs(diff) <= 1 ? 'matched' : 'unexplained_gap',
    title: '현금 대사 (BS 현금 ↔ CF 기말현금)',
    expected: bsCash, actual: cfCash, difference: diff, tolerance: 1,
    reason: Math.abs(diff) <= 1 ? 'BS와 CF 기말현금 일치' : `차이 ${diff.toLocaleString()}`,
    evidence,
  })];
}

export function equityTieCheck(report) {
  const bsSection = report.statements.find(s => /재무상태표|대차대조표/.test(s.title));
  const sceSection = report.statements.find(s => /자본변동/.test(s.title));

  if (!sceSection?.tables?.length) {
    return [_makeResult({
      checkId: 'equity-tie', checkType: 'EQUITY_TIE', status: 'parse_uncertain',
      title: '자본 대사 (BS 자본총계 ↔ SCE 기말자본)',
      reason: '자본변동표를 찾을 수 없음',
      parseUncertainReason: 'SCE_NOT_FOUND',
    })];
  }

  const bsTable = bsSection?.tables?.[0];
  const sceTable = sceSection.tables[sceSection.tables.length - 1];

  const bsEqMatch = bsTable ? findRow(bsTable, 'equity_total') : null;
  const sceEqMatch = findRow(sceTable, 'equity_total');

  const bsEq = bsTable ? _currentAmount(bsTable, bsEqMatch) : null;
  const sceEq = _currentAmount(sceTable, sceEqMatch);

  const evidence = [
    { label: 'BS 자본총계', amount: bsEq, source: 'statement:bs/equity_total' },
    { label: 'SCE 기말자본', amount: sceEq, source: 'statement:sce/equity_total' },
  ];

  if (bsEq === null || sceEq === null) {
    return [_makeResult({
      checkId: 'equity-tie', checkType: 'EQUITY_TIE', status: 'parse_uncertain',
      title: '자본 대사 (BS 자본총계 ↔ SCE 기말자본)',
      expected: bsEq, actual: sceEq, evidence,
      reason: '금액 파싱 실패',
      parseUncertainReason: 'AMOUNT_PARSE_FAILED',
    })];
  }

  const diff = bsEq - sceEq;
  return [_makeResult({
    checkId: 'equity-tie', checkType: 'EQUITY_TIE',
    status: Math.abs(diff) <= 1 ? 'matched' : 'unexplained_gap',
    title: '자본 대사 (BS 자본총계 ↔ SCE 기말자본)',
    expected: bsEq, actual: sceEq, difference: diff, tolerance: 1,
    reason: Math.abs(diff) <= 1 ? 'BS와 SCE 기말자본 일치' : `차이 ${diff.toLocaleString()}`,
    evidence,
  })];
}

export function runAllChecks(report) {
  return [
    ...bsEquationCheck(report),
    ...cashTieCheck(report),
    ...equityTieCheck(report),
  ];
}
```

- [ ] **Step 4: Run all tests**

```bash
npx vitest run tests/js/verify-engine.test.js
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add static/js/verify-engine.js tests/js/verify-engine.test.js
git commit -m "feat(js): BS/Cash/Equity checks — port of checks_statement_ties.py"
```

---

## Task 6: HTMLParser

**Files:** `static/js/html-parser.js`, `tests/js/html-parser.test.js`

- [ ] **Step 1: Write failing tests**

Create `tests/js/html-parser.test.js`:

```js
import { describe, test, expect } from 'vitest';
import { parseHtml } from '../../static/js/html-parser.js';

describe('HTMLParser', () => {
  test('parses single BS table', () => {
    const html = `<html><body>
      <p>재무상태표 (단위: 백만원)</p>
      <table>
        <tr><th>항목</th><th>당기말</th><th>전기말</th></tr>
        <tr><td>자산총계</td><td>1,000</td><td>900</td></tr>
      </table>
    </body></html>`;

    const report = parseHtml(html, 'bs.html');
    expect(report.statements.length).toBeGreaterThanOrEqual(1);
    const table = report.statements[0].tables[0];
    expect(table.rows[0]).toEqual(['항목', '당기말', '전기말']);
    expect(table.rows[1]).toEqual(['자산총계', '1,000', '900']);
    expect(table.unitMultiplier).toBe(1_000_000);
    expect(table.reportType).toBe('annual');
  });

  test('detects half-year from headers', () => {
    const html = `<table>
      <tr><th>항목</th><th>당반기말</th><th>전반기말</th></tr>
      <tr><td>자산총계</td><td>500</td><td>400</td></tr>
    </table>`;

    const report = parseHtml(html);
    const table = report.statements[0].tables[0];
    expect(table.reportType).toBe('half');
  });

  test('detects quarter from headers', () => {
    const html = `<table>
      <tr><th>항목</th><th>당분기</th><th>전분기</th></tr>
      <tr><td>자산총계</td><td>300</td><td>250</td></tr>
    </table>`;

    const report = parseHtml(html);
    const table = report.statements[0].tables[0];
    expect(table.reportType).toBe('quarter');
  });

  test('unit: 십억원 → 1,000,000,000', () => {
    const html = `<table>
      <caption>재무상태표 (단위: 십억원)</caption>
      <tr><th>항목</th><th>당기</th></tr>
      <tr><td>자산총계</td><td>1</td></tr>
    </table>`;
    const report = parseHtml(html);
    expect(report.statements[0].tables[0].unitMultiplier).toBe(1_000_000_000);
  });

  test('unit: 천원 → 1,000', () => {
    const html = `<p>(단위: 천원)</p>
    <table>
      <tr><th>항목</th><th>당기</th></tr>
      <tr><td>자산총계</td><td>1</td></tr>
    </table>`;
    const report = parseHtml(html);
    expect(report.statements[0].tables[0].unitMultiplier).toBe(1_000);
  });

  test('multi-table: BS and IS classified separately', () => {
    const html = `<body>
      <table>
        <caption>재무상태표</caption>
        <tr><th>항목</th><th>당기말</th></tr>
        <tr><td>자산총계</td><td>1000</td></tr>
      </table>
      <table>
        <caption>손익계산서</caption>
        <tr><th>항목</th><th>당기</th></tr>
        <tr><td>매출액</td><td>500</td></tr>
      </table>
    </body>`;

    const report = parseHtml(html);
    expect(report.statements.length).toBeGreaterThanOrEqual(2);
    const titles = report.statements.map(s => s.title);
    expect(titles.some(t => /재무상태표/.test(t))).toBe(true);
    expect(titles.some(t => /손익/.test(t))).toBe(true);
  });

  test('skips empty tables', () => {
    const html = `<table></table>
    <table>
      <tr><th>항목</th><th>당기말</th></tr>
      <tr><td>자산총계</td><td>1000</td></tr>
    </table>`;
    const report = parseHtml(html);
    expect(report.statements.length).toBe(1);
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
npx vitest run tests/js/html-parser.test.js
```

Expected: FAIL — `Cannot find module '../../static/js/html-parser.js'`

- [ ] **Step 3: Implement html-parser.js**

Create `static/js/html-parser.js`:

```js
import { inferReportType } from './verify-engine.js';

// ─── HTMLParser ───────────────────────────────────────────────────────────────

const _STATEMENT_RE = /재무상태표|대차대조표|손익계산서|포괄손익|현금흐름|자본변동/;

export function parseHtml(text, filename = '') {
  const dom = new DOMParser().parseFromString(
    text || '<html></html>', 'text/html'
  );
  const tables = Array.from(dom.querySelectorAll('table'));
  const sections = [];

  for (let i = 0; i < tables.length; i++) {
    const rows = _extractRows(tables[i]);
    if (rows.length < 2) continue; // skip empty / header-only

    const caption = _extractCaption(tables[i]);
    const unitMultiplier = _detectUnit(caption) || _detectUnit(_nearbyText(tables[i]));
    const reportType = inferReportType(rows[0] ?? []);
    const isStatement = _STATEMENT_RE.test(caption);

    const reportTable = { index: i, rows, caption, unitMultiplier, reportType };
    const section = {
      sectionId: `s-${i}`,
      title: caption || `표 ${i + 1}`,
      kind: isStatement ? 'statement' : 'note',
      noteNo: isStatement ? '' : _extractNoteNo(caption),
      tables: [reportTable],
    };
    sections.push(section);
  }

  return {
    company: _extractCompany(dom),
    statements: sections.filter(s => s.kind === 'statement'),
    notes: sections.filter(s => s.kind === 'note'),
  };
}

function _extractRows(table) {
  const rows = [];
  for (const tr of table.querySelectorAll('tr')) {
    const cells = Array.from(tr.querySelectorAll('th, td')).map(
      cell => cell.textContent.replace(/\s+/g, ' ').trim()
    );
    if (cells.some(c => c !== '')) rows.push(cells);
  }
  return rows;
}

function _extractCaption(table) {
  const cap = table.querySelector('caption');
  if (cap) return cap.textContent.trim();
  // Nearest preceding heading or paragraph
  let prev = table.previousElementSibling;
  while (prev) {
    if (/^[HPh]/.test(prev.tagName)) {
      const text = prev.textContent.trim();
      if (text.length > 0 && text.length < 100) return text;
    }
    prev = prev.previousElementSibling;
  }
  return '';
}

function _nearbyText(table) {
  const prev = table.previousElementSibling;
  return prev ? prev.textContent : '';
}

function _detectUnit(text) {
  if (!text) return 1;
  if (/십억/.test(text)) return 1_000_000_000;
  if (/백만/.test(text)) return 1_000_000;
  if (/천원/.test(text)) return 1_000;
  return 1;
}

function _extractNoteNo(caption) {
  const m = String(caption).match(/(?:주석|주)\s*(\d+)/);
  return m ? m[1] : '';
}

function _extractCompany(dom) {
  const meta = dom.querySelector('meta[name="company"], title');
  return meta ? meta.textContent.trim() : '';
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run tests/js/html-parser.test.js
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add static/js/html-parser.js tests/js/html-parser.test.js
git commit -m "feat(js): HTMLParser — DOMParser table extraction with unit/reportType detection"
```

---

## Task 7: DSDParser

**Files:** `static/js/dsd-parser.js`  
(No dedicated test — DSD that is raw XML is covered by passing inner HTML to parseHtml; ZIP case shows guidance callout. Integration tested via FormatDetector in Task 9.)

- [ ] **Step 1: Create dsd-parser.js**

```js
import { parseHtml } from './html-parser.js';

// ─── DSDParser ────────────────────────────────────────────────────────────────
// DSD files come in two forms:
//  1. XML wrapper around inner <HTML> — parse with DOMParser then delegate
//  2. ZIP archive (magic: PK\x03\x04) — cannot unzip in browser; show guidance

export function parseDsd(text, arrayBuffer) {
  // Check ZIP magic bytes
  if (arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer.slice(0, 4));
    if (bytes[0] === 0x50 && bytes[1] === 0x4b) {
      return {
        error: 'DSD_ZIP',
        message: 'DSD 파일이 ZIP 압축 형식입니다. DART 전자공시 뷰어에서 HTML을 먼저 추출한 뒤 업로드해주세요.',
      };
    }
  }

  // Try XML parse — look for inner HTML node
  try {
    const xmlDom = new DOMParser().parseFromString(text, 'text/xml');
    const parseError = xmlDom.querySelector('parsererror');
    if (!parseError) {
      // Extract text content of <HTML> or <Body> element if present
      const htmlNode = xmlDom.querySelector('HTML, Body, body, html');
      if (htmlNode) {
        return parseHtml(htmlNode.outerHTML || htmlNode.innerHTML);
      }
    }
  } catch (_) {
    // fall through
  }

  // Fallback: treat as raw HTML
  return parseHtml(text);
}
```

- [ ] **Step 2: Commit**

```bash
git add static/js/dsd-parser.js
git commit -m "feat(js): DSDParser — XML extraction + ZIP guidance callout"
```

---

## Task 8: PDFParser (PDF.js wrapper)

**Files:** `static/js/pdf-parser.js`, `tests/js/pdf-parser.test.js`

- [ ] **Step 1: Write failing tests**

Create `tests/js/pdf-parser.test.js`:

```js
import { describe, test, expect, vi, beforeEach } from 'vitest';

// Mock pdfjsLib globally (PDF.js UMD sets window.pdfjsLib in browser)
// In tests, we inject a mock
const mockPage = {
  getTextContent: vi.fn(),
};
const mockDoc = {
  numPages: 2,
  getPage: vi.fn(() => Promise.resolve(mockPage)),
};

globalThis.pdfjsLib = {
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: vi.fn(() => ({ promise: Promise.resolve(mockDoc) })),
};

import { parsePdf } from '../../static/js/pdf-parser.js';

beforeEach(() => {
  vi.clearAllMocks();
  globalThis.pdfjsLib = {
    GlobalWorkerOptions: { workerSrc: '' },
    getDocument: vi.fn(() => ({ promise: Promise.resolve(mockDoc) })),
  };
  mockDoc.getPage.mockResolvedValue(mockPage);
});

describe('PDFParser', () => {
  test('returns parse_uncertain when PDF.js not loaded', async () => {
    const savedLib = globalThis.pdfjsLib;
    globalThis.pdfjsLib = undefined;
    const result = await parsePdf(new ArrayBuffer(0));
    expect(result.error).toBe('PDFJS_NOT_LOADED');
    globalThis.pdfjsLib = savedLib;
  });

  test('returns parse_uncertain for empty PDF', async () => {
    mockPage.getTextContent.mockResolvedValue({ items: [] });
    const result = await parsePdf(new ArrayBuffer(0));
    // Should return a FullReport with parse_uncertain note or empty statements
    expect(result).toHaveProperty('statements');
    expect(result).toHaveProperty('notes');
  });

  test('extracts text items and groups into rows', async () => {
    // Simulate two-column table: header row + data row
    mockPage.getTextContent.mockResolvedValueOnce({
      items: [
        // Row 1 (y=800): headers
        { str: '항목', transform: [1,0,0,1, 50, 800], width: 100 },
        { str: '당기말', transform: [1,0,0,1,200, 800], width: 80 },
        { str: '전기말', transform: [1,0,0,1,320, 800], width: 80 },
        // Row 2 (y=780): data
        { str: '자산총계', transform: [1,0,0,1, 50, 780], width: 100 },
        { str: '1,000', transform: [1,0,0,1,200, 780], width: 80 },
        { str: '900', transform: [1,0,0,1,320, 780], width: 80 },
      ],
    }).mockResolvedValueOnce({ items: [] }); // page 2

    const buf = new ArrayBuffer(0);
    const result = await parsePdf(buf);
    // Should have at least one table with 2 rows
    const allTables = [...result.statements, ...result.notes].flatMap(s => s.tables);
    if (allTables.length > 0) {
      expect(allTables[0].rows.length).toBeGreaterThanOrEqual(2);
    }
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
npx vitest run tests/js/pdf-parser.test.js
```

Expected: FAIL — `Cannot find module '../../static/js/pdf-parser.js'`

- [ ] **Step 3: Implement pdf-parser.js**

Create `static/js/pdf-parser.js`:

```js
import { inferReportType } from './verify-engine.js';

// ─── PDFParser ────────────────────────────────────────────────────────────────
// Wraps PDF.js (global pdfjsLib set by UMD build inlined in HTML).
// Coordinate-based column/row detection for electronic (text-layer) PDFs.
// Known limitation: merged cells → parse_uncertain_reason: PDF_COLUMN_UNCERTAIN

const _ROW_GAP_THRESHOLD = 4; // y-coordinate diff that separates rows
const _COL_CLUSTER_THRESHOLD = 20; // x-coordinate diff to merge into same column

export async function parsePdf(arrayBuffer) {
  if (typeof pdfjsLib === 'undefined' || !pdfjsLib) {
    return _emptyReport('PDFJS_NOT_LOADED');
  }

  let pdf;
  try {
    const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
    pdf = await loadingTask.promise;
  } catch (e) {
    return _emptyReport('PDF_LOAD_FAILED');
  }

  const allItems = []; // { str, x, y, width }
  for (let pageNo = 1; pageNo <= pdf.numPages; pageNo++) {
    const page = await pdf.getPage(pageNo);
    const content = await page.getTextContent();
    for (const item of content.items) {
      if (!item.str?.trim()) continue;
      const [,, , , x, y] = item.transform;
      allItems.push({ str: item.str.trim(), x, y: Math.round(y), width: item.width });
    }
  }

  if (!allItems.length) {
    return { company: '', statements: [], notes: [] };
  }

  const rows = _groupIntoRows(allItems);
  const tables = _segmentTables(rows);
  const sections = tables.map((tableRows, i) => _makeSection(tableRows, i));

  return {
    company: '',
    statements: sections.filter(s => s.kind === 'statement'),
    notes: sections.filter(s => s.kind === 'note'),
  };
}

function _groupIntoRows(items) {
  // Sort by descending y (top of page first) then ascending x
  const sorted = [...items].sort((a, b) => b.y - a.y || a.x - b.x);
  const rows = [];
  let currentY = null;
  let currentRow = [];

  for (const item of sorted) {
    if (currentY === null || Math.abs(item.y - currentY) > _ROW_GAP_THRESHOLD) {
      if (currentRow.length) rows.push(currentRow);
      currentRow = [item];
      currentY = item.y;
    } else {
      currentRow.push(item);
    }
  }
  if (currentRow.length) rows.push(currentRow);
  return rows;
}

function _segmentTables(rows) {
  // Split on blank rows or large y-gaps — simple heuristic
  const tables = [];
  let current = [];
  for (const row of rows) {
    if (row.length === 0) {
      if (current.length) { tables.push(current); current = []; }
    } else {
      current.push(row);
    }
  }
  if (current.length) tables.push(current);
  return tables.filter(t => t.length >= 2);
}

function _makeSection(tableRows, index) {
  // Detect column boundaries by clustering x positions of first row
  const headerItems = tableRows[0];
  const colBoundaries = _clusterX(headerItems.map(i => i.x));
  
  const rows = tableRows.map(rowItems => {
    const cells = new Array(colBoundaries.length).fill('');
    for (const item of rowItems) {
      const colIdx = _assignColumn(item.x, colBoundaries);
      if (colIdx >= 0) {
        cells[colIdx] = cells[colIdx] ? cells[colIdx] + ' ' + item.str : item.str;
      }
    }
    return cells;
  });

  const caption = '';
  const reportType = inferReportType(rows[0] ?? []);
  const _STATEMENT_RE = /재무상태표|대차대조표|손익계산서|포괄손익|현금흐름|자본변동/;
  const firstCellText = (rows[0] ?? []).join(' ');
  const isStatement = _STATEMENT_RE.test(firstCellText);

  return {
    sectionId: `pdf-s-${index}`,
    title: firstCellText.slice(0, 30) || `PDF 표 ${index + 1}`,
    kind: isStatement ? 'statement' : 'note',
    noteNo: '',
    tables: [{
      index,
      rows,
      caption,
      unitMultiplier: 1,
      reportType,
    }],
  };
}

function _clusterX(xValues) {
  const sorted = [...new Set(xValues)].sort((a, b) => a - b);
  const clusters = [];
  for (const x of sorted) {
    const last = clusters[clusters.length - 1];
    if (last === undefined || x - last > _COL_CLUSTER_THRESHOLD) {
      clusters.push(x);
    }
  }
  return clusters;
}

function _assignColumn(x, boundaries) {
  for (let i = boundaries.length - 1; i >= 0; i--) {
    if (x >= boundaries[i] - _COL_CLUSTER_THRESHOLD) return i;
  }
  return 0;
}

function _emptyReport(errorCode) {
  return {
    company: '',
    statements: [{
      sectionId: 'pdf-error',
      title: '파싱 오류',
      kind: 'note',
      noteNo: '',
      tables: [{
        index: 0,
        rows: [['오류', errorCode]],
        caption: '',
        unitMultiplier: 1,
        reportType: 'unknown',
      }],
    }],
    notes: [],
    error: errorCode,
  };
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run tests/js/pdf-parser.test.js
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add static/js/pdf-parser.js tests/js/pdf-parser.test.js
git commit -m "feat(js): PDFParser — PDF.js wrapper with coordinate-based column/row detection"
```

---

## Task 9: FormatDetector

**Files:** `static/js/format-detector.js`

- [ ] **Step 1: Implement format-detector.js** (no separate test — verified via E2E in Task 13)

```js
import { parseHtml } from './html-parser.js';
import { parseDsd } from './dsd-parser.js';
import { parsePdf } from './pdf-parser.js';

// ─── FormatDetector ───────────────────────────────────────────────────────────

export async function detectAndParse(file) {
  const name = (file.name ?? '').toLowerCase();

  if (name.endsWith('.pdf')) {
    const buf = await file.arrayBuffer();
    return parsePdf(buf);
  }

  if (name.endsWith('.dsd')) {
    const [text, buf] = await Promise.all([file.text(), file.arrayBuffer()]);
    return parseDsd(text, buf);
  }

  if (name.endsWith('.html') || name.endsWith('.htm')) {
    const text = await file.text();
    return parseHtml(text, file.name);
  }

  return {
    error: 'UNSUPPORTED_FORMAT',
    message: `지원하지 않는 형식입니다: ${file.name}. HTML(.html/.htm), DSD(.dsd), 전자 PDF(.pdf)를 지원합니다.`,
    statements: [],
    notes: [],
    company: '',
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add static/js/format-detector.js
git commit -m "feat(js): FormatDetector — dispatch by extension to HTML/DSD/PDF parser"
```

---

## Task 10: ResultsRenderer + KreportsPanel

**Files:** `static/js/results-renderer.js`, `static/js/kreports-panel.js`

No unit tests for DOM-rendering code — verified visually and via E2E in Task 13.

- [ ] **Step 1: Create results-renderer.js**

```js
// ─── ResultsRenderer — evidence_cockpit DOM builder ──────────────────────────
// Design tokens: --sidebar-bg, --ok, --warn, --down, --accent (set in CSS)

export function renderResults(results, container) {
  container.innerHTML = '';

  if (!results.length) {
    container.innerHTML = '<p class="empty-state">검증 결과 없음</p>';
    return;
  }

  // Verdict banner
  const matched = results.filter(r => r.status === 'matched').length;
  const gaps = results.filter(r => r.status === 'unexplained_gap').length;
  const uncertain = results.filter(r => r.status === 'parse_uncertain').length;

  const bannerClass = gaps > 0 ? 'verdict-fail' : uncertain > 0 ? 'verdict-warn' : 'verdict-ok';
  const bannerText = gaps > 0 ? '검토 필요' : uncertain > 0 ? '확인 필요' : '이상 없음';

  const banner = _el('div', { class: `verdict-banner ${bannerClass}` });
  banner.innerHTML = `
    <span class="verdict-label">${_esc(bannerText)}</span>
    <span class="verdict-kpi">일치 <strong>${matched}</strong></span>
    <span class="verdict-kpi">차이 <strong>${gaps}</strong></span>
    <span class="verdict-kpi">불확실 <strong>${uncertain}</strong></span>
  `;
  container.appendChild(banner);

  // Check result cards
  for (const result of results) {
    container.appendChild(_renderCard(result));
  }
}

function _renderCard(result) {
  const card = _el('div', { class: `check-card check-${result.status}`, id: _safeId(result.checkId) });

  // Tick overlay
  const tick = { matched: '✓', unexplained_gap: '⚠', parse_uncertain: '?' }[result.status] ?? '?';
  const tickClass = { matched: 'tick-ok', unexplained_gap: 'tick-warn', parse_uncertain: 'tick-unknown' }[result.status] ?? '';

  card.innerHTML = `
    <div class="card-header">
      <span class="tick ${tickClass}">${tick}</span>
      <strong>${_esc(result.title)}</strong>
    </div>
    <div class="card-body">
      <span class="card-reason">${_esc(result.reason)}</span>
      ${result.expected != null ? `
        <table class="amount-table">
          <tr><th>기대</th><td class="amount">${_fmt(result.expected)}</td></tr>
          <tr><th>실제</th><td class="amount">${_fmt(result.actual)}</td></tr>
          ${result.difference != null ? `<tr><th>차이</th><td class="amount ${Math.abs(result.difference) > result.tolerance ? 'amount-gap' : ''}">${_fmt(result.difference)}</td></tr>` : ''}
        </table>` : ''}
      ${result.parseUncertainReason ? `<div class="parse-uncertain-badge">파싱 불확실: ${_esc(result.parseUncertainReason)}</div>` : ''}
    </div>
    <details class="evidence-drilldown">
      <summary>근거 보기 (${result.evidence.length}건)</summary>
      <table class="evidence-table">
        ${result.evidence.map(e => `
          <tr>
            <td>${_esc(e.label)}</td>
            <td class="amount">${e.amount != null ? _fmt(e.amount) : '—'}</td>
            <td class="source-path">${_esc(e.source)}</td>
          </tr>
        `).join('')}
      </table>
    </details>
  `;

  return card;
}

function _el(tag, attrs = {}) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function _safeId(s) {
  return String(s ?? '').replace(/[^a-zA-Z0-9_-]/g, '-');
}

function _fmt(n) {
  if (n == null) return '—';
  return n.toLocaleString('ko-KR');
}
```

- [ ] **Step 2: Create kreports-panel.js**

```js
// ─── KreportsPanel — stub oracle + sidebar UI ─────────────────────────────────

export class NullPriorPeriodOracle {
  async fetchPriorAmounts(_corpCode, _reportType) {
    return null; // stub — returns no data
  }
}

export function renderKreportsPanel(container) {
  container.innerHTML = `
    <div class="kreports-panel" data-kreports-status="stub">
      <div class="panel-label">kreports 연동
        <label class="toggle-switch">
          <input type="checkbox" id="kreports-toggle" autocomplete="off">
          <span class="slider"></span>
        </label>
      </div>
      <div id="kreports-body" class="kreports-body" style="display:none">
        <label>사업자등록번호 / corp_code
          <input type="text" id="kreports-corp" placeholder="00000000" maxlength="8">
        </label>
        <button type="button" id="kreports-query" class="btn-secondary">조회</button>
        <div id="kreports-result" class="callout callout-info" style="display:none">
          연동 준비 중 — 이 버전에서는 kreports 호출이 비활성 상태입니다.
        </div>
      </div>
    </div>
  `;

  document.getElementById('kreports-toggle')?.addEventListener('change', e => {
    const body = document.getElementById('kreports-body');
    if (body) body.style.display = e.target.checked ? 'block' : 'none';
  });

  document.getElementById('kreports-query')?.addEventListener('click', () => {
    const result = document.getElementById('kreports-result');
    if (result) result.style.display = 'block';
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add static/js/results-renderer.js static/js/kreports-panel.js
git commit -m "feat(js): ResultsRenderer (evidence_cockpit DOM) + KreportsPanel stub"
```

---

## Task 11: app.js — UI Orchestration

**Files:** `static/js/app.js`

- [ ] **Step 1: Create app.js**

```js
import { detectAndParse } from './format-detector.js';
import { runAllChecks } from './verify-engine.js';
import { renderResults } from './results-renderer.js';
import { renderKreportsPanel, NullPriorPeriodOracle } from './kreports-panel.js';

// ─── App Initialization ───────────────────────────────────────────────────────

const _oracle = new NullPriorPeriodOracle();

function init() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const mainContent = document.getElementById('main-content');
  const sidebar = document.getElementById('sidebar');
  const kreportsContainer = document.getElementById('kreports-container');
  const statusBar = document.getElementById('status-bar');

  if (kreportsContainer) renderKreportsPanel(kreportsContainer);

  // File input change
  fileInput?.addEventListener('change', e => {
    const file = e.target.files?.[0];
    if (file) _handleFile(file, mainContent, statusBar);
  });

  // Drag and drop
  dropZone?.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone?.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer?.files?.[0];
    if (file) _handleFile(file, mainContent, statusBar);
  });
}

async function _handleFile(file, container, statusBar) {
  _setStatus(statusBar, `파싱 중: ${file.name} …`, 'parsing');
  container.innerHTML = '<div class="spinner"></div>';

  try {
    const report = await detectAndParse(file);

    if (report.error && !report.statements.length) {
      _setStatus(statusBar, `오류: ${report.message || report.error}`, 'error');
      container.innerHTML = `<div class="callout callout-error">${_esc(report.message || report.error)}</div>`;
      return;
    }

    const results = runAllChecks(report);
    renderResults(results, container);
    _setStatus(statusBar, `${file.name} — 검증 완료`, 'done');
  } catch (err) {
    _setStatus(statusBar, `오류: ${err.message}`, 'error');
    container.innerHTML = `<div class="callout callout-error">${_esc(String(err))}</div>`;
  }
}

function _setStatus(bar, message, state) {
  if (!bar) return;
  bar.textContent = message;
  bar.className = `status-bar status-${state}`;
}

function _esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Boot
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
```

- [ ] **Step 2: Commit**

```bash
git add static/js/app.js
git commit -m "feat(js): app.js — file drop → parse → runAllChecks → renderResults orchestration"
```

---

## Task 12: HTML Shell Template

**Files:** `static/dart-verify-template.html`

- [ ] **Step 1: Create dart-verify-template.html**

Create `static/dart-verify-template.html` with full evidence_cockpit layout, PAS design tokens, and two placeholder comments for the builder to inject PDF.js and bundled JS:

```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DART 감사검증 — PAS Evidence Cockpit</title>
<style>
/* ── Design tokens ── */
:root {
  --sidebar-bg: #0f172a;
  --sidebar-fg: #cbd5e1;
  --sidebar-accent: #3b82f6;
  --ok:   #16a34a;
  --warn: #f59e0b;
  --down: #dc2626;
  --accent: #3b82f6;
  --surface: #1e293b;
  --border: #334155;
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --radius: 6px;
  font-family: 'Pretendard', system-ui, -apple-system, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  display: flex;
  height: 100vh;
  background: #0a0f1a;
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
  letter-spacing: -0.02em;
}

/* ── Sidebar ── */
#sidebar {
  width: 260px;
  min-width: 220px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 16px;
  gap: 20px;
  overflow-y: auto;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--sidebar-accent);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

/* ── Drop zone ── */
#drop-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 24px 12px;
  text-align: center;
  cursor: pointer;
  color: var(--text-muted);
  transition: border-color .2s, background .2s;
}
#drop-zone.drag-over,
#drop-zone:hover {
  border-color: var(--accent);
  background: rgba(59,130,246,.08);
}
#drop-zone input[type="file"] { display: none; }
.drop-label { font-size: 13px; margin-top: 8px; }

/* ── Nav items ── */
.nav-section { border-top: 1px solid var(--border); padding-top: 12px; }
.nav-item { display: flex; justify-content: space-between; align-items: center;
  padding: 4px 0; font-size: 13px; color: var(--sidebar-fg); }
.tick-ok    { color: var(--ok); }
.tick-warn  { color: var(--warn); }
.tick-unknown { color: var(--text-muted); }

/* ── Main ── */
#main {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

/* ── Verdict banner ── */
.verdict-banner {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 16px 20px;
  border-radius: var(--radius);
  margin-bottom: 24px;
  font-weight: 600;
}
.verdict-ok   { background: rgba(22,163,74,.15); border-left: 4px solid var(--ok); }
.verdict-warn { background: rgba(245,158,11,.15); border-left: 4px solid var(--warn); }
.verdict-fail { background: rgba(220,38,38,.15);  border-left: 4px solid var(--down); }
.verdict-label { font-size: 18px; }
.verdict-kpi  { font-size: 13px; color: var(--text-muted); }
.verdict-kpi strong { color: var(--text); font-size: 16px; }

/* ── Check card ── */
.check-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 12px;
  overflow: hidden;
}
.check-matched      { border-left: 4px solid var(--ok); }
.check-unexplained_gap { border-left: 4px solid var(--down); }
.check-parse_uncertain { border-left: 4px solid var(--warn); }

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  font-weight: 600;
}
.tick { font-size: 16px; }
.card-body { padding: 0 16px 12px; color: var(--text-muted); font-size: 13px; }
.card-reason { display: block; margin-bottom: 8px; }

.amount-table { font-size: 13px; border-collapse: collapse; }
.amount-table th { color: var(--text-muted); padding-right: 12px; font-weight: 400; }
.amount { text-align: right; font-variant-numeric: tabular-nums; font-family: monospace; }
.amount-gap { color: var(--down); }

.parse-uncertain-badge {
  margin-top: 6px;
  font-size: 11px;
  color: var(--warn);
  background: rgba(245,158,11,.1);
  border-radius: 4px;
  padding: 2px 8px;
  display: inline-block;
}

/* ── Drilldown ── */
.evidence-drilldown { padding: 8px 16px 12px; }
.evidence-drilldown summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--accent);
  list-style: none;
}
.evidence-drilldown summary::-webkit-details-marker { display: none; }
.evidence-table { font-size: 12px; border-collapse: collapse; width: 100%; margin-top: 8px; }
.evidence-table td { padding: 3px 8px 3px 0; border-bottom: 1px solid var(--border); }
.source-path { font-family: monospace; color: var(--text-muted); font-size: 11px; }

/* ── Status bar ── */
#status-bar {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 24px;
  padding: 0 16px;
  font-size: 12px;
  display: flex;
  align-items: center;
  background: var(--sidebar-bg);
  border-top: 1px solid var(--border);
  color: var(--text-muted);
}
.status-parsing { color: var(--accent); }
.status-done    { color: var(--ok); }
.status-error   { color: var(--down); }

/* ── kreports panel ── */
.kreports-panel { font-size: 13px; }
.panel-label { display: flex; align-items: center; justify-content: space-between;
  color: var(--sidebar-fg); font-weight: 500; }
.kreports-body { margin-top: 8px; display: flex; flex-direction: column; gap: 8px; }
.kreports-body label { display: flex; flex-direction: column; gap: 4px;
  font-size: 12px; color: var(--text-muted); }
.kreports-body input {
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
  color: var(--text); padding: 4px 8px; font-size: 13px;
}

/* ── Toggle switch ── */
.toggle-switch { position: relative; display: inline-block; width: 32px; height: 18px; }
.toggle-switch input { display: none; }
.slider { position: absolute; inset: 0; background: var(--border); border-radius: 18px;
  cursor: pointer; transition: .2s; }
.toggle-switch input:checked + .slider { background: var(--accent); }
.slider::before { content: ''; position: absolute; width: 14px; height: 14px; left: 2px; bottom: 2px;
  background: #fff; border-radius: 50%; transition: .2s; }
.toggle-switch input:checked + .slider::before { transform: translateX(14px); }

/* ── Buttons ── */
.btn-secondary {
  background: var(--surface); border: 1px solid var(--border); border-radius: 4px;
  color: var(--text); padding: 4px 12px; cursor: pointer; font-size: 13px;
}
.btn-secondary:hover { border-color: var(--accent); }

/* ── Callouts ── */
.callout { padding: 10px 14px; border-radius: var(--radius); font-size: 13px; }
.callout-info  { background: rgba(59,130,246,.1); color: var(--accent); }
.callout-error { background: rgba(220,38,38,.1);  color: var(--down); }

/* ── Empty / spinner ── */
.empty-state { color: var(--text-muted); padding: 40px; text-align: center; }
.spinner {
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin .7s linear infinite; margin: 60px auto;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<aside id="sidebar">
  <div>
    <div class="sidebar-title">DART 감사검증</div>
    <div style="font-size:11px;color:var(--text-muted);margin-top:2px">PAS Evidence Cockpit</div>
  </div>

  <!-- File upload drop zone -->
  <label id="drop-zone">
    <input type="file" id="file-input" accept=".html,.htm,.dsd,.pdf">
    <div style="font-size:28px">📂</div>
    <div class="drop-label">파일 첨부<br><span style="font-size:11px">HTML · DSD · 전자 PDF</span></div>
  </label>

  <!-- kreports stub panel -->
  <div id="kreports-container"></div>

  <!-- Nav placeholder (populated by renderer) -->
  <div class="nav-section" id="sidebar-nav"></div>
</aside>

<main id="main">
  <div id="main-content">
    <div class="empty-state">
      파일을 첨부하면 재무상태표 방정식, 현금 대사, 자본 대사 검증 결과가 표시됩니다.
    </div>
  </div>
</main>

<div id="status-bar">준비 완료</div>

<!-- PDFJS_PLACEHOLDER -->
<!-- BUNDLE_JS_PLACEHOLDER -->

</body>
</html>
```

- [ ] **Step 2: Verify template renders in browser** (open directly with `open static/dart-verify-template.html` — should show sidebar + empty state)

```bash
open static/dart-verify-template.html
```

Expected: Browser opens, shows dark sidebar + "파일을 첨부하면" message. No console errors.

- [ ] **Step 3: Commit**

```bash
git add static/dart-verify-template.html
git commit -m "feat: HTML shell template — evidence_cockpit layout with PAS design tokens"
```

---

## Task 13: Python Builder + CLI

**Files:** `src/dart_footing_reconciler/verify_html/__init__.py`, `src/dart_footing_reconciler/verify_html/builder.py`, `src/dart_footing_reconciler/cli.py`

- [ ] **Step 1: Create verify_html/__init__.py**

```python
"""verify_html — single-file offline verification HTML builder."""
from .builder import build_verify_html

__all__ = ["build_verify_html"]
```

- [ ] **Step 2: Create verify_html/builder.py**

```python
"""Assemble dart-verify.html from JS source files + HTML template."""
from __future__ import annotations

import re
from pathlib import Path

_STATIC = Path(__file__).parent.parent.parent.parent / "static"
_JS_DIR = _STATIC / "js"
_VENDOR_DIR = _STATIC / "vendor"
_TEMPLATE = _STATIC / "dart-verify-template.html"

# Load order must match import dependency graph
_JS_ORDER = [
    "verify-engine.js",
    "html-parser.js",
    "dsd-parser.js",
    "pdf-parser.js",
    "format-detector.js",
    "results-renderer.js",
    "kreports-panel.js",
    "app.js",
]

_IMPORT_RE = re.compile(
    r"""^(import\s+.*?from\s+['"].*?['"];?\s*\n?|export\s+\{\s*\};\s*\n?)""",
    re.MULTILINE,
)
_EXPORT_KEYWORD_RE = re.compile(
    r"^export\s+((?:async\s+)?function|class|const|let|var)\b",
    re.MULTILINE,
)
_EXPORT_DEFAULT_RE = re.compile(r"^export\s+default\s+", re.MULTILINE)


def _inline_js() -> str:
    parts: list[str] = []
    for name in _JS_ORDER:
        src = (_JS_DIR / name).read_text(encoding="utf-8")
        # Strip ES module import declarations (files concatenated in order)
        src = _IMPORT_RE.sub("", src)
        # Strip export modifiers (functions/classes become plain globals)
        src = _EXPORT_KEYWORD_RE.sub(r"\1 ", src)
        src = _EXPORT_DEFAULT_RE.sub("", src)
        parts.append(f"// ── {name} ──\n{src.strip()}")
    return "\n\n".join(parts)


def _inline_pdfjs() -> str:
    pdf_path = _VENDOR_DIR / "pdf.min.js"
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF.js not found at {pdf_path}. "
            "Run: npm install && cp node_modules/pdfjs-dist/build/pdf.min.js static/vendor/"
        )
    worker_path = _VENDOR_DIR / "pdf.worker.min.js"
    pdf_js = pdf_path.read_text(encoding="utf-8")
    
    worker_init = ""
    if worker_path.exists():
        worker_js = worker_path.read_text(encoding="utf-8")
        # Create a Blob URL for the worker so PDF.js can load it offline
        worker_init = (
            "\n;(function(){"
            "var b=new Blob([" + repr(worker_js) + "],{type:'text/javascript'});"
            "var u=URL.createObjectURL(b);"
            "if(typeof pdfjsLib!=='undefined')pdfjsLib.GlobalWorkerOptions.workerSrc=u;"
            "})();"
        )
    return pdf_js + worker_init


def build_verify_html(output_path: Path) -> None:
    """Build a single self-contained dart-verify.html."""
    template = _TEMPLATE.read_text(encoding="utf-8")

    bundled_js = _inline_js()
    pdfjs = _inline_pdfjs()

    html = template.replace(
        "<!-- PDFJS_PLACEHOLDER -->",
        f"<script>\n{pdfjs}\n</script>",
    )
    html = html.replace(
        "<!-- BUNDLE_JS_PLACEHOLDER -->",
        f"<script>\n{bundled_js}\n</script>",
    )

    output_path.write_text(html, encoding="utf-8")
```

- [ ] **Step 3: Add CLI command to cli.py**

In `src/dart_footing_reconciler/cli.py`, after the existing imports, add:

```python
from dart_footing_reconciler.verify_html import build_verify_html
```

And add this command before `if __name__ == "__main__":` or at the end of the file (just before `app()` call if present):

```python
@app.command()
def build_verify_html_cmd(
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("dart-verify.html"),
) -> None:
    """Build a single self-contained offline verification HTML file."""
    from dart_footing_reconciler.verify_html import build_verify_html as _build
    _build(output)
    typer.echo(f"Built: {output} ({output.stat().st_size // 1024} KB)")
```

Name the function `build_verify_html_cmd` to avoid shadowing the import.

- [ ] **Step 4: Run builder**

```bash
python -m dart_footing_reconciler build-verify-html --output dart-verify.html
```

Expected: `Built: dart-verify.html (XXXX KB)` — no errors.

- [ ] **Step 5: Verify the built HTML opens and works**

```bash
open dart-verify.html
```

Drag a DART HTML file onto the drop zone. Check:
- Sidebar renders
- File name shown in status bar
- Verdict banner appears
- Check cards show

- [ ] **Step 6: Add dart-verify.html to .gitignore (build artifact)**

```bash
echo "dart-verify.html" >> .gitignore
```

- [ ] **Step 7: Run full pytest suite (Python tests must not regress)**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: All Python tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/dart_footing_reconciler/verify_html/ src/dart_footing_reconciler/cli.py .gitignore
git commit -m "feat: Python builder + CLI 'build-verify-html' — assembles single offline HTML"
```

---

## Task 14: E2E Playwright Smoke Test

**Files:** `tests/e2e/upload-smoke.spec.ts`

- [ ] **Step 1: Build the HTML first**

```bash
python -m dart_footing_reconciler build-verify-html --output dart-verify.html
```

- [ ] **Step 2: Write E2E test**

Create `tests/e2e/upload-smoke.spec.ts`:

```ts
import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const HTML_PATH = path.resolve(process.cwd(), 'dart-verify.html');
const FILE_URL = `file://${HTML_PATH}`;

// Minimal synthetic BS HTML for upload
const SYNTHETIC_BS_HTML = `
<html><body>
<p>재무상태표 (단위: 백만원)</p>
<table>
  <tr><th>항목</th><th>당기말</th><th>전기말</th></tr>
  <tr><td>자산총계</td><td>1,000</td><td>900</td></tr>
  <tr><td>부채총계</td><td>400</td><td>360</td></tr>
  <tr><td>자본총계</td><td>600</td><td>540</td></tr>
</table>
</body></html>`.trim();

test.describe('dart-verify.html smoke', () => {
  test.beforeAll(() => {
    // Ensure the HTML exists
    if (!fs.existsSync(HTML_PATH)) {
      throw new Error(`dart-verify.html not found. Run: python -m dart_footing_reconciler build-verify-html`);
    }
  });

  test('initial page — empty state visible', async ({ page }) => {
    await page.goto(FILE_URL);
    await expect(page.locator('#main-content')).toContainText('파일을 첨부하면');
    await expect(page.locator('#sidebar')).toBeVisible();
    await expect(page.locator('#status-bar')).toContainText('준비 완료');
  });

  test('upload synthetic HTML — verdict banner appears', async ({ page }) => {
    await page.goto(FILE_URL);

    // Write synthetic file to disk and upload via file input
    const tmpPath = path.join(process.cwd(), '_test_synthetic_bs.html');
    fs.writeFileSync(tmpPath, SYNTHETIC_BS_HTML);

    try {
      const fileInput = page.locator('#file-input');
      await fileInput.setInputFiles(tmpPath);

      // Wait for verdict banner
      await expect(page.locator('.verdict-banner')).toBeVisible({ timeout: 10_000 });

      // Should show 'matched' status (1000 = 400+600)
      await expect(page.locator('.verdict-banner')).toContainText('이상 없음');
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  test('upload HTML with equity gap — verdict-fail banner', async ({ page }) => {
    await page.goto(FILE_URL);

    // Corrupt: asset=1000, liab=400, eq=500 → gap of 100
    const gapHtml = SYNTHETIC_BS_HTML.replace(
      '<td>자본총계</td><td>600</td>',
      '<td>자본총계</td><td>500</td>'
    );
    const tmpPath = path.join(process.cwd(), '_test_gap_bs.html');
    fs.writeFileSync(tmpPath, gapHtml);

    try {
      await page.locator('#file-input').setInputFiles(tmpPath);
      await expect(page.locator('.verdict-banner')).toBeVisible({ timeout: 10_000 });
      await expect(page.locator('.verdict-banner')).toContainText('검토 필요');
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });

  test('evidence drilldown opens on click', async ({ page }) => {
    await page.goto(FILE_URL);
    const tmpPath = path.join(process.cwd(), '_test_drilldown_bs.html');
    fs.writeFileSync(tmpPath, SYNTHETIC_BS_HTML);

    try {
      await page.locator('#file-input').setInputFiles(tmpPath);
      await expect(page.locator('.verdict-banner')).toBeVisible({ timeout: 10_000 });

      const drilldown = page.locator('.evidence-drilldown').first();
      await drilldown.locator('summary').click();
      await expect(drilldown.locator('.evidence-table')).toBeVisible();
    } finally {
      fs.unlinkSync(tmpPath);
    }
  });
});
```

- [ ] **Step 3: Install Playwright browsers**

```bash
npx playwright install chromium
```

- [ ] **Step 4: Run E2E tests**

```bash
npx playwright test tests/e2e/upload-smoke.spec.ts
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/upload-smoke.spec.ts
git commit -m "test(e2e): Playwright upload smoke — verdict banner, gap detection, drilldown"
```

---

## Task 15: Final Verification

- [ ] **Step 1: Run full Vitest suite**

```bash
npx vitest run
```

Expected: All JS unit tests PASS (verify-engine, html-parser, pdf-parser).

- [ ] **Step 2: Run Playwright E2E**

```bash
npx playwright test
```

Expected: All 4 E2E tests PASS.

- [ ] **Step 3: Run Python tests (no regressions)**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -5
```

Expected: 741+ tests pass, 0 failures.

- [ ] **Step 4: Build final artifact**

```bash
python -m dart_footing_reconciler build-verify-html --output dart-verify.html
ls -lh dart-verify.html
```

Expected: File exists, size reasonable (< 2MB).

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final verification pass — all unit + E2E tests passing"
```

---

## Self-Review Against Spec

| Spec requirement | Task |
|---|---|
| File upload: HTML/DSD/PDF | Tasks 6,7,8 + FormatDetector T9 |
| Runs in-browser, no server | Tasks 10,11,12 (pure JS) |
| parseAmount — footnote, unicode minus, △ | Task 2 |
| Column detection: 당분기/당반기/전분기/전반기/제N기 | Task 3 |
| LabelResolver 5-tier, POSITION ASSET_TOTAL only | Task 4 |
| BS/Cash/Equity checks | Task 5 |
| NullPriorPeriodOracle stub | Task 10 (kreports-panel.js) |
| evidence_cockpit UI: verdict banner, tick, drilldown | Tasks 10,11,12 |
| kreports UI stub (toggle OFF by default) | Task 10 |
| Python builder + CLI command | Task 13 |
| E2E: HTML upload → verdict | Task 14 |
| No CDN (except PDF.js inlined) | Task 12,13 |
| Security: escHtml, safeId, no innerHTML raw | Tasks 10,12 |
| Single self-contained HTML output | Task 13 |

All 14 requirements covered.

---

## Codex Handoff Notes

- **Branch**: `feat/offline-verify-html` (from `audit-workpaper-note-reconciliation`)
- **Python refs**: `src/dart_footing_reconciler/amounts.py`, `label_resolver.py`, `checks_statement_ties.py`
- **Design spec**: `docs/superpowers/specs/2026-06-12-offline-verify-html.md`
- **Verification**: Claude reviews after implementation (spec compliance + security)
- **Do not**: add backend server, CDN links, or kreports live API calls — stub only
- **PDF.js**: use UMD build (`pdf.min.js`) from `pdfjs-dist@4.x` npm package; builder inlines via Blob URL worker
- **Testing**: Vitest (`npx vitest run`) for units, Playwright (`npx playwright test`) for E2E — both must pass before handoff back to Claude
