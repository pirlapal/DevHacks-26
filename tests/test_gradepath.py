import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import demo
from calculate import calculate, validate
from state import Store

class CalculatorTests(unittest.TestCase):
    def test_points_exact_boundary(self):
        result = calculate(demo('points'))
        self.assertEqual(result['required_remaining_points'], 200)
        self.assertEqual(result['required_remaining_average'], 100)
        self.assertTrue(result['target_reachable'])

    def test_points_impossible(self):
        course = demo('points'); course['target'] = 93
        result = calculate(course)
        self.assertEqual(result['required_remaining_points'], 210)
        self.assertEqual(result['maximum_known_possible_grade'], 92)
        self.assertFalse(result['target_reachable'])

    def test_weighted_scenario(self):
        result = calculate(demo(), {'project-2': 95}, 'final')
        self.assertEqual(result['solved']['required_points'], 90)
        self.assertEqual(result['solved']['achievable_points'], 90)

    def test_weighted_93_is_not_90_final(self):
        course = demo(); course['target'] = 93
        solved = calculate(course, {'project-2': 95}, 'final')['solved']
        self.assertEqual(solved['required_points'], 97.5)
        self.assertEqual(solved['achievable_points'], 98)

    def test_weighted_baseline(self):
        result = calculate(demo())
        self.assertEqual(result['current_graded_average'], 87.5)
        self.assertEqual(result['secured_contribution'], 39.75)
        self.assertEqual(result['maximum_known_possible_grade'], 94.75)
        self.assertAlmostEqual(result['required_remaining_average'], 91.36363636363636)

    def test_ungraded_not_zero(self):
        course = demo('points')
        self.assertEqual(calculate(course)['current_graded_average'], 90)
        course['assignments'][1].update(score=0, status='missing')
        self.assertEqual(calculate(course)['current_graded_average'], 72)

    def test_hidden_score_not_inferred(self):
        course = demo(); course['assignments'][1]['status'] = 'hidden'
        result = calculate(course)
        self.assertEqual(result['status'], 'needs_information')
        self.assertIsNone(result['target_reachable'])
        self.assertIsNone(result['maximum_known_possible_grade'])

    def test_incomplete_denominator(self):
        course = demo('points'); course.update(target=93, data_completeness='partial')
        result = calculate(course)
        self.assertIsNone(result['target_reachable'])
        self.assertIsNone(result['maximum_known_possible_grade'])
        self.assertEqual(result['conditional_maximum'], 92)
        self.assertFalse(result['conditional_target_reachable'])
        self.assertIsNone(result['secured_contribution'])

    def test_unsupported_policy(self):
        course = demo(); course['unsupported_rules'] = ['Drop lowest quiz']
        result = calculate(course)
        self.assertEqual(result['status'], 'needs_review')
        self.assertIsNone(result['required_remaining_average'])

    def test_conflicting_rules(self):
        course = demo(); course['rules_status'] = 'conflicting'
        self.assertEqual(calculate(course)['status'], 'needs_review')

    def test_conflicting_provenance(self):
        course = demo()
        course['provenance'] = [{'rule':'target', 'value':93, 'source_type':'syllabus', 'source_reference':'page 3', 'status':'conflicting'}]
        self.assertEqual(calculate(course)['status'], 'needs_review')

    def test_round_up_achievable_points(self):
        course = demo('points'); course.update(target=92.4)
        course['assignments'] = [{'id':'final','name':'Final','category':'all','points_possible':50,'score':None,'status':'not_due','increment':1}]
        result = calculate(course, {}, 'final')['solved']
        self.assertEqual(result['required_points'], 46.2)
        self.assertEqual(result['achievable_points'], 47)

    def test_exact_fraction_rounding(self):
        course = demo(); course['target'] = 90
        course['categories'] = [{'id':'a','name':'A','weight':100}]
        course['assignments'] = [{'id':'done','name':'Done','category':'a','score':2,'points_possible':3,'status':'graded'}, {'id':'final','name':'Final','category':'a','score':None,'points_possible':7,'status':'not_due','increment':1}]
        self.assertEqual(calculate(course, {}, 'final')['solved']['achievable_points'], 7)

    def test_missing_points(self):
        course = demo(); course['assignments'][1]['points_possible'] = None
        self.assertEqual(calculate(course)['status'], 'needs_information')

    def test_no_remaining_work(self):
        course = demo('points'); course['assignments'][1].update(score=200,status='graded')
        result = calculate(course)
        self.assertEqual(result['projected_final'], 92)
        self.assertTrue(result['target_already_secured'])

    def test_all_ungraded(self):
        course = demo();
        for a in course['assignments']: a.update(score=None,status='not_due')
        result = calculate(course)
        self.assertIsNone(result['current_graded_average'])
        self.assertEqual(result['required_remaining_average'], 90)

    def test_excused_excluded(self):
        course = demo('points'); course['assignments'][1]['status'] = 'excused'
        self.assertEqual(calculate(course)['projected_final'], 90)

    def test_validation(self):
        for value in [-1, 101, 'NaN', 'Infinity', True]:
            with self.subTest(value=value):
                course=demo();course['target']=value
                with self.assertRaises(ValueError): calculate(course)

    def test_invalid_weights(self):
        course=demo();course['categories'][0]['weight']=20
        with self.assertRaises(ValueError):calculate(course)

    def test_duplicate_ids(self):
        course=demo();course['assignments'][1]['id']='homework'
        with self.assertRaises(ValueError):calculate(course)

    def test_extra_credit_pauses(self):
        course=demo();course['assignments'][1]['score']=105
        self.assertEqual(calculate(course)['status'],'needs_review')

    def test_scenario_does_not_mutate_course(self):
        course=demo();saved=copy.deepcopy(course)
        calculate(course,{'project-2':95},'final')
        self.assertEqual(course,saved)

    def test_scenario_cannot_overwrite_verified_grade(self):
        with self.assertRaises(ValueError):calculate(demo(),{'project-1':100},'final')

    def test_solve_requires_other_conditions(self):
        with self.assertRaises(ValueError):calculate(demo(),{},'final')

    def test_scenario_respects_increments(self):
        with self.assertRaises(ValueError):calculate(demo(),{'project-2':95.5},'final')

    def test_grade_missing_value(self):
        course=demo();course['assignments'][1]['score']=None
        self.assertEqual(calculate(course)['status'],'needs_information')

class StateTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.test-data').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT / '.test-data');self.store=Store(self.tmp.name);self.course=demo();self.store.baseline(self.course)
    def tearDown(self):self.tmp.cleanup()

    def test_duplicate_check(self):
        for _ in range(3):self.assertEqual(self.store.check(self.course)['status'],'no_change')
        self.assertEqual(self.store.read()['events'],[])
        self.assertEqual(self.store.read()['notifications'],[])

    def test_new_grade_and_persistence(self):
        self.course['assignments'][2].update(score=84,status='graded')
        result=self.store.check(self.course)
        self.assertEqual(result['changes'][0]['type'],'new_grade')
        self.assertEqual(len(result['state']['notifications']),1)
        self.store.check(self.course)
        self.assertEqual(len(Store(self.tmp.name).read()['notifications']),1)

    def test_revised_grade_and_return_to_old_score(self):
        self.course['positive_notifications']=True
        for score in [92,85,92]:
            self.course['assignments'][1]['score']=score
            self.store.check(self.course)
        events=self.store.read()['events']
        self.assertEqual(len(events),3)
        self.assertEqual(len({e['id'] for e in events}),3)
        self.assertEqual(len(self.store.read()['notifications']),3)

    def test_positive_notifications_off(self):
        self.course['assignments'][1]['score']=92
        self.store.check(self.course)
        self.assertEqual(len(self.store.read()['events']),1)
        self.assertEqual(self.store.read()['notifications'],[])

    def test_partial_read_preserves_assignments(self):
        self.course['assignments']=self.course['assignments'][:1]
        self.course['data_completeness']='partial'
        result=self.store.check(self.course)
        self.assertEqual(len(result['state']['course']['assignments']),4)
        self.assertIsNone(result['calculation']['target_reachable'])

    def test_unavailable_does_not_erase_score(self):
        self.course['assignments'][1].update(score=None,status='hidden')
        result=self.store.check(self.course)
        self.assertEqual(result['status'],'pending_grade')
        self.assertEqual(result['state']['course']['assignments'][1]['score'],85)
        self.assertIsNone(result['calculation']['target_reachable'])

    def test_rule_change_is_not_committed(self):
        before=self.store.read();self.course['categories'][0]['weight']=25;self.course['categories'][1]['weight']=35
        self.assertEqual(self.store.check(self.course)['status'],'needs_review')
        self.assertEqual(before,self.store.read())

    def test_points_change_pauses(self):
        self.course['assignments'][1]['points_possible']=120
        self.assertEqual(self.store.check(self.course)['status'],'needs_review')

    def test_delivery_acknowledgment(self):
        self.course['assignments'][1]['score']=80
        result=self.store.check(self.course)
        notification=result['state']['notifications'][0]
        self.store.acknowledge(notification['id'],'sent')
        self.store.check(self.course)
        self.assertEqual(self.store.read()['notifications'][0]['status'],'sent')

    def test_uncertain_delivery_not_assumed_sent(self):
        self.course['assignments'][1]['score']=80
        result=self.store.check(self.course)
        self.store.acknowledge(result['state']['notifications'][0]['id'],'uncertain')
        self.assertEqual(self.store.read()['notifications'][0]['status'],'uncertain')

    def test_other_course_rejected(self):
        with self.assertRaises(ValueError):self.store.check(demo('points'))

    def test_repeated_baseline_cannot_erase_outbox(self):
        with self.assertRaises(ValueError):self.store.baseline(self.course)

    def test_write_lock(self):
        with self.store.lock():
            with self.assertRaises(ValueError):self.store.check(self.course)

    def test_target_change(self):
        self.store.update_target(93,True)
        self.assertEqual(self.store.read()['course']['target'],93)

    def test_target_label_is_saved(self):
        self.course.update(target=93,target_label='A')
        self.store.check(self.course)
        self.assertEqual(self.store.read()['course']['target_label'],'A')

    def test_explicit_rule_review_preserves_history(self):
        self.course['assignments'][1]['score']=80
        self.store.check(self.course)
        self.course['categories'][0]['weight']=25
        self.course['categories'][1]['weight']=35
        with self.assertRaises(ValueError):self.store.review(self.course,False)
        self.store.review(self.course,True)
        self.assertEqual(len(self.store.read()['events']),1)
        self.assertEqual(len(self.store.read()['notifications']),1)
        self.assertEqual(self.store.check(self.course)['status'],'no_change')

if __name__=='__main__':unittest.main()
