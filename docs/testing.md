# GradePath: run and test demo2

Run the following commands in PowerShell. Python 3.10 or newer is required.
There are no Python packages to install and no npm install/build step.

## 1. Open the repository

```powershell
Set-Location 'C:\Vriddhi Work\DevHacks26\DevHacks-26'
git branch --show-current
python --version
```

The branch should be `demo2`. If `python` is unavailable but the Windows Python
launcher is installed, use `py -3` instead of `python` in the commands below.

## 2. Run all automated tests

```powershell
python -m unittest discover -s tests -v
```

Expected: **42 tests**, ending with **OK**. These cover points/weighted arithmetic,
what-if calculations, score rounding, incomplete/hidden grades, unsupported rules,
state persistence, revisions, duplicate protection, and notification acknowledgment.
Tests use isolated directories under the ignored `.test-data/` directory.

Optional syntax checks (the JavaScript check requires Node.js):

```powershell
python -m py_compile app.py gradepath/scripts/calculate.py gradepath/scripts/state.py
node --check web/app.js
```

## 3. Start a fresh local demo

```powershell
$demoData = Join-Path '.test-data' ('browser-' + [guid]::NewGuid().ToString('N'))
python app.py --port 8767 --data-dir "$demoData"
```

Keep that terminal running and open **http://127.0.0.1:8767/** in a browser.
Stop the server with **Ctrl+C** in its terminal. If the port is occupied, choose
another port and open the corresponding URL.

Port 8767 avoids the preview already running on 8766. A unique data directory
starts a clean example without changing saved work in `.gradepath-data/`.
To reopen the same test data later in that PowerShell session, rerun the same
`python app.py --port 8767 --data-dir "$demoData"` command without regenerating
`$demoData`.

For ordinary use with persistent default data:

```powershell
python app.py --port 8767
```

## 4. Check the browser flows

1. **Initial weighted example:** Software Engineering should show current graded
   average **87.5%**, target **90%**, required remaining **91.36%**, and maximum
   **94.75%**. Current average is normalized over categories with graded work.
2. **What-if:** with Project 2 at **95%**, the final needs **90/100**. Move the
   slider to **100%**; the final needs **89/100** after whole-point rounding.
3. **Target:** edit the target to **93%**, label **A**. Set Project 2 back to **95%**.
   The final should need **98/100** (raw requirement is 97.5). Reload and verify
   the target and label persist. Hypothetical slider positions reset on reload.
4. **Grade revision:** restore target **90%**. Edit Project 1 from **85** to **80**.
   Current average becomes **85%**, required remaining **92.73%**, and maximum
   **94%**. With Project 2 at **95%**, the final needs **92/100**. Recent Changes
   should show **85 → 80**. Reload and verify the saved grade remains.
5. **Duplicate:** save Project 1 at **80** again. No second event should appear.
6. **Points model:** choose **Switch example → Psychology · Points based → Switch
   course**. It should show **90%** current, target **92%**, and **100%** required.
   Change target to **93%**: required becomes **105%**, maximum stays **92%**, and
   the target is marked above the known maximum.
7. **Import/export:** export the course JSON. Import it unchanged through the file
   picker or paste box. Calculations should stay the same. The workspace becomes
   labeled **Imported course · local**. Invalid JSON should show an error.
8. **Unknown future work:** add an ungraded assignment. Completeness becomes partial
   and projections are conditional; the app must not claim an exact final maximum.
9. **Connection explanation:** open **Connect with Cubbie**. It explains the real
   installation/connection flow; it must not claim Canvas is already connected.
10. **Layout:** resize the browser to phone width and check that the cards stack,
    dialogs fit, and the coursework table scrolls. Try keyboard Tab navigation.

The app records local events but does not send iMessages or sync Canvas.

## 5. Test the calculator directly

From the repository root:

```powershell
python gradepath/scripts/calculate.py tests/fixtures/points.json
python gradepath/scripts/calculate.py tests/fixtures/weighted.json
```

Points expected: required_remaining_points=200, required_remaining_average=100,
target_reachable=true, maximum_known_possible_grade=92.
Weighted expected: current_graded_average=87.5, required_remaining_average about
91.363636, maximum_known_possible_grade=94.75.

For the weighted what-if example:

```powershell
python -c "import json; from pathlib import Path; c=json.loads(Path('tests/fixtures/weighted.json').read_text(encoding='utf-8')); print(json.dumps({'course':c,'scenario':{'project-2':95},'solve_for':'final'}))" | python gradepath/scripts/calculate.py
```

Expected `solved.required_points` and `solved.achievable_points`: **90**.

## 6. Test persistent state and a duplicate snapshot

Use a new directory for each baseline test, keeping your browser data separate:

```powershell
$stateData = Join-Path '.test-data' ('state-' + [guid]::NewGuid().ToString('N'))
python gradepath/scripts/state.py baseline --input tests/fixtures/weighted.json --data-dir "$stateData"
python gradepath/scripts/state.py check --input tests/fixtures/weighted.json --data-dir "$stateData"
python gradepath/scripts/state.py check --input tests/fixtures/weighted.json --data-dir "$stateData"
python gradepath/scripts/state.py read --data-dir "$stateData"
```

Expected: baseline_ready, then no_change twice. The saved events and notifications
arrays remain empty. The automated tests additionally cover real score changes,
reversions, pending deliveries, and acknowledged deliveries.

## 7. Test on Cubbie after publishing

1. Commit and push `demo2` to a public GitHub repository.
2. Send Cubbie the actual public folder link:
   `https://github.com/YOUR_OWNER/YOUR_REPO/tree/demo2/gradepath`.
   Replace the owner/repository placeholders. Ask it to install GradePath from that
   branch. The packaged alternative is `dist/gradepath.zip` when hosted at a public
   download URL.
3. Connect Canvas through Cubbie's flow using your school's Canvas URL. The
   connected account works independently of login in your own browser.
4. In a new message, ask Cubbie to track one course and a target from its syllabus.
5. Verify actual scores, point maxima, weights, rules, and future-work completeness.
6. Agree to a daily check time and timezone. Confirm Cubbie creates the schedule.
7. Verify a later run detects a real released/revised grade, recalculates, and sends
   one useful update. An unchanged repeat must not send a duplicate notification.
8. Ask a what-if question and compare its result with the deterministic calculator.
9. Ask to stop monitoring and verify the schedule is canceled.

These are live integration tests. Local test success does not establish that the
Skill has installed, that Canvas fields are available, or that Cubbie sent a message.

## 8. Review and commit when ready

The implementation and this guide are staged on `demo2`; no commit was made.

```powershell
git status
git diff --cached --stat
git diff --cached
git commit -m "Add GradePath demo app and Cubbie skill"
git push -u origin demo2
```

If you edit files before committing, stage the edits again with `git add`.
The ignored local data, logs, and Python caches are not included.
