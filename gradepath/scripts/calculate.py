"""GradePath's deterministic calculator. No network calls or third-party packages."""
import copy
import json
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import ceil

D = Fraction
STATUSES = {'graded', 'ungraded', 'submitted', 'missing', 'late', 'excused', 'hidden', 'not_due', 'unavailable'}

def number(value, label, minimum=0, maximum=None):
    if isinstance(value, bool) or value is None:
        raise ValueError(f'{label} must be a number.')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label} must be a number.')
    if not result.is_finite() or result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f'{label} is outside the supported range.')
    return Fraction(result)

def output(value):
    return None if value is None else float(value)

def validate(course):
    if not isinstance(course, dict):
        raise ValueError('A course object is required.')
    for key in ('course_key', 'course_name', 'model', 'target', 'categories', 'assignments'):
        if key not in course:
            raise ValueError(f'Missing {key}.')
    if not isinstance(course['course_key'], str) or not course['course_key'].strip():
        raise ValueError('A stable course_key is required.')
    if not isinstance(course['course_name'], str) or not course['course_name'].strip():
        raise ValueError('A course name is required.')
    if course['model'] not in ('points', 'weighted'):
        raise ValueError('Choose points or weighted grading.')
    number(course['target'], 'Target', maximum=100)
    if course.get('data_completeness') not in ('complete', 'likely_complete', 'partial', 'unknown'):
        raise ValueError('Set data_completeness explicitly.')
    if course.get('rules_status') not in ('confirmed', 'student_confirmed', 'inferred', 'unknown', 'conflicting'):
        raise ValueError('Set rules_status explicitly.')
    if not isinstance(course.get('rule_source'), str) or not course['rule_source'].strip():
        raise ValueError('Record the source of the grading rules.')
    if not isinstance(course.get('unsupported_rules', []), list):
        raise ValueError('unsupported_rules must be a list.')
    if any(not isinstance(rule, str) for rule in course.get('unsupported_rules', [])):
        raise ValueError('Unsupported rules must be descriptions.')
    if 'positive_notifications' in course and not isinstance(course['positive_notifications'], bool):
        raise ValueError('positive_notifications must be true or false.')
    if not isinstance(course.get('provenance', []), list):
        raise ValueError('provenance must be a list.')
    for rule in course.get('provenance', []):
        if not isinstance(rule, dict) or any(key not in rule for key in ('rule', 'value', 'source_type', 'source_reference', 'status')):
            raise ValueError('Each provenance entry needs rule, value, source_type, source_reference, and status.')
    if not isinstance(course['categories'], list) or not course['categories']:
        raise ValueError('At least one category is required.')
    if not isinstance(course['assignments'], list):
        raise ValueError('assignments must be a list.')
    categories = {}
    for c in course['categories']:
        if not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id'] or c['id'] in categories:
            raise ValueError('Categories need unique, nonempty IDs.')
        if not isinstance(c.get('name'), str) or not c['name'].strip():
            raise ValueError('Each category needs a name.')
        categories[c['id']] = number(c.get('weight', 0), 'Category weight', maximum=100)
    if course['model'] == 'weighted' and sum(categories.values()) != 100:
        raise ValueError('Category weights must total exactly 100%.')
    ids = set()
    for a in course['assignments']:
        if not isinstance(a, dict) or not isinstance(a.get('id'), str) or not a['id'] or a['id'] in ids:
            raise ValueError('Assignments need unique, nonempty IDs.')
        ids.add(a['id'])
        if not isinstance(a.get('name'), str) or not a['name'].strip():
            raise ValueError('Each assignment needs a name.')
        if a.get('category') not in categories:
            raise ValueError('Assignment category is not defined.')
        if a.get('status') not in STATUSES:
            raise ValueError('Assignment has an unknown status.')
        if a.get('points_possible') is not None:
            number(a['points_possible'], 'Points possible')
        if a.get('score') is not None:
            number(a['score'], 'Score')
        if a.get('increment') is not None and number(a['increment'], 'Score increment') == 0:
            raise ValueError('Score increment must be positive.')
    return course

def calculate(course, scenario=None, solve_for=None):
    validate(course)
    course = copy.deepcopy(course)
    scenario = scenario or {}
    if not isinstance(scenario, dict):
        raise ValueError('Scenario must map assignment IDs to percentages.')
    by_id = {a['id']: a for a in course['assignments']}
    for key, percentage in scenario.items():
        if key not in by_id or by_id[key]['status'] not in ('ungraded', 'submitted', 'not_due', 'late', 'missing') or by_id[key].get('score') is not None:
            raise ValueError('Scenarios must refer to visible, ungraded assignments.')
        number(percentage, 'Scenario percentage', maximum=100)
    if solve_for is not None and (solve_for not in by_id or solve_for in scenario or by_id[solve_for]['status'] not in ('ungraded', 'submitted', 'not_due', 'late', 'missing') or by_id[solve_for].get('score') is not None):
        raise ValueError('Choose an ungraded assignment to solve for.')
    warnings = []
    review = list(course.get('unsupported_rules', []))
    if course['rules_status'] not in ('confirmed', 'student_confirmed'):
        review.append('Grading rules need confirmation or conflict resolution.')
    for rule in course.get('provenance', []):
        if rule['status'] not in ('confirmed', 'student_confirmed'):
            review.append(f"{rule['rule']}: source is not confirmed.")
    totals = {c['id']: {'earned': D(0), 'graded': D(0), 'remaining': D(0), 'fixed': D(0), 'variable': D(0)} for c in course['categories']}
    incomplete = False
    for a in course['assignments']:
        if a['status'] == 'excused':
            continue
        p = a.get('points_possible')
        if p is None:
            incomplete = True
            warnings.append(f"{a['name']}: points possible are unknown.")
            continue
        p = number(p, 'Points possible')
        if p == 0:
            review.append(f"{a['name']}: zero-point or bonus work needs review.")
            continue
        t = totals[a['category']]
        if a['status'] in ('hidden', 'unavailable'):
            incomplete = True
            warnings.append(f"{a['name']}: score unavailable; no score inferred.")
            continue
        if a.get('score') is not None:
            if a['status'] not in ('graded', 'missing', 'late'):
                review.append(f"{a['name']}: score and status conflict.")
                continue
            score = number(a['score'], 'Score')
            if score > p:
                review.append(f"{a['name']}: extra credit needs review.")
            t['earned'] += score
            t['graded'] += p
        else:
            if a['status'] == 'graded':
                incomplete = True
                warnings.append(f"{a['name']}: marked graded but score unavailable.")
                continue
            t['remaining'] += p
            if a['id'] in scenario:
                hypothetical = p * number(scenario[a['id']], 'Scenario percentage') / 100
                if a.get('increment') is not None and hypothetical % number(a['increment'], 'Increment') != 0:
                    raise ValueError(f"{a['name']}: scenario does not match its score increment.")
                t['fixed'] += hypothetical
            else:
                t['variable'] += p
    earned = sum(t['earned'] for t in totals.values())
    graded = sum(t['graded'] for t in totals.values())
    remaining = sum(t['remaining'] for t in totals.values())
    denominator = graded + remaining
    base = D(0)
    capacity = D(0)
    current = None
    category_results = []
    active_weight = D(0)
    current_sum = D(0)
    for c in course['categories']:
        t = totals[c['id']]
        weight = number(c['weight'], 'Weight') / 100 if course['model'] == 'weighted' else D(0)
        final_possible = t['graded'] + t['remaining']
        if course['model'] == 'weighted':
            if not final_possible and weight:
                incomplete = True
                warnings.append(f"{c['name']}: final category total unknown.")
            elif final_possible:
                base += weight * (t['earned'] + t['fixed']) / final_possible
                capacity += weight * t['variable'] / final_possible
            if t['graded']:
                current_sum += weight * t['earned'] / t['graded']
                active_weight += weight
        category_results.append({'id': c['id'], 'name': c['name'], 'weight': c['weight'], 'earned': output(t['earned']), 'graded': output(t['graded']), 'remaining': output(t['remaining']), 'average': output(t['earned'] / t['graded'] * 100) if t['graded'] else None})
    if course['model'] == 'points':
        current = earned / graded if graded else None
        if denominator:
            base = (earned + sum(t['fixed'] for t in totals.values())) / denominator
            capacity = sum(t['variable'] for t in totals.values()) / denominator
        else:
            incomplete = True
    elif active_weight:
        current = current_sum / active_weight
    target = number(course['target'], 'Target') / 100
    conditional = course['data_completeness'] != 'complete'
    if conditional:
        warnings.append('Based on currently known coursework; the final denominator is not confirmed complete.')
    status = 'needs_review' if review else ('needs_information' if incomplete else 'success')
    required = (target - base) / capacity if capacity else None
    reachable = (base + capacity >= target) if status == 'success' else None
    solved = None
    if solve_for and status == 'success':
        other = [a for a in course['assignments'] if a['id'] != solve_for and a['status'] != 'excused' and a.get('score') is None and a['id'] not in scenario]
        if other:
            raise ValueError('Set a scenario for all other ungraded work before solving one assignment.')
        a = by_id[solve_for]
        p = number(a['points_possible'], 'Points possible')
        raw = max(D(0), required or D(0)) * p
        inc = number(a['increment'], 'Increment') if a.get('increment') is not None else None
        achievable = ceil(raw / inc) * inc if inc else raw
        solved = {'id': solve_for, 'required_points': output(raw), 'achievable_points': output(achievable), 'points_possible': output(p), 'required_percentage': output(achievable / p * 100), 'reachable': achievable <= p, 'rounding_applied': inc is not None}
    safe = status == 'success'
    return {'status': status, 'model': course['model'], 'current_graded_average': output(current * 100) if current is not None and not review else None,
            'earned_points': output(earned), 'graded_points': output(graded), 'remaining_points': output(remaining),
            'target_percentage': output(target * 100), 'target_reachable': reachable if not conditional else None,
            'conditional_target_reachable': reachable if conditional else None,
            'required_remaining_average': output(max(D(0), required) * 100) if safe and required is not None else None,
            'required_remaining_points': output(max(D(0), target * denominator - earned - sum(t['fixed'] for t in totals.values()))) if safe and course['model'] == 'points' else None,
            'maximum_known_possible_grade': output((base + capacity) * 100) if safe and not conditional else None,
            'conditional_maximum': output((base + capacity) * 100) if safe and conditional else None,
            'projected_final': output(base * 100) if safe and not capacity else None,
            'secured_contribution': output(base * 100) if safe and not scenario and not conditional else None,
            'target_already_secured': bool(safe and base >= target and not conditional),
            'categories': category_results, 'scenario': scenario, 'solved': solved, 'warnings': warnings + review,
            'data_completeness': course['data_completeness'], 'conditional': conditional,
            'requirement_label': 'Same percentage on every remaining point in each category' if course['model'] == 'weighted' else 'Average across remaining points'}

def main():
    try:
        request = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else json.load(sys.stdin)
        print(json.dumps(calculate(request.get('course', request), request.get('scenario'), request.get('solve_for')), allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        sys.exit(1)

if __name__ == '__main__':
    main()
