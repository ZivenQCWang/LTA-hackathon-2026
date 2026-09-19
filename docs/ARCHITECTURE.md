# PLiZ implementation details

A local hackathon workspace for NebulaX PS1 railway track access planning. It generates crew-assigned possession schedules, compares closure/absence scenarios, and provides a grounded OpenAI assistant.

## Run on Windows

The current workspace already has dependencies installed. Run `./start.ps1` from PowerShell, then open http://127.0.0.1:5173. Stop with Ctrl+C. Close existing servers first if their ports are occupied.

Fresh setup:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
npm install
Copy-Item .env.example .env
./start.ps1
```

Set `OPENAI_API_KEY` and optionally `OPENAI_MODEL` in `.env`. The default is `gpt-5.6-luna`. This file is ignored by Git and is read only by the backend. Never use a `VITE_` variable for an API key. Use AI assistant → Connection details → Check connection to check access. Without a key, the app provides local schedule summaries; provider failures are shown explicitly. OpenAI calls use `store=False`.

For a single-process production-build preview:

```powershell
npm run build
./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000. Local development has no login. See [Deployment](DEPLOYMENT.md) for hosted origins, the explicit public-demo mode, optional shared login and AI rate limits.

## Working flows

The interface uses gold (`#FDC323`), forest green (`#00785D`), sky blue (`#32BFDB`) and slate teal (`#539BA9`). Phone and tablet layouts include bottom navigation, a More menu, larger form controls, and card layouts for schedule, milestone and forecast rows. The timeline scrolls within its panel. The supplied PLiZ icon and wordmark replace the earlier lightning branding.

- **Overview:** computed workload, late-contract attention cards, quick actions and a clickable weekly workload chart.
- **Schedule:** weekly shift cards, all-shifts and timeline views, name/contract/crew filters, accessible shift-details dialogs, contract milestones, and schedule export. ZIP packaging is currently on hold until the user confirms development is finished.
- **Your crew:** 24 explicitly fictional profiles, bulk additions, role/skill/weekly limit edits, leave weeks (`5,8,12-14`) and active status. Saved changes invalidate old forecasts and regenerate the baseline.
- **Test a change:** full-week track closures and named absences; past weeks are frozen, future accesses are replanned, and changed dates/crew are compared with the baseline. Results persist. Apply a candidate only if local checks pass and the baseline has not changed. Use Rebuild plan before testing another disruption against an already applied plan. The guided form uses readable line/section/direction choices and a review-before-apply workflow.
- **AI assistant:** answers questions and executes explicit requests to add crew, edit a named person's skills/availability, add a maintenance activity under an existing contract, rebuild the selected scenario, or apply the active forecast. Missing details prompt a follow-up. Simulations remain previews until the user explicitly asks to apply them. Each successful write shows a saved-action receipt and a link to the relevant view. Examples populate the composer first. Requests, model output/usage and receipts persist in SQLite; request IDs prevent duplicate writes on retry. The visible conversation remains session-only.
- **Checks & data:** actual audit findings, limitations, eight-file CSV import, and restore of the official sample instance.

## Data and persistence

**Dataset priority:** Use the organiser-provided [GitHub PS1 dataset](https://github.com/aochinwen/NebulaX-Hackathon-ProblemStatement/tree/main/PS1/01_data) and its problem-statement rules as the primary source for planning and hackathon evaluation, as requested by the user. The eight source CSVs are preserved in `data/official/01_data/`; their downloaded revision and hashes are recorded in `data/official/provenance.json`. Public LTA datasets and news sources are supplementary context and must not silently replace or relabel the organiser's planning inputs. Keep added fictional crew and user-entered disruption simulations clearly identified as demo inputs.

The rail dataset is the organiser's **synthetic** Alpha/Beta network: 54 activities, 14 contracts and 192 standard work units. It is not live MRT operations data. Sources and downloaded files are in `data/official/`; `provenance.json` records origins. The fictional crew roster is an additional demo layer.

SQLite at `storage/nightshift.db` stores people, instance overrides, applied plans and forecast history. Public reports are also saved locally with photo bytes and a durable delivery queue, then delivered through the DBStudios project API to NightShift AI's `public_reports` table. The **Public's report** inbox reads from DBStudios when configured. Planner data and photo bytes stay in SQLite; DBStudios is not a complete backup. See [Public app](PUBLIC_APP.md) and [DBStudios reports](DBSTUDIOS_REPORTS.md).

Chat-created maintenance jobs modify a labelled working copy, preserving the eight organiser CSVs. New jobs need an existing contract, exact endpoints, workload and start date/week. Their type and possession rules come from that contract. Roster/job commands recalculate the schedule before committing; unresolved checks leave the workspace unchanged. Existing applied disruption constraints and frozen past assignments are preserved. Chat cannot delete records, create contracts, or export ZIPs. One independent write is handled per message. Monetary cost estimates are not guessed; raw provider token usage and the configured model are saved with each generation.

## Planner and limits

`backend/planner.py` runs three deterministic greedy orderings and chooses the best complete audited result by objective and changed accesses. This is a heuristic, not a proof of optimality or infeasibility. Local audit code independently recomputes workload, precedence, crew limits, possession conflicts, capacity, contract budgets and ECLO rules from output rows.

Scenario A has strict supply and no ECLO; B has strict planned dates with extra supply/ECLO penalties; C allows at most one extra location-night per week and a two-week ECLO span per affected line. Scores implement the published weights. An incomplete plan shows unscheduled work explicitly and cannot be exported or applied.

Crew assumptions: one qualified Engineer plus one Technician per activity-night, at most one shift per night, skill matching, weekly limits and leave. Live work requires electrical skills. Live exclusion handling is conservative. Weekly supply repeats past the input horizon; search extends up to 52 extra weeks, capped at week 104. There is no intra-night duration or travel-time model.

Calendar `night` (1–7) is used for crew dispatch and shared physical possessions. Exported `access_night` is remapped to the required local contract/type/week index. Exports contain exactly `SCHEDULE_ACCESS.csv`, `SCHEDULE_OCCUPANCY.csv`, and `RESULTS.csv`.

The organisers' reference validator is not included. Passing this app's local audit is **not official validation**. Validate exports with the organisers' tooling before submitting. Hidden instances may need a stronger search algorithm.

Forecast bands describe scenario impacts, not calibrated failure probabilities. Equipment failure prediction requires asset condition, inspection and maintenance-history data that this dataset does not contain.

## Verify

```powershell
./.venv/Scripts/python.exe -m pytest tests -q -k "not export"
npm run build
```

Tests use a separate temporary database and cover A/B/C, named crew absences, frozen history, no-op forecasts, incomplete staffing, corrupted-plan audit checks, roster persistence, stale-candidate rejection, CSV upload/export and redacted AI failures. Live API checks require a configured key and are not part of the automated suite.

## Proposal draft

`SUBMISSION.md` contains three ready-to-review answers under 150 words each, the remaining publishing links, and a three-minute demo outline. ZIP creation and official-validator uploads are on hold until the user is finished.
