# News and operator evidence for PLiZ

Researched 19 September 2026. Published evidence below is separate from the synthetic PS1 demo.

## 1. Tight maintenance window — Singapore reporting

**CNA, 1 April 2025 (updated 4 February 2026): [The night shift that keeps Singapore's trains running](https://www.channelnewsasia.com/singapore/tough-work-smrt-workers-train-rail-maintenance-5022391).**

The report followed a rail replacement on 11 March 2025. Workers had a three-hour window, 1:30am–4:30am, to replace an 18-metre defective rail.

Supports: maintenance teams operate under tight time constraints. This specific example does not establish a universal window or measure scheduling labour.

## 2. Allocating maintenance access affects passengers — Singapore reporting

**CNA, 17 January 2026 (updated 23 January): [Taking the Circle Line? What to expect during the scheduled 3-month disruption](https://www.channelnewsasia.com/singapore/circle-line-ccl-disruption-3-month-shuttle-buses-train-faq-5863851).**

The article reported the service plan for tunnel strengthening. Intervals were to change from 2 to 3 minutes between HarbourFront and Paya Lebar at peak hours, 3 to 10 between Paya Lebar and Mountbatten (shuttle service), and 6 to 10 between Mountbatten and Dhoby Ghaut/Marina Bay.

Supports: the service trade-off when track access is allocated to engineering work. These are announced intervals, not measured passenger delays, unexpected closures, or evidence of planner inefficiency. The dates describe a historical plan; do not present it as current service information.

The chart `cna-circle-line-access-impact.png` and editable `cna-circle-line-access-impact.svg` reproduce those published figures. `news-chart-data.json` records their provenance. Regenerate using `python docs/evidence/build_news_chart.py` with matplotlib installed.

## 3. Competing urgent tasks — historical Singapore reporting

**CNA/TODAY, 7 November 2017: [North-South, East-West lines will likely see shortened operating hours on weekdays](https://www.channelnewsasia.com/singapore/north-south-east-west-lines-will-likely-see-shortened-operating-hours-weekdays-khaw-5745951).**

The minister described limited engineering hours as an obstacle to renewal and the need to prioritise urgent work. This is historical context, not a measurement of today's planning process.

## 4. Direct evidence of manual conflict checking — operator report

**[SMRT Group Review 2024/25](https://www.smrt.com.sg/getmedia/f5eeb838-eb2e-4289-9f76-94513d49fe56/SMRT-Group-Review-2024_25.pdf), printed pages 54 and 90.**

Page 90 describes difficulty handling urgent requests when track-access deconfliction and validation were manual. Page 54 reports approximately 14,000 ad-hoc Engineering Work Requests per year handled by its Track Access Management System (TAMS).

The report also states that TAMS already uses AI and is deployed on the North-South, East-West and Circle lines. This validates the operational use case but means we cannot claim SMRT currently has no automated solution. It does not demonstrate a feature gap in TAMS or establish PLiZ's superiority. These are operator-reported statements, not independent performance measurements. The search index exposed these sections; a full web PDF opening failed because of its size.

## 5. Independent review of access-plan changes — UK context

**[ORR announcement, 14 October 2021](https://www.orr.gov.uk/search-news/rail-regulator-calls-better-planning-engineering-works-reduce-impact-passengers)** and **[GHD Possessions Efficiency Review, April 2021](https://www.orr.gov.uk/sites/default/files/2021-10/ghd-possessions-efficiency-review-independent-report-april-2021.pdf), printed pages 1–2.**

The review identified substantial changes to access plans and recommended measuring time spent on manual data processing, repeated tasks and rework. It supports the need to investigate planning efficiency; it does not supply a measured Singapore baseline for time saved.

## How PLiZ addresses the planning problem

PLiZ helps planners work out what to change when maintenance loses its allocated track access. Its focus is the repeated scheduling and checking needed after a disruption.

For example, suppose jobs and crews are already scheduled, then a track section becomes unavailable for two weeks. The current prototype supports this workflow:

1. **Find affected jobs.** The planner enters the closure location, start week and duration. PLiZ identifies scheduled work affected by the closure or its exclusion buffers.
2. **Build a revised schedule.** The scheduling engine searches for alternative nights and suitably skilled, available crew while checking the implemented PS1 constraints, including dependencies, track capacity, possession conflicts and crew limits. Past weeks stay fixed; the heuristic tries to preserve existing future assignments.
3. **Show the consequences.** The preview identifies changed activities, before-and-after completion dates, delays and remaining unscheduled workload. Results come from a deterministic what-if calculation, not an equipment-failure prediction.
4. **Review and apply.** The planner reviews the proposed changes before applying them. Candidates with failed local checks cannot be applied. This is an in-app review step, not formal OCC approval or a track permit.
5. **Ask for an explanation.** The AI assistant answers questions about the plan, assignments and disruption previews. Scheduling calculations and constraint checks are performed by the Python planner; the language model supports interpretation and explanation.

The intended benefit is less repeated checking and easier review of a proposed change. We have not measured staff hours saved, passenger-delay reductions or performance against an operator's existing system.

### How the evidence connects to the app

- **CNA's maintenance-window reporting** establishes the time constraint in which planning takes place. PLiZ allocates access-nights; it does not yet schedule individual tasks minute by minute within a three-hour window.
- **CNA's Circle Line coverage and the chart** show the passenger-service trade-off of allocating more engineering access. They do not demonstrate that PLiZ would prevent those closures or their effects.
- **SMRT's report** directly documents the manual conflict-checking problem and an existing automated response, TAMS. It supports the relevance of the use case, not a claim that PLiZ is the first solution or fills a demonstrated gap in TAMS.
- **The PS1 brief**, [section 2.1 point 10 and section 3.3](https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement/blob/main/PS1/PS1_README.md#33-bonus-scope--beyond-the-schedule-innovation), establishes disruption impact assessment and replanning as part of the hackathon context.

PLiZ remains a hackathon prototype using the organiser's synthetic rail instance and fictional crew. Its local checks cover the implemented PS1 model; they are not certification for live railway operations or a pass from the organisers' reference validator.

## Suggested pitch wording

Rail maintenance teams must coordinate work within short engineering windows. Published reporting shows the passenger trade-offs of extending track access, while SMRT documents the challenges of manual conflict checking and its investment in automation. PLiZ demonstrates constraint-aware scheduling and explainable disruption previews for the NebulaX PS1 challenge.

**Short product explanation:** When track access changes, PLiZ turns the disruption into a revised schedule—with crew assignments, constraint checks and clear explanations—so planners can review the impact before approving changes in the app.

Do not claim that PLiZ prevents the reported incidents, eliminates necessary closures, replaces existing operator systems, or saves a measured percentage of staff time. Those outcomes have not been tested. A direct manual-versus-PLiZ task study would be needed to substantiate a time-saving claim.

No ZIP packaging or validator submissions were performed.
