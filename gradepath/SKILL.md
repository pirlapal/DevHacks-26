---
name: gradepath
description: Track one course's grade trajectory, calculate what is needed for a target, and check Canvas for grade changes. Use for grade goals and what-if scores, not study plans or doing coursework.
---

# GradePath

Cubbie retrieves and communicates. Python calculates. Local files remember.
Never invent a grade, grading rule, platform API, or arithmetic result.

## Setup

Python 3 standard library only. Run commands from this Skill folder. No packages,
network access, secrets, server, or `cubbie.yaml` are needed.
Use an existing `SKILL_DATA_DIR` if available. Otherwise explicitly set it to
`$HOME/.local/share/gradepath` when invoking scripts; automatic injection of this
variable is not documented. This location is on the student's persistent drive.
The calculator and state scripts NEVER call Canvas or Cubbie tools.

Read [the input contract](references/input-contract.md) when assembling course data.
[The JSON schema](references/course.schema.json) defines the course object.
Save structured inputs as UTF-8 JSON files; do not interpolate student text into shell commands.

## Establish one course and a goal

1. Ask Cubbie to check whether the student has connected Canvas. If not, have
   the student send their school's Canvas URL and complete Cubbie's connection
   flow. Do not collect a password in chat. A connected account does not require
   the student's own browser to stay signed in. Revocation or an expired connection
   still requires reconnection.
2. Read available courses and disambiguate the student's course. Use identifiers
   actually returned by Cubbie, never guessed Canvas IDs. If stable IDs aren't
   available, confirm a mapping with the student and save it; never fuzzy-match
   different assignments silently.
3. Read accessible scores, maximum points, assignment categories, statuses,
   remaining work and official grading rules. Search course files for the syllabus
   if necessary. Canvas is the source for scores. Email is only a hint to check Canvas.
4. Confirm the target threshold using exposed reliable grading configuration,
   then syllabus, then official course material, then the student. Ask about conflicts.
   Never assume A=90. Record `rule_source`, `rules_status`, and optional per-rule
   provenance. Explicitly record whether the full future denominator is known.
5. Detect unsupported policies (drops, replacement exams, curves, extra credit,
   attendance adjustments, total overrides, unusual normalization). Populate
   `unsupported_rules`; do not silently omit them.
6. Assemble `course.json` using the contract, then run:

   ```sh
   python3 scripts/calculate.py course.json
   python3 scripts/state.py baseline --input course.json
   ```

   On an existing tracked course, read state first; use `check` rather than baseline.
   State or calculation errors mean stop and resolve, not improvise a result.
7. Explain the current graded average separately from the final grade projection.
   A weighted remaining average means the SAME percentage on every remaining point
   in each category; it is one sufficient path, not a unique assignment requirement.
   Use exact `solved.achievable_points` for discrete scores. Don't round a minimum
   percentage down; say “about” for display-only averages.
8. Ask whether the student wants monitoring, a reasonable daily time and timezone,
   and positive updates (off by default). Only create a recurring Cubbie check-in
   after that consent. Save the returned schedule reference in Cubbie memory.

## Scheduled check

Create a self-contained scheduled task using Cubbie's existing scheduling ability
in plain words. Do not invent a tool name or API parameters. Example task text:

> Run the GradePath Skill for [confirmed course reference], using this student's
> saved GradePath state at [resolved persistent directory]. Read the connected
> Canvas course, normalize current accessible grades and rules into a fresh JSON
> file, and run the GradePath check command. If retrieval fails, retain the prior
> state. Process pending notifications only when useful, respecting positive-update
> preferences. Stay silent on unchanged data. If rules change, ask for review.

At each run:

```sh
python3 scripts/state.py read
python3 scripts/state.py check --input fresh-course.json
```

- Fetch using Cubbie before invoking Python. Missing assignments in a partial
  response are not deleted. A score that becomes hidden is retained only as a
  historical observation and the projection becomes conditional.
- Retrieval failure: do not invoke `check` with empty invented data. Leave the
  last successful snapshot intact and retry on the next scheduled run.
- `needs_review`: pause projections. Explain the changed policy/denominator.
  After explicit rule confirmation, use `review --input confirmed-course.json --confirm`
  to replace the model while preserving event and notification history.
- `no_change`: no new notification. Inspect previously pending deliveries separately.
- `pending_grade`: retry on the next check; no inferred zero.
- `changed`: state contains uniquely identified events and a persisted notification
  outbox. Read `notifications` with status `pending`, not every historical event.
  Reconcile older pending events for the same assignment against the latest
  snapshot before composing a consolidated message; do not send stale projections.
- A below-target assignment triggers an impact check. It does not prove that
  the course average dropped below the target.
- Send one concise useful update to the student under their monitoring consent.
  Use `calculate.py` results, including uncertainty; don't claim Canvas officially
  reports a GradePath estimate. If target is conditionally impossible, say “under
  the currently known coursework.” Never assert a lower letter target without its
  verified threshold.
- After confirmed delivery, acknowledge each included event:

  ```sh
  python3 scripts/state.py ack --id EVENT_ID --status sent
  ```

  Known delivery failure: leave `pending` and retry at the next scheduled check.
  Unknown delivery outcome: mark `uncertain`; inspect conversation history before
  retrying. Do not automatically resend uncertain messages. There is no documented
  platform idempotency API, so exactly-once delivery cannot be promised across crashes.

Example update: “Project 1 changed from 85/100 to 80/100. I checked your 90% target.
You now need about 92.73% on each remaining assessment under the confirmed rules.
Want to explore a project/final scenario?” Use actual output, never this example
unless those are the verified inputs.

## What-if question

Load state and resolve assignment references. Do not mutate verified grades.
Pass a request file containing `course`, `scenario` (assignment ID → percentage),
and `solve_for` (remaining assignment ID) to `calculate.py`. Every other remaining
assignment needs a hypothetical score when solving for one assignment.
If underdetermined, ask for the missing condition or explain the same-percentage
remaining path. Read the returned `solved` object and explain its reachable flag,
required points, achievable points, and conditional status.

## Change preferences or stop

To update a target or positive notifications, save a JSON object containing
`target` and `positive_notifications`, then use `state.py target --input preferences.json`.
On “stop monitoring,” cancel the saved Cubbie schedule and confirm cancellation
before saying monitoring stopped. The local companion app does not control schedules.

## Limitations

No Gmail event trigger is assumed. Scheduling limits, exposed Canvas fields,
stable identifiers, hidden-score behavior, and invocation reliability must be
tested with the student's real connected account. Do not substitute the local
web application's sample data for a Canvas observation.
