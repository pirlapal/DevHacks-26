"""Step 1 connection check: read course JSON, report what Canvas exposed, save and reload state."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from decimal import Decimal

FIELDS = ["id", "group", "score", "points_possible", "graded", "excused", "missing", "late"]


def state_path():
    base = os.environ.get("SKILL_DATA_DIR") or os.path.join(os.path.expanduser("~"), ".gradepath")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "probe_state.json")


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_state(path, state):
    # Write to a temp file first so a crash never leaves half a file behind.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def to_decimal(value):
    if value is None or isinstance(value, bool):
        return None
    return Decimal(str(value))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    try:
        with open(args.input) as f:
            course = json.load(f)
        assignments = course["assignments"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Error: could not read course data ({e}).")
        return 1

    # Which fields did Canvas actually give us a value for?
    coverage = {field: sum(1 for a in assignments if a.get(field) is not None) for field in FIELDS}

    earned = Decimal(0)
    possible = Decimal(0)
    for a in assignments:
        score, points = to_decimal(a.get("score")), to_decimal(a.get("points_possible"))
        if a.get("excused") or score is None or not points:
            continue
        earned += score
        possible += points

    path = state_path()
    previous = load_state(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save_state(path, {
        "run_count": (previous or {}).get("run_count", 0) + 1,
        "last_run": now,
        "course_name": course.get("course_name"),
        "course": course,
    })
    reloaded = load_state(path)

    lines = [f"GradePath connection check: {course.get('course_name') or 'unnamed course'}"]
    lines.append(f"Assignments received: {len(assignments)}")
    lines.append("Fields with values: " + ", ".join(f"{k} {v}/{len(assignments)}" for k, v in coverage.items()))
    lines.append(f"Group weights received: {len(course.get('group_weights') or [])}")
    if possible > 0:
        pct = (earned / possible * 100).quantize(Decimal("0.01"))
        lines.append(f"Graded points (unweighted): {earned}/{possible} = {pct}%")
    else:
        lines.append("Graded points: none yet")
    if previous:
        lines.append(f"Saved state: found previous run from {previous.get('last_run')} (run #{reloaded['run_count']})")
    else:
        lines.append("Saved state: first run, state saved")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
