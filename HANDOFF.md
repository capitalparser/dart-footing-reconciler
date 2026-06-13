# HANDOFF.md — dart-verify.html (Offline Verification HTML)

**Target branch:** `feat/offline-verify-html`  
**Base branch:** `audit-workpaper-note-reconciliation`  
**Primary executor:** Codex  
**Verifier:** Claude (spec compliance + security review after all tasks complete)

---

## Objective

Build `dart-verify.html` — a single self-contained HTML file that:
- Accepts DART HTML / DSD / electronic PDF file uploads (drag-and-drop)
- Runs BS equation / cash tie / equity tie checks in-browser (JS port of Python core)
- Renders PAS evidence_cockpit UI (dark sidebar, verdict banner, tick overlays, drilldowns)
- Has kreports stub panel (UI present, API calls no-op)

No server. No external CDN. Single artifact file.

---

## Documents to Read (in order)

1. **`docs/superpowers/specs/2026-06-12-offline-verify-html.md`** — full design spec (architecture, data structures, format handling, checks, UI)
2. **`docs/superpowers/plans/2026-06-12-offline-verify-html.md`** — step-by-step implementation plan with complete code for every step

---

## Python Reference Files

| File | Port target |
|------|-------------|
| `src/dart_footing_reconciler/amounts.py` | `parseAmount()` in verify-engine.js |
| `src/dart_footing_reconciler/label_resolver.py` | `LabelResolver.findRow()` in verify-engine.js |
| `src/dart_footing_reconciler/checks_statement_ties.py` | `bsEquationCheck/cashTieCheck/equityTieCheck` in verify-engine.js |
| `src/dart_footing_reconciler/html_tables.py` | `parseHtml()` in html-parser.js |

---

## Execution

### Step 0: Resume state check (mandatory first step)

```bash
cd ~/vault/01_Projects/09_dart_footing_reconciler
git checkout feat/offline-verify-html
git status        # check untracked/modified files
git log --oneline -5  # check what's already committed
```

If **untracked files already exist** from a previous partial run, commit them immediately before starting:

```bash
git add <existing files>
git commit -m "feat(task-N): <description> [resume commit]"
git log --oneline -1   # verify commit landed
```

### Step 1–15: Task-by-task TDD

1. Follow the plan task-by-task (Tasks 1–15). Skip tasks whose output files are **already committed** (`git log` shows them).
2. TDD: write failing test → implement → pass → verify tests pass
3. **Git commits are handled by Claude (the session owner), NOT by Codex.** Do NOT attempt git commit or git add commands — the `.git` directory is owned by the Claude process. Just create/edit files and run tests.
4. After Task 15 all tests pass, report the full test results and list of new files created. Claude will then commit.

### Division of responsibility

| Role | Responsibility |
|------|---------------|
| **Codex** | Create files, run `npx vitest run`, run `npx playwright test`, report results |
| **Claude** | `git add` + `git commit` after each confirmed test-pass batch |

After each task, report: task number, files created, test result (pass count / fail count).

---

## Done Criteria

- `npx vitest run` — all JS unit tests pass
- `npx playwright test` — all 4 E2E smoke tests pass
- `python -m pytest tests/ -x -q` — all Python tests pass (no regressions)
- `python -m dart_footing_reconciler build-verify-html --output dart-verify.html` — builds successfully
- Drag a DART HTML file onto dart-verify.html → verdict banner renders
