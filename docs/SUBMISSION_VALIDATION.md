# Submission checks and the Scenario A correction

PLiZ's first test export was rejected by the organiser's portal with 49 closure
violations. The previous local audit only compared jobs on the same internal
calendar night. That did not match the weekly possession graph encoded in
`SCHEDULE_OCCUPANCY.csv`.

The correction keeps the three required filenames and headers unchanged:

- `SCHEDULE_ACCESS.csv`: work, weeks, ECLO and local contract/type/week night indices.
- `SCHEDULE_OCCUPANCY.csv`: each occupied location and its possession group.
- `RESULTS.csv`: completion dates and overruns for every contract, for one scenario.

Possession members are connected through shared `(location_id, week,
co_share_group)` values. An external activity cannot occupy that possession's
closure zone in the same week. Changing an internal night number does not
resolve that exported conflict. The scheduler now places compatible jobs in
the same possession or moves conflicting jobs to another week. Crew and
workfront checks still use the actual internal dispatch nights.

The corrected closure footprint includes Live isolation buffers on both lines
at the interchange. A consist buffer includes the adjoining tunnel without its
far platform; Live isolation includes the far platform. These details were
checked against the supplied instance, published sample and actual portal
feedback. They are a local interpretation, not access to the reference code.

`tests/test_submission_closures.py` reproduces all 49 original reports exactly,
accepts the official sample's closure arrangements, and proves that a stale
`audit.passed` flag cannot bypass CSV closure inspection. The API also rebuilds
plans made by an older planner version while retaining their applied disruption
restrictions, and checks the CSV content before allowing an export.

The reference validator is not published in the problem-statement repository.
Local passing results remain provisional until the organiser validates the
submission. A low objective score is meaningful only after feasibility passes;
lateness is permitted in A/C but physical closure violations are not. Do not
reuse the rejected ZIPs or describe their earlier local scores as official.

## Scenario C verification and trade-offs

The corrected B export was subsequently confirmed **Feasible, score 30.0** by
the organiser's portal in the user's screenshot. Its CSV hashes are retained
in a regression test. C must still be submitted independently.

C now compares optional ECLO use against standard-night alternatives, keeping
the original three candidates and testing up to eight activities across the
same three orderings. Only a complete, audited plan with a better rank can
replace the original. This is bounded search, not a proof of optimality. On the
supplied instance the local C penalty improves from 29.1 to 26.1: two ECLO nights
instead of four, zero excess nights, and all 54 activities fully delivered.

100% workload does not mean zero lateness. A036 requires seven work units,
starts in week 22 and has a week-26 target. There are only five eligible weeks
before that target. C permits at most two ECLO accesses per activity, so those
five weeks can deliver at most six units. Its earliest possible finish is
week 27, even before considering other jobs. The UI now explains this C-specific
bound instead of assuming unrestricted ECLO.

`validate_csv_content` independently reads the exported text and checks the
published filenames, headers, workloads, start dates, predecessor order,
weekly budgets, workfronts, occupancy coverage, legal mixes, weekly closures,
scenario capacity policy, C's per-line ECLO windows (including cross-line Live
work), B's fixed deadlines and every reported completion date/overrun. It
recomputes coverage and score without trusting the saved plan's audit flag.
Tests corrupt these fields deliberately and confirm rejection. These remain
local checks, not the organiser's reference implementation.
