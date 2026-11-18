# Project Plan and Management

**Project:** ReadySteady — Campus Canteen Pre-Ordering System
**Group:** Ready Teady Go & Company · **Course:** Software Engineering
**Version:** 1.0 · **Date:** 18 November 2026

> **Fill before submission:** replace the member placeholders below with real names and roll
> numbers. Per the course brief, only **one** member submits the group form, **once**, and all
> member details must be correct.

## 1. Team and responsibility matrix

| Member | Roll no. | Primary ownership | Secondary / review |
|---|---|---|---|
| Member A — *name pending* | *pending* | Requirements (SRS), use cases, stakeholder analysis | Test plan review |
| Member B — *name pending* | *pending* | Backend: services, repository, schema, concurrency | Architecture doc |
| Member C — *name pending* | *pending* | Frontend UI/UX, UML diagrams, integration & system tests | Maintenance doc |
| Member D — *name pending (if 4)* | *pending* | Testing lead: unit tests, QA checklist, this plan | SRS traceability |

Every member contributes meaningfully: ownership above is *primary*, not exclusive — all members
review each other's pull requests and each owns at least one SDLC deliverable end-to-end.
Existing code history (initial prototype by the founding member) is credited in the git log and
in §3 milestone M3.

## 2. Method

Incremental SDLC in six milestones, each ending in a verifiable deliverable (not "code written").
Requirements → modelling → design → implementation → testing → documentation/maintenance planning
are treated as equal-weight activities, per the course brief. Work is tracked as issues/branches;
`main` always passes `python -m pytest`.

## 3. Milestones and schedule

| # | Milestone | Window (2026) | Activities & deliverables | Exit criteria |
|---|---|---|---|---|
| M1 | Requirements | 10–13 Nov | Stakeholders, use cases, FR/NFR list; SRS v1 | SRS reviewed by all members; every FR has acceptance criteria |
| M2 | Modelling & design | 13–16 Nov | Use-case, class, sequence, activity, state diagrams; layer design; decision log | 5 UML diagrams match code; ARCHITECTURE.md justifies each major decision |
| M3 | Implementation | 16–24 Nov | Flask API, services, repository, schema, seed; three-role SPA | `python run.py` boots with demo data; all FR demonstrable |
| M4 | Testing & QA | 24–30 Nov | 60 unit + 11 integration + 4 system tests incl. concurrency races; QA checklist (security, usability, performance) | 75/75 green on a clean checkout; race tests prove NFR-02 |
| M5 | UI revision + SE documentation | 18–25 Nov | Rebrand to ReadySteady + logo; glass drawer; light/dark theme; menu photos; toasts; confirmation animation; SRS/ARCHITECTURE/PLAN/MAINTENANCE docs | UI verified in browser in both themes; docs complete and cross-linked; tests still green |
| M6 | Freeze, review, submit | 26 Nov–5 Dec | Full regression, doc proof-read, member-details check, demo rehearsal, single form submission | Tagged release; one submission; demo script rehearsed by all members |

Buffer: 6–10 Dec reserved for corrective maintenance after evaluator feedback (see MAINTENANCE.md).

## 4. Weekly rhythm and communication

- Two 30-minute syncs per week (progress, blockers, next commitments); notes kept in the repo.
- Async discussion on the group channel; decisions that change scope or contracts are written
  into the relevant doc in the same pull request.
- Branch per feature/fix; PR requires one review from a non-author; CI-equivalent gate = full
  pytest run pasted in the PR description.

## 5. Risk register

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| Knowledge silo (one member wrote the prototype) | High | High | Pair walkthroughs; docs + 75 tests as shared understanding; rotate PR review | All |
| Concurrency bugs (oversell/overbook) | Medium | High | `BEGIN IMMEDIATE` + threaded race tests ST-03/04 in every run | Member B |
| Scope creep (payments, delivery, notifications) | Medium | Medium | SRS §1.2 out-of-scope list; changes need a doc update + group vote | Member A |
| Exam-week crunch | High | Medium | M6 buffer week; freeze date 25 Nov; no new features after freeze | All |
| UI regressions breaking API contracts | Medium | High | Frontend-only changes; contract table in SRS §6.1; integration tests as gate | Member C |
| Wrong/missing group details on form | Low | High | Checklist in M6; single submitter verifies all roll numbers | Submitter |

## 6. Definition of done (per deliverable)

- **Code:** merged via reviewed PR; full suite green; no contract change without SRS update.
- **Requirement:** id, acceptance criteria, and traceability to code + at least one test.
- **Diagram:** Mermaid source committed next to rendered PNG; matches current code.
- **Document:** reviewed by one non-author; cross-links resolve; version/date header present.
- **UI change:** exercised in a real browser in light and dark mode, mobile and desktop widths.

## 7. Effort estimate (person-days, remaining work at 18 Nov)

| Work item | Estimate |
|---|---|
| M5 UI revision (drawer, theme, photos, toasts, animation, rebrand) | 3 |
| M5 SE documents (SRS, architecture, plan, maintenance) | 2 |
| M6 regression, proof-read, demo rehearsal, submission | 2 |
| Buffer / corrective maintenance | 2 |
| **Total remaining** | **9 person-days** across the group |