# GradePath input contract

`calculate.py` accepts either a course object or `{ "course": COURSE, "scenario":
{ "assignment-id": 95 }, "solve_for": "final-id" }`. `state.py baseline/check/review`
accept the course object directly. All percentages are 0–100, not 0–1. All numeric
inputs must be finite. Internal arithmetic uses exact rational numbers parsed
from decimal strings. JSON outputs are numbers; round only for display.

Required course fields: `course_key`, `course_name`, `model`, `target`, `rule_source`,
`rules_status`, `data_completeness`, `categories`, `assignments`.
Optional fields: `course_code`, `target_label`, `source`, `positive_notifications`,
`unsupported_rules`, `provenance`.

Each category has a unique `id`, `name`, and `weight`. Weighted-course weights must
sum to 100. Points courses still use categories for display; their weights are ignored.
Each assignment has a unique stable `id`, `name`, `category`, `points_possible`,
`score`, `status`, and optionally `increment`, `source_reference`, `due_at`.
Unknown maximum points or scores are null. An unknown maximum prevents exact
projection. `increment` is optional: do not invent whole-point grading.

Statuses: graded, ungraded, submitted, missing, late, excused, hidden, not_due,
unavailable. Only verified scores with graded/missing/late status count. A missing
item without an explicit score is not zero. Excused work is excluded. Hidden and
unavailable scores are not inferred. Extra credit or zero-point items need review.

Rules statuses: confirmed, student_confirmed, inferred, unknown, conflicting.
Only confirmed/student_confirmed rules permit projection. Completeness:
complete, likely_complete, partial, unknown. Only complete permits an unconditional
maximum and target reachability. Other values return conditional fields.

Add `provenance` entries for each threshold, category weight, and denominator:
`{"rule":"target", "value":93, "source_type":"syllabus",
"source_reference":"page 3", "status":"confirmed"}`. `rule_source` is the
human-readable source summary; it does not override conflicting provenance.

The state store uses one atomic `state.json` instead of three independently written
files. It contains schema version, course, rule hash, monotonic revision, events,
notifications and last_successful_check. A new event's identity includes its revision,
so a legitimate 85→92→85 change is not suppressed. Keep this state private to one
student. A `.lock` prevents overlapping state writes. A crash may leave a lock;
inspect whether a process is still running before removing it.

Notification records contain `id`, `event`, `calculation`, `status`, `created_at`,
and optional `updated_at`. Status is pending, sent, or uncertain. Scripts never send
messages themselves. The web companion displays local events and cannot acknowledge
Cubbie delivery. The local app uses its own `.gradepath-data` directory.
