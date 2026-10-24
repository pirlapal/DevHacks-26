# GradePath

**Your goal. Your way there.** A deterministic grade trajectory calculator, a
Cubbie Skill, and a companion app inspired by the Cubbie hackathon site.

## Run the app

Requires Python 3.10+; no package installation or build step.

```sh
python app.py
```

Open http://127.0.0.1:8765. Use `--port 8766` if that port is busy.
The application binds only to this computer. It is a local demo and personal
calculator, not an internet production server. Nunito and Shantell Sans load
from Google Fonts, with system fallbacks when offline.

Try the weighted or points-based example, set a target, explore what-if scores,
record a new/revised grade, add coursework, or import/export a course JSON file.
Edits survive reload in the ignored `.gradepath-data/` directory. Switching courses
requires confirmation and saves the previous state as `previous-state.json`.
Export a course before repeated switches to keep multiple archives.

**Canvas is not connected to this local app.** Demo data is labeled. Real Canvas
retrieval and scheduled iMessages belong to the separately installed Cubbie Skill.
The Connect button explains the process; it does not fake a successful connection,
schedule, or message delivery.

## Install the Cubbie Skill

The self-contained folder is [`gradepath/`](gradepath/SKILL.md). Publish it in a
public GitHub repository, then send Cubbie the public link to that folder and ask
it to install GradePath. Verify installation in a new message. This repository
has not been published or installed by this build session.

Connect Canvas to Cubbie using the school's Canvas link and its connection flow.
The connection belongs to Cubbie and does not require the student's browser to
stay signed in. Then ask:

> Track my Software Engineering course with GradePath. Help me finish at the A
> threshold in my syllabus. Verify the grading rules, explain my baseline, and
> ask me about a daily check-in.

Cubbie orchestrates retrieval/scheduling/delivery in plain language. Scripts only
calculate and persist state. No SDK, Canvas endpoint, webhook, or hosted bridge is
invented. Use `SKILL_DATA_DIR` if supplied, or explicitly set it to
`$HOME/.local/share/gradepath`; automatic variable injection is unverified.

## Calculator and state commands

From the `gradepath` folder:

```sh
python scripts/calculate.py course.json
python scripts/state.py baseline --input course.json
python scripts/state.py check --input updated-course.json
python scripts/state.py read
python scripts/state.py ack --id EVENT_ID --status sent
python scripts/state.py review --input confirmed-course.json --confirm
```

`calculate.py` also accepts a request with `course`, `scenario` mapping assignment
IDs to percentages, and `solve_for`. Hypotheticals do not modify saved scores.
Only acknowledge messages when Cubbie confirms delivery. Unknown outcomes are
`uncertain` and need conversation-history reconciliation before retry.

## Correctness

```sh
python -m unittest discover -s tests -v
```

Exact rational arithmetic supports points and straightforward weighted categories.
Ungraded is not zero. Excused work is excluded. Hidden grades, unknown denominators,
conflicting sources, drop-lowest rules, extra credit and other unsupported policies
are explicit. Discrete required scores round upward. State and notification outbox
are written atomically; repeated snapshots do not duplicate events.

The supplied weighted example with Project2=95 and target90 needs Final=90.
At target93, it needs Final=97.5 (98 if only whole points are possible).

See [architecture and live acceptance gates](docs/architecture.md) and
[the course schema](gradepath/references/course.schema.json).

For copy-and-paste PowerShell commands, expected results, browser checks, and
Cubbie integration testing, see [the testing guide](docs/testing.md).

## Remaining live verification

Publish/install the Skill, connect a real Canvas account, verify fields and syllabus
rules, observe a scheduled run, and confirm actual iMessage delivery. These depend
on Cubbie's connected account and are not simulated as completed.

Branches: `main` for shared work, `demo2` for this demo implementation, `track-1`
for Track 1 work, and `track-3` for the separate group-chat track.
