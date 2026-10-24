"""Atomic per-student state, snapshot events and notification outbox. No delivery API."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from calculate import calculate, validate

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def rules_hash(course):
    return digest({k: course.get(k) for k in ('model', 'categories', 'rule_source', 'rules_status', 'unsupported_rules', 'provenance')})

class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory or os.environ.get('SKILL_DATA_DIR') or Path.home() / '.local/share/gradepath')
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'state.json'

    @contextmanager
    def lock(self):
        path = self.directory / '.lock'
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ValueError('A GradePath update is already running. Retry later; inspect a stale lock before removing it.')
        try:
            os.close(descriptor)
            yield
        finally:
            path.unlink(missing_ok=True)

    def read(self):
        if not self.path.exists():
            return {'version': 1, 'course': None, 'revision': 0, 'events': [], 'notifications': [], 'last_successful_check': None}
        return json.loads(self.path.read_text(encoding='utf-8'))

    def write(self, state):
        fd, name = tempfile.mkstemp(dir=self.directory, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def baseline(self, course):
        validate(course)
        result = calculate(course)
        with self.lock():
            state = self.read()
            if state['course'] and state['course']['course_key'] != course['course_key']:
                raise ValueError('One course is already tracked. Export it and explicitly reset before replacing it.')
            if state['course']:
                raise ValueError('A baseline exists. Use check for updates instead of clearing notification history.')
            state.update(course=copy.deepcopy(course), rules_hash=rules_hash(course), last_successful_check=now())
            self.write(state)
        return {'status': 'baseline_ready' if result['status'] == 'success' else result['status'], 'calculation': result, 'state': state}

    def check(self, incoming):
        validate(incoming)
        with self.lock():
            state = self.read()
            old = state['course']
            if not old:
                raise ValueError('Establish a baseline first.')
            if incoming['course_key'] != old['course_key']:
                raise ValueError('This snapshot belongs to another course.')
            if rules_hash(incoming) != rules_hash(old):
                return {'status': 'needs_review', 'error': 'Grading rules changed. Confirm the new rules before replacing the baseline.', 'state': state}
            merged = copy.deepcopy(old)
            lookup = {a['id']: a for a in old['assignments']}
            changes = []
            pending = []
            changed_structure = False
            for item in incoming['assignments']:
                previous = lookup.get(item['id'])
                if previous and (previous.get('points_possible') != item.get('points_possible') or previous['category'] != item['category'] or (previous['status'] == 'excused') != (item['status'] == 'excused')):
                    changed_structure = True
                if item.get('score') is None or item['status'] in ('hidden', 'unavailable'):
                    if previous and previous.get('score') is not None:
                        pending.append(item['id'])
                        continue
                before = None if previous is None else previous.get('score')
                after = item.get('score')
                if after is not None and item['status'] in ('graded', 'missing', 'late') and before != after:
                    changes.append({'assignment_id': item['id'], 'name': item['name'], 'before': before, 'after': after, 'points_possible': item.get('points_possible'), 'type': 'new_grade' if before is None else 'changed_grade'})
                lookup[item['id']] = copy.deepcopy(item)
            if changed_structure:
                return {'status': 'needs_review', 'error': 'Assignment points, category, or excusal changed. Confirm the denominator before updating.', 'state': state}
            merged['assignments'] = list(lookup.values())
            merged['target'] = incoming['target']
            merged['target_label'] = incoming.get('target_label', old.get('target_label', 'Custom'))
            merged['source'] = incoming.get('source', old.get('source', 'imported'))
            merged['positive_notifications'] = incoming.get('positive_notifications', old.get('positive_notifications', False))
            if incoming['data_completeness'] != 'complete' or set(lookup) != {a['id'] for a in incoming['assignments']}:
                merged['data_completeness'] = 'partial'
            else:
                merged['data_completeness'] = 'complete'
            if pending:
                merged['data_completeness'] = 'partial'
            result = calculate(merged)
            for change in changes:
                state['revision'] += 1
                change.update(id=digest([old['course_key'], state['revision'], change, rules_hash(old)]), observed_at=now())
                state['events'].append(change)
                positive = change['before'] is not None and change['after'] > change['before']
                below = change['points_possible'] and change['after'] / change['points_possible'] * 100 < merged['target']
                useful = (not positive and below) or (not positive and change['before'] is not None) or merged.get('positive_notifications', False)
                if useful:
                    state['notifications'].append({'id': change['id'], 'event': change, 'calculation': result, 'status': 'pending', 'created_at': now()})
            state.update(course=merged, last_successful_check=now())
            self.write(state)
            return {'status': 'changed' if changes else ('pending_grade' if pending else 'no_change'), 'changes': changes, 'pending_grades': pending, 'calculation': result, 'state': state}

    def update_target(self, target, positive):
        with self.lock():
            state = self.read()
            if not state['course']:
                raise ValueError('No course is tracked.')
            state['course']['target'] = target
            state['course']['positive_notifications'] = bool(positive)
            validate(state['course'])
            self.write(state)
            return state

    def review(self, course, confirmed=False):
        if not confirmed:
            raise ValueError('Explicit confirmation is required to replace reviewed rules.')
        validate(course)
        result = calculate(course)
        if result['status'] != 'success':
            raise ValueError('Resolve unsupported or unknown rules and missing inputs before confirming this model.')
        with self.lock():
            state = self.read()
            if not state['course'] or state['course']['course_key'] != course['course_key']:
                raise ValueError('Review must refer to the tracked course.')
            state.setdefault('rule_reviews', []).append({'previous_course': state['course'], 'reviewed_at': now()})
            state.update(course=copy.deepcopy(course), rules_hash=rules_hash(course), last_successful_check=now())
            self.write(state)
        return {'status': 'reviewed', 'calculation': result, 'state': state}

    def acknowledge(self, event_id, status):
        if status not in ('sent', 'uncertain', 'pending'):
            raise ValueError('Use sent, uncertain, or pending.')
        with self.lock():
            state = self.read()
            match = next((n for n in state['notifications'] if n['id'] == event_id), None)
            if not match:
                raise ValueError('Unknown notification.')
            match.update(status=status, updated_at=now())
            self.write(state)
        return state

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['baseline', 'check', 'read', 'ack', 'target', 'review'])
    parser.add_argument('--input')
    parser.add_argument('--id')
    parser.add_argument('--status', default='sent')
    parser.add_argument('--data-dir')
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    try:
        store = Store(args.data_dir)
        payload = json.loads(Path(args.input).read_text(encoding='utf-8')) if args.input else None
        if args.action in ('baseline', 'check'):
            response = getattr(store, args.action)(payload)
        elif args.action == 'ack':
            response = store.acknowledge(args.id, args.status)
        elif args.action == 'target':
            response = store.update_target(payload['target'], payload.get('positive_notifications', False))
        elif args.action == 'review':
            response = store.review(payload, args.confirm)
        else:
            response = store.read()
        print(json.dumps(response, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        raise SystemExit(1)

if __name__ == '__main__':
    main()
