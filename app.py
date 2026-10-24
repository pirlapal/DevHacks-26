"""Local GradePath companion. Run: python app.py"""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'gradepath/scripts'))
from calculate import calculate, validate
from state import Store

def demo(model='weighted'):
    if model == 'points':
        return {'course_key': 'demo-points', 'course_name': 'Introduction to Psychology', 'course_code': 'PSY 101', 'model': 'points', 'target': 92, 'target_label': 'Custom', 'rule_source': 'Demo syllabus · 1,000 total course points', 'rules_status': 'confirmed', 'data_completeness': 'complete', 'unsupported_rules': [], 'positive_notifications': False, 'source': 'demo', 'categories': [{'id': 'all', 'name': 'Coursework', 'weight': 100}], 'assignments': [{'id': 'completed', 'name': 'Completed coursework', 'category': 'all', 'points_possible': 800, 'score': 720, 'status': 'graded'}, {'id': 'final', 'name': 'Final exam', 'category': 'all', 'points_possible': 200, 'score': None, 'status': 'not_due', 'increment': 1}]}
    return {'course_key': 'demo-software-engineering', 'course_name': 'Software Engineering', 'course_code': 'CSE 340', 'model': 'weighted', 'target': 90, 'target_label': 'A−', 'rule_source': 'Demo syllabus · Grading policy, page 3', 'rules_status': 'confirmed', 'data_completeness': 'complete', 'unsupported_rules': [], 'positive_notifications': False, 'source': 'demo', 'categories': [{'id': 'homework', 'name': 'Homework', 'weight': 30}, {'id': 'projects', 'name': 'Projects', 'weight': 30}, {'id': 'final', 'name': 'Final exam', 'weight': 40}], 'assignments': [{'id': 'homework', 'name': 'Homework 1–6', 'category': 'homework', 'points_possible': 300, 'score': 270, 'status': 'graded'}, {'id': 'project-1', 'name': 'Project 1', 'category': 'projects', 'points_possible': 100, 'score': 85, 'status': 'graded'}, {'id': 'project-2', 'name': 'Project 2', 'category': 'projects', 'points_possible': 100, 'score': None, 'status': 'not_due', 'increment': 1}, {'id': 'final', 'name': 'Final exam', 'category': 'final', 'points_possible': 100, 'score': None, 'status': 'not_due', 'increment': 1}]}

class Handler(BaseHTTPRequestHandler):
    store = None

    def log_message(self, *args):
        pass

    def send(self, status, data, mime='application/json'):
        body = json.dumps(data, allow_nan=False).encode() if mime == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        expected = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        return host in expected and (not origin or origin in {'http://' + h for h in expected})

    def do_GET(self):
        if not self.allowed():
            return self.send(403, {'error': 'Local requests only.'})
        path = urlparse(self.path).path
        try:
            if path == '/api/state':
                state = self.store.read()
                course = state['course']
                return self.send(200, {'state': state, 'calculation': calculate(course) if course else None})
            if path == '/api/demo':
                return self.send(200, demo('points' if 'points' in self.path else 'weighted'))
            files = {'/': ('web/index.html', 'text/html; charset=utf-8'), '/style.css': ('web/style.css', 'text/css'), '/app.js': ('web/app.js', 'text/javascript'), '/schema.json': ('gradepath/references/course.schema.json', 'application/schema+json')}
            if path not in files:
                return self.send(404, {'error': 'Not found.'})
            file, mime = files[path]
            return self.send(200, (ROOT / file).read_bytes(), mime)
        except (OSError, ValueError) as exc:
            self.send(500, {'error': str(exc)})

    def do_POST(self):
        if not self.allowed() or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send(403, {'error': 'Local JSON requests only.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 1000000:
                return self.send(413, {'error': 'Use a JSON file smaller than 1 MB.'})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('Request must be an object.')
            path = urlparse(self.path).path
            if path == '/api/calculate':
                result = calculate(payload['course'], payload.get('scenario'), payload.get('solve_for'))
            elif path == '/api/baseline':
                result = self.store.baseline(payload['course'])
            elif path == '/api/check':
                result = self.store.check(payload['course'])
            elif path == '/api/target':
                state = self.store.update_target(payload['target'], payload.get('positive_notifications', False))
                result = {'state': state, 'calculation': calculate(state['course'])}
            elif path == '/api/review':
                result = self.store.review(payload['course'], payload.get('confirm') is True)
            elif path == '/api/reset':
                if payload.get('confirm') != 'reset-local-course':
                    raise ValueError('Explicit reset confirmation required.')
                with self.store.lock():
                    previous = self.store.read()
                    archive = self.store.directory / 'previous-state.json'
                    archive.write_text(json.dumps(previous, indent=2), encoding='utf-8')
                    self.store.write({'version': 1, 'course': None, 'revision': 0, 'events': [], 'notifications': [], 'last_successful_check': None})
                result = {'status': 'reset'}
            else:
                return self.send(404, {'error': 'Not found.'})
            self.send(200, result)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.send(400, {'error': str(exc)})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', default=str(ROOT / '.gradepath-data'))
    args = parser.parse_args()
    Handler.store = Store(args.data_dir)
    server = HTTPServer(('127.0.0.1', args.port), Handler)
    print(f'GradePath is ready at http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
