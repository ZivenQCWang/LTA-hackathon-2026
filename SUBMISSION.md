# PLiZ — proposal pack

These answers describe the working prototype. Each answer is below the form's 150-word limit. Review the wording with your team before submitting.

## What does your solution do?

PLiZ helps railway planners turn competing maintenance requests into a coordinated track-access and crew schedule. It checks work dependencies, track capacity, possession compatibility, exclusion buffers, and crew skills and availability. Planners can compare three approaches: protect capacity, meet deadlines, or balance both. When a track closes or a crew member becomes unavailable, a what-if preview recalculates future work while keeping earlier weeks fixed, then shows changed assignments and completion dates before the planner applies it. An AI assistant answers schedule questions, runs disruption previews, and executes requests to add crew, update leave, create jobs and save a plan. The app also imports the eight PS1 input files and exports the three required schedule CSVs. It reduces repetitive scheduling and conflict-checking work while keeping the planner in control. The prototype uses organiser-provided synthetic data and fictional crew; its forecasts estimate scheduling impacts rather than equipment failures.

## What tech stack was used to build this solution?

The frontend uses React 19, TypeScript and Vite, with custom responsive CSS and Lucide icons. The backend uses Python and FastAPI, with Pydantic for request validation and SQLAlchemy for persistence in SQLite. A custom deterministic scheduling heuristic evaluates three job orderings and selects a complete, locally checked plan using the scenario objective and assignment changes. Separate audit logic checks the generated schedule. OpenAI's Responses API, using gpt-5.6-luna, powers natural-language interpretation and explanations grounded in schedule data. API credentials remain on the backend. Python's CSV and ZIP libraries handle PS1 imports and exports. Pytest and FastAPI's test client cover scheduling, disruptions, persistence, validation and error handling; browser checks verify the main user flows. The public demo runs on the 4bytedigi server using systemd, with HTTPS provided through Cloudflare Tunnel.

## What challenges did you face, and how did you overcome them?

The main challenge was coordinating track constraints, work dependencies and crew availability without hiding unfinished work. We built a deterministic scheduler and a separate output audit, and made unscheduled workloads visible instead of presenting incomplete plans as successful. Disruption handling also needed to preserve earlier assignments, so replanning freezes past weeks and compares future assignments with the original plan. Another challenge was making AI responses dependable: early routing confused activity IDs with locations and asked unnecessary questions. We added explicit identifier context, structured interpretation and direct handling of fully specified requests; schedule calculations remain in Python. We also replaced dense tables and technical location codes with weekly shift cards, readable track names and a guided preview-and-apply flow. Automated tests and browser checks helped catch regressions. Remaining work includes testing against the organisers' validator and measuring time savings with users.

## Required links — do not paste placeholders into the form

| Field | Current status | What you need |
|---|---|---|
| Pitch video URL | Not published | Record a three-minute demo, upload it to YouTube, and paste the shareable URL. |
| GitHub repository URL | Published | https://github.com/Pskm12E/Nus_Hackathon |
| Prototype URL | Published and verified | https://pliz.4bytedigi.com |

`http://127.0.0.1:5173/` works only on the machine running the app. It is not a public prototype URL. A DBstudios project is a database workspace, not the hosted app.

## Scenario ZIPs — packaging on hold

Packaging is paused at your request until you finish the project. No new ZIPs are being created or updated during this UI/submission-draft work. Earlier development bundles in `artifacts/` are not the final submission. When you are ready, each scenario ZIP must contain exactly:

- `SCHEDULE_ACCESS.csv`
- `SCHEDULE_OCCUPANCY.csv`
- `RESULTS.csv`

The existing public-data plans passed PLiZ's local checks. They have not been scored by the official validator. The form in your screenshot has limited runs and keeps the latest score, so record each official result before considering a revised upload. No official validator attempts were used to prepare these draft answers.

After you confirm that development is finished, generate fresh exports for the final roster and dataset, one for each planning approach.

## Three-minute video outline

**0:00–0:25 — The problem.** Railway planners must fit competing maintenance work into limited access nights. A closure or absence creates manual checking and rescheduling.

**0:25–0:55 — The plan.** Show the overview and weekly schedule. Open a shift to show its location, crew and work requirements. Explain that counts and dates come from the scheduler.

**0:55–1:20 — The team.** Open a fictional crew profile. Show skills, weekly limits and leave. Explain that saved availability is used in scheduling.

**1:20–2:05 — The disruption.** Open Test a change. Select a Beta H01–H02 eastbound closure, week 11, two weeks. Preview the impact. Explain the before-and-after completion dates, then apply and open the updated schedule.

**2:05–2:35 — The assistant.** Ask who is assigned to A003, or ask for an explanation of late contracts. Show the answer using actual schedule data. Explain that the model supports the planner while Python computes and checks schedules.

**2:35–3:00 — Evidence and next steps.** Show Checks & data and the CSV export. Mention local checks, synthetic source data, and the remaining official validation. Close with the benefit: less repetitive coordination and clearer decisions when plans change. Avoid claiming measured manpower savings or equipment-failure prediction.
