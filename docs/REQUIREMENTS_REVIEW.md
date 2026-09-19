# PLiZ requirement and gap review

Reviewed on 19 September 2026 against the [shared product review](https://chatgpt.com/share/6aad9acf-0094-83ec-ac6d-bdc75f29726e), [PS1 specification](https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement/blob/main/PS1/PS1_README.md), source code and organiser CSVs.

The shared conversation is a list of suggestions, not evidence that a feature is absent or a set of additional official requirements. Example passenger counts, delay minutes, allocation counts and claimed percentage improvements in it are not measurements of PLiZ.

## Core requirements

| Requirement | Implementation and verification | Limit |
|---|---|---|
| Full workload, start weeks and predecessor order | Python scheduler plus local audit; regressions check complete A/B/C plans and detect invalid precedence. | Hidden instances may remain incomplete; those plans cannot be applied or exported. |
| Exclusion buffers, Live opposite-bound mirroring and Live-only interchange crossover | CSV-derived footprints and same-night conflict checks; tests cover mirroring and cross-line isolation. | Conservative Live exclusivity; no operational safety certification. |
| PM/PC/C legal mixes and co-sharing | One PM alone, one PC plus up to three C, or up to four C; matching possessions share location capacity. | Greedy packing is not proven optimal. |
| Weekly access budgets and workfront caps | Planner and audit; CSV conversion preserves contract/type/week night indices. | Physical night mapping is an internal seven-night weekly model. |
| A/B/C and ECLO scoring | Scenario rules, 1.5-unit ECLO yield, weighted delays, extra-night and ECLO penalties; score components reconcile with the planner. | Scores from different scenarios use different objectives. |
| Three submission CSVs | Exact headers and in-memory round-trip checks in **Insights & checks → Checks**. | No ZIP produced by this review; no official judge submission. The official validator is not published in the organiser repository. |

## Changes delivered by this review

| Gap | Where to use it | What the result means |
|---|---|---|
| Compare plans without switching back and forth | **Insights & checks → Compare plans** | All A/B/C metrics, full-workload status, score components, co-sharing and ECLO counts. Different applied disruptions are flagged. |
| Explain delays and blocked scheduling attempts | **Explain the plan** | Specific constraint, week, other activity and locations where available. Intrinsically impossible workload windows are explained separately. Earlier alternatives are drawn from actual locally checked scenarios under the same disruption conditions. |
| Broader what-if planning | **Test a change → Reduced capacity / No ECLO** | Preview reduced weekly access quotas or a no-ECLO period. Quota reductions are hard limits even in B/C. Earlier weeks remain fixed; applying a valid preview is explicit. |
| Show the impact of replanning | Preview's before/after table | Work left, late contracts, ECLO, extra nights, penalty and assignment changes. Change counts include additions, removals and ECLO changes. |
| Make commuter implications visible without inventing them | **Network & ECLO** | Weekly ECLO exposure and selectable station engineering footprints on synthetic Alpha/Beta. Includes buffer and mirrored isolation; these are not confirmed station closures. |
| Crew and contractor oversight | **Crew & contracts** | Planned weekly crew load against limits, contract workload allocation, finish dates and late status. Scheduled coverage is not recorded field completion. |
| Stakeholder communications | **Handover** | Operations, contractor and passenger draft text from the selected week/night. Copy for review; nothing is sent or published. Missing service times and alternatives are explicitly unconfirmed. |
| Explain the solver's choice | **Explain the plan** | Actual three candidate orderings, objective, remaining work, audit failures and changes. Does not claim thousands of searches or global optimality. |

Examples for the assistant:

> Simulate SEC:BET:H01_H02:EB capacity to 1 night in week 11 for 2 weeks.

> Simulate no ECLO in week 11 for 2 weeks.

These produce previews. “Apply this plan” saves a displayed valid preview. The planner performs the calculation; the language model interprets requests and explains supplied results.

## Deliberately not claimed

- Passenger volumes, crowding, passenger-minutes lost, journey-delay estimates or real alternative-route recommendations: no demand or service timetable inputs are supplied.
- Equipment breakdown probabilities: no asset-condition history or sensor data is supplied.
- Real depot movements, minute-by-minute traction isolation, OCC permits or on-site completion: outside this weekly possession prototype.
- Event-aware planning and live alerts: no event calendar, authoritative alerts feed or station mapping from real MRT to Alpha/Beta is configured.
- Measured manpower savings: a timed baseline study is needed. Counts of assignments and co-sharing are observable indicators, not proven labour reductions.
- Contractor authentication or notifications: this remains the user-requested public shared demo.

For real-world context, [LTA's 28 April 2026 TEL/DTL announcement](https://www.lta.gov.sg/content/ltagov/en/newsroom/2026/4/news-releases/train-service-adjustments-tel-and-dtl-to-facilitate-rail-expansion-works.html) describes service adjustments for rail expansion work and passenger alternatives. It supports the value of communicating planned impacts, but its service changes are not PLiZ's synthetic dataset or evidence that PLiZ caused a time saving.

## Verification

`python -m pytest tests -q -k "not export"` covers existing workflows plus the review regressions: hard temporary quotas, ECLO restrictions, frozen history, score reconciliation, honest ECLO indicators, readable draft handovers, CSV round-trips, and read-only insight endpoints. Production build and desktop/phone browser checks verify the UI. Final submission packaging remains on hold.
