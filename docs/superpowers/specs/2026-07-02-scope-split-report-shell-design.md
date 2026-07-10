# Scope Split Report Shell Design

## Goal

The generated workpaper HTML must present consolidated and separate reports as distinct reviewer surfaces. A user selecting `연결보고서` should see only consolidated statements, consolidated notes, and consolidated-scoped review summaries. Selecting `별도보고서` should show only separate statements, separate notes, and separate-scoped review summaries.

## Scope

- Keep one generated HTML file.
- Add a top-left report scope switch: `연결보고서`, `별도보고서`.
- Render independent sidebar sections and main panels per scope.
- Preserve the existing note/source HTML fidelity, total highlights, review rail, and source jumps.
- Do not change parser section scope semantics or deterministic validation status rules.

## Data Flow

`FullReport` already carries `ReportSection.scope` values:

- `consolidated`
- `separate`
- empty scope for shared/non-scoped sections

The renderer will derive scoped report views from the existing `FullReport` and `CheckResult` list:

- statement panels: include sections whose `scope` matches the selected report scope
- note panels: include notes whose `scope` matches the selected report scope
- overview panels: compute status counts from results tied to the selected scope
- navigation: sidebar items belong to exactly one scope shell

## UI Behavior

- Default view is `연결보고서` when consolidated sections exist.
- The scope switch is visible near the sidebar brand.
- Changing scope hides the inactive report shell and activates the first meaningful panel in the selected scope.
- Source jumps open the target scope shell first, then scroll to the panel/cell.
- Global artifacts such as the review rail remain shared.

## Validation

Automated checks must cover:

- both report scope shells are rendered when consolidated and separate sections exist
- selecting separate hides consolidated statement/note labels and shows separate labels
- duplicate panel ids do not appear across both shells
- rendered SK Eternix output has separate/consolidated scope counts and no note-body regressions

Browser verification must check:

- default consolidated view shows consolidated statements/notes
- clicking `별도보고서` shows separate statements/notes only
- a source jump from separate view lands inside the separate shell
