# 0003. Signature-driven verification, not category dispatch

Status: accepted (2026-06-06)

## Decision

The engine verifies note tables by extracting *data signatures* from each table and dispatching verification attempts on signature match, **not** by first classifying a table into a fixed category (cycle, K-IFRS section, industry, disclosure-type) and routing verification by that category. Categories (cycle, outcome family, disclosure intent) remain as **enumeration grids and outcome labels** — never as verification entry gates.

## Context

The repo was drifting toward an architecture where every note table had to be classified into a `LayoutClassification` before any verification was attempted. The doctrine forbids company-name branching, but the same hardcode-game was re-emerging as *layout-name branching*: 46 flat `_is_X` classifiers in `layout_variants.py`, each tightly bound to one company's table shape. 35,846 of 40,842 inventoried note tables in the 100-company corpus fell into `unknown_layout` and were silently excluded from verification despite many of them carrying perfectly verifiable signatures (e.g. `기초/취득/처분/기말` roll-forward rows).

During domain interviews on 2026-06-06 the user surfaced the underlying objection: forcing categories at the entry of the verification pipeline blocks verification whenever classification fails, and category boundaries are themselves company-variant.

## Considered Options

1. **Category-first dispatch (rejected).** Classify → route → verify. Strong matrix story, weak coverage. Fails on boundary-ambiguous tables. Recreates company-name branching at the category layer.
2. **Signature-driven attempts (accepted).** Extract signatures → attempt all signature-matched verifications in parallel → label the outcome. Boundary-ambiguous tables still get verified if any signature matches. Categories survive only as outcome labels and enumeration grids.

## Consequences

- `LayoutClassification` is demoted from a verification gate to one signature among many. Existing 46 classifiers are not deleted in the migration; they are wrapped as signature emitters and gradually folded into a smaller signature library.
- New verification capabilities are added by registering signatures and attempt strategies, not by adding new layout keys.
- The 35,846 `unknown_layout` tables are re-evaluated under signature extraction in the first plan slice. Any table with at least one matched signature becomes a verification candidate; those with zero matched signatures are labeled `no_signature_matched_*` (qualitative / industry_terms / unknown) and remain backlog.
- `Audit Cycle` (CONTEXT.md) keeps its definition but its role changes from "verification routing key" to "core-account enumeration grid + signature vocabulary for row-label matching."
- Outcome labels (`matched_*`, `unresolved_with_signature`, `parse_uncertain`, `no_signature_matched_*`) replace the proposed 5-category cycle-miss taxonomy. The 5-category sketch (disclosure-only, cross-cycle bridge, industry-specific, internal-only, informational) survives only as a **statistics view** over outcome labels, not as a dispatch tree.
- The "no false matched" doctrine is unchanged: a signature match only triggers an attempt; closure still requires exact or display-unit-bounded arithmetic with source location.

## Follow-up notes (2026-06-06)

- **Module placement:** signatures live in a new `signatures.py`; essential-note grid lives in a new `essential_notes.py`. `taxonomy.py` is *not* extended with cycle/essential-note semantics; `verification_candidates.py` is *not* extended with signature emission. These are easy-to-reverse decisions and do not warrant a separate ADR.
- **Confidence policy:** signature confidence is observation-side; attempt acceptance thresholds (`matched_minimum`, `attempt_minimum`) are attempt-side and override-able per attempt. Defaults 0.70 / 0.40. See CONTEXT.md `Signature Confidence`.
