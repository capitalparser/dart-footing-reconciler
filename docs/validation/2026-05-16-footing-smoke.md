# 2026-05-16 Footing Smoke Validation

## Scope

Validated the first footing engine against public DART viewer HTML samples.

## Commands

```bash
uv run python -m pytest
uv run dart-footing foot /tmp/dart_viewer.html --format json
uv run dart-footing foot /tmp/kctech_fin.html --format json
uv run dart-footing foot /tmp/samsung_heavy_fin.html --format json
```

After this smoke run, validation-manifest support was added:

```bash
uv run dart-footing validate validation_manifest.json --mode conservative
uv run dart-footing validate validation_manifest.json --mode diagnostic
uv run dart-footing validate validation_manifest.json --tag manufacturing
```

## Results

| Sample | Result | Observation |
|---|---:|---|
| DGP audit report viewer HTML | 3 / 3 matched | Basic PPE and intangible movement tables parsed and footed |
| KC Tech business report viewer HTML | 7 / 7 matched | Beginning/ending gross cost, accumulated depreciation, and impairment detail rows had to be excluded from movements |
| Samsung Heavy Industries business report viewer HTML | 14 / 14 matched | XBRL-style note tables needed target detection from heading/header rows, not only movement text |

## Rules Added From Real Samples

- Default tolerance is `1` to absorb displayed-unit rounding in DART tables.
- Capital/equity movement tables are excluded from default MVP scan.
- Cash flow statement bodies are excluded even when they contain target line items such as PPE acquisition.
- If a DART heading contains multiple section titles, only the last section title is treated as the current table context.
- Beginning/ending detail rows such as gross cost, accumulated depreciation, and impairment are ignored unless they are the selected beginning or ending carrying amount rows.

## Current Gap

This is still footing only. Cash flow statement reconciliation is not implemented yet.

## Direction Confirmed

- Keep `conservative` as the default audit-facing mode.
- Keep `diagnostic` as the broad parser-development mode.
- Expand the corpus through manufacturing companies first.
- Use validation manifests so every new company/report becomes a regression sample rather than a one-off manual check.
