# Election Workpaper Design

## Status

Draft for review.

## Product Positioning

Election Workpaper is a neutral, evidence-based election information
workbench for the 2026 Korean local elections. It is not a candidate scoring,
ranking, grading, or recommendation service.

The first customer is an investigation-oriented user: local media, civic
groups, policy researchers, and community editors who need to turn official
candidate and pledge materials into traceable comparison tables. A simplified
public voter view can be exposed from the same reviewed data, but the product's
source of truth is the workbench.

The product metaphor is:

```text
Election pledge GitHub + audit workpaper
```

Every claim should be decomposed into source-backed units, tagged, compared,
and reviewed without asking the system to decide which candidate is better.

## Context

The 9th nationwide local elections are scheduled for June 3, 2026. Local
elections create an information overload problem because a voter may need to
review metropolitan, basic local government, local council, education
superintendent, and by-election candidates at the same time.

Official sources exist, including NEC candidate data, policy and pledge pages,
party policy PDFs, and public data APIs. The gap is not raw availability. The
gap is structured comparison: grouping similar pledges, showing differences,
tracking sources, and surfacing factual review questions without creating a
candidate hierarchy.

Legal and trust constraints are product-shaping requirements. Candidate pledge
comparison should avoid scores, ranks, grades, "best candidate" language,
personalized candidate recommendations, and any UI that can reasonably be read
as ranking candidates.

## Goals

- Let a user select an area and see the relevant election contests and
  candidates.
- Preserve source links and source text for every material candidate fact and
  pledge claim.
- Split candidate pledges into claim-level records that can be tagged,
  compared, and reviewed.
- Group claims by neutral policy topics such as transportation, housing,
  welfare, education, industry, budget, climate, safety, and administration.
- Show non-ranking comparison labels such as similar pledge, distinct pledge,
  funding mentioned, funding not mentioned, execution authority unclear, and
  source needs review.
- Provide an audit-style feasibility workpaper for funding source, responsible
  authority, timeline, ordinance/statute dependency, and external statistics.
- Keep AI in a helper role: extraction, clustering, summarization, and review
  prompts. AI must not score, rank, grade, endorse, or recommend candidates.

## Non-Goals

- Candidate scores, ranks, grades, tiers, or "best candidate" labels.
- "Candidate closest to me" recommendations.
- Election outcome prediction or candidate viability analysis.
- Automated claims that a pledge is true, false, good, bad, feasible, or
  infeasible.
- Fully automated coverage of all local council candidates in the first MVP.
- Legal advice or election-law compliance certification.

## Users

### Primary: Investigation Desk

Local journalists, civic organization researchers, and policy analysts use the
workbench to prepare articles, voter guides, issue briefs, and comparison
tables. They need provenance, review status, and exportable structured data.

### Secondary: Public Voter View

Voters use a simplified public interface to find their local contests, compare
pledges by topic, and open the original source. The public view should inherit
only reviewed records and should avoid evaluative language.

### Tertiary: Internal Policy Reviewer

A specialist reviewer uses the feasibility workpaper to inspect funding,
authority, timeline, and legal-dependency signals. This is where the founder's
accounting and audit background creates product differentiation.

## Core Data Model

### ElectionArea

Represents an administrative area and the election contests that apply to it.
It stores normalized region codes, display names, source of mapping, and mapping
confidence.

### ElectionContest

Represents one contest such as mayor, governor, district head, education
superintendent, metropolitan council, basic council, or by-election. It stores
NEC election identifiers where available and exposes the contest type without
collapsing separate elections into one comparison.

### Candidate

Represents a candidate in a contest. It stores official profile attributes such
as name, party, career, education, property, military service, tax, criminal
record, and source references. Sensitive fields must be displayed only when
they are officially published and should retain direct source attribution.

### SourceEvidence

Represents a source artifact or source fragment. It stores source type, URL or
file identifier, publication date, retrieval date, page or section, raw text,
and extraction confidence.

### PromiseClaim

Represents one pledge or claim extracted from official materials. It stores the
raw text, normalized summary, candidate, contest, policy tags, source evidence,
and review status.

### PolicyTag

Represents a neutral topic label. Tags should be descriptive, not evaluative.
The MVP should start with 10 to 15 tags and allow manual correction.

### ComparisonCluster

Groups claims that discuss the same issue or policy instrument. It can contain
claims from several candidates and should explain why the claims were grouped.
It must not produce a winner or ordered list.

### FeasibilitySignal

Represents a neutral review signal such as funding mentioned, responsible
authority stated, timeline stated, ordinance/statute dependency, central
government dependency, or external-statistic conflict candidate. Signals are
questions for review, not verdicts.

## Data Sources

MVP sources:

- NEC election schedule and candidate pages.
- NEC policy and pledge portal.
- Public Data Portal NEC election pledge API.
- Public Data Portal NEC party policy API.
- Official party policy PDFs.
- Official candidate pledge PDFs or pages where available.

Supplemental sources after MVP:

- Candidate homepages and campaign pages.
- Election pamphlet PDFs.
- Debate transcripts.
- Local government budget documents.
- Local ordinances and statutes.
- Statistics Korea, local open-data portals, and ministry statistics.

Source priority should be official election sources first, candidate-submitted
materials second, government/public statistics third, and media or campaign
statements fourth.

## Data Flow

```text
official source discovery
  -> source ingestion
  -> candidate and contest normalization
  -> source evidence indexing
  -> pledge claim extraction
  -> policy tagging
  -> comparison clustering
  -> feasibility signal extraction
  -> human review
  -> public comparison table or data export
```

The system should store raw source text and the extracted record side by side.
Reviewers must be able to trace from a comparison cell back to the original
source fragment.

## MVP Scope

The two-week MVP should support one or two pilot regions rather than the entire
country.

Default MVP decisions:

- Start with a local web app for the investigation workbench.
- Use city/county/district selection first; defer exact address-to-district
  mapping until the data model and source coverage are validated.
- Ship the workbench first. The public voter view should be generated only from
  reviewed records after the workbench can produce reliable comparison tables.
- Use one pilot region selected by the product owner before implementation.

Required capabilities:

- Select a region by city, county, or district.
- Display applicable contests and candidate cards.
- Ingest official candidate profile data with source references.
- Ingest official pledge data for contests covered by the NEC pledge API.
- Add PDF/manual ingestion for uncovered pledge materials where needed.
- Extract pledge claims and assign 10 to 15 policy tags.
- Display topic-by-topic candidate comparison tables.
- Show non-ranking labels for similar pledge, distinct pledge, funding
  mentioned, funding not mentioned, authority unclear, and source needs review.
- Provide a reviewer queue for accepting, editing, or rejecting extracted
  claims, tags, clusters, and feasibility signals.
- Export reviewed data as CSV or JSON for media and civic-group users.

Deferred capabilities:

- Nationwide automated ingestion.
- Full local council coverage.
- Debate and speech fact-check workflows.
- Public account system.
- Paid report API.
- Personalized candidate matching.

## User Experience

### Workbench View

The workbench opens with a region selector and a list of contests. Selecting a
contest shows candidates side by side. Each candidate has official profile
facts, pledge source coverage, review status, and missing-source warnings.

The main comparison view is organized by policy topic. Within a topic, the user
sees comparison clusters. Each cluster shows the original claim text, a short
neutral summary, source evidence, and review labels.

### Feasibility Workpaper

The feasibility workpaper is claim-centered. For each claim, the reviewer sees:

- funding source mentioned or not mentioned
- responsible authority stated or unclear
- timeline stated or unclear
- ordinance or statute dependency candidate
- central government or National Assembly dependency candidate
- related budget or statistics source needed
- reviewer notes

The workpaper should use hypothesis and question language. It should say
"central government cooperation may be required" or "funding source is not
identified in the submitted pledge," not "this pledge is impossible."

### Public View

The public view is a read-only subset of reviewed records. It supports region
selection, contest selection, candidate cards, topic filters, and source links.
It should not expose experimental or unreviewed AI labels unless clearly marked
as pending review.

## Legal and Trust Guardrails

The system must not provide:

- numeric scores
- letter grades
- ranking tables
- best/worst labels
- candidate recommendations
- ideological matching
- turnout, viability, or winning-probability labels

The system may provide:

- source-backed factual profile fields
- raw pledge text
- neutral summaries
- policy topic grouping
- source coverage status
- similarity grouping
- non-ranking feasibility signals
- reviewer notes and open questions

All generated summaries and labels should carry a review status:

- extracted
- needs review
- reviewed
- corrected
- rejected

Public pages should prefer reviewed or corrected records.

## Architecture

The product should be built as a separate application or package, not inside
the DART footing reconciler core. The current DART project can inspire the
audit-workpaper approach, source traceability, confidence fields, and neutral
classification patterns, but election data should have its own domain model.

Suggested service boundaries:

- ingestion: fetches API, HTML, and PDF sources
- normalization: maps areas, contests, candidates, and source identifiers
- extraction: turns raw materials into claim records with evidence spans
- classification: applies policy tags and feasibility signals
- comparison: groups similar or distinct claims without ranking candidates
- review: stores human decisions and correction history
- presentation: serves workbench, public view, and exports

The core data processing should run without MCP or agent infrastructure. Agent
tools can be added later as thin wrappers for source ingestion, claim review,
and report generation.

## Error Handling

Missing source coverage should be explicit. If the NEC pledge API does not cover
a contest type, the UI should show that the official API source is unavailable
for that contest and allow manual PDF/source ingestion.

Low-confidence extraction should not silently appear as fact. Claims, tags,
clusters, and feasibility signals below the confidence threshold should enter
the reviewer queue with the source evidence attached.

Conflicting sources should be shown as conflicts, not resolved automatically.
The reviewer can select a preferred source or mark the conflict unresolved.

## Testing and Validation

MVP validation should include:

- fixture tests for NEC API response parsing
- fixture tests for policy PDF extraction
- source-location tests for claim extraction
- tag classification regression tests with Korean pledge examples
- comparison clustering tests that confirm no ranking output is produced
- guardrail tests that block score, grade, rank, and recommendation fields from
  public output
- reviewer workflow tests for accept, edit, reject, and export

Acceptance criteria:

- A pilot region can be loaded end to end from source ingestion to comparison
  table.
- Every public claim has at least one source evidence record.
- Public output contains no score, rank, grade, or recommendation fields.
- At least one contest can be exported as reviewed CSV or JSON.

## Remaining Product Input

Before implementation planning, choose the first pilot region. A good pilot has
at least one high-interest executive contest, available official pledge
materials, and enough local issues to test topic clustering and feasibility
signals.

## References

- NEC election schedule page for the 9th nationwide local elections:
  https://nec.go.kr/site/nec/ex/bbs/View.do?bcIdx=289351&cbIdx=1104
- Public Data Portal NEC election pledge API:
  https://www.data.go.kr/data/15040587/openapi.do
- Public Data Portal NEC party policy API:
  https://www.data.go.kr/data/15040588/openapi.do
- NEC policy and pledge portal:
  https://policy.nec.go.kr/plc/policy/initUPAPolicy.do?menuId=PARTY5
