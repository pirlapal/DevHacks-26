'use strict';
const $ = (id) => document.getElementById(id);
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n) => n == null ? '—' : Number(n).toLocaleString(undefined, {maximumFractionDigits: 2});
const pct = (n) => n == null ? '—' : `${fmt(n)}%`;
let state, course, result, scenario = {}, solveFor = null, sequence = 0, toastTimer;
async function api(path, payload) {
  const response = await fetch(`/api/${path}`, payload === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}
function toast(message) { $('toast').textContent = message; $('toast').classList.remove('hidden'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').classList.add('hidden'), 4000); }
function error(message) { $('error').textContent = message; $('error').classList.remove('hidden'); }
function modal(html) { $('modal-content').innerHTML = html; $('modal').showModal(); }
function dialogError(message) { let el = $('modal-error'); if (!el) {el=document.createElement('p');el.id='modal-error';el.className='modal-error';el.setAttribute('role','alert');$('modal-content').append(el);} el.textContent=message; }
function run(handler) {return async (...args) => {try {await handler(...args);} catch(e) {if ($('modal').open) dialogError(e.message); else error(e.message);}};}
$('close-modal').onclick = () => $('modal').close();
$('modal').addEventListener('click', e => { if(e.target === $('modal')) {const r=$('modal').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('modal').close();}});

async function load() {
  const data = await api('state');
  if (!data.state.course) {const sample=await api('demo');await api('baseline',{course:sample}); return load();}
  state = data.state; course=state.course; result=data.calculation;
  $('error').classList.add('hidden'); render();
}
function render() {
  const isDemo=course.source==='demo';
  $('mode-pill').innerHTML=`<span></span>${isDemo?'Demo workspace':'Imported course · local'}`;
  $('course-code').textContent=course.course_code || (course.model==='points'?'POINTS BASED':'WEIGHTED CATEGORIES');
  $('course-name').textContent=course.course_name;
  $('data-note').textContent=isDemo?'Example data, real calculations. Your Canvas account isn’t connected to this local app.':'Imported snapshot stored on this computer. Cubbie’s Canvas connection runs separately; this page does not sync automatically.';
  $('current').innerHTML=result.current_graded_average==null?'—':`${fmt(result.current_graded_average)}<span>%</span>`;
  $('current-caption').textContent=course.model==='weighted'?'Normalized across categories with graded work':`${fmt(result.earned_points)} of ${fmt(result.graded_points)} graded points`;
  $('target-display').innerHTML=`${fmt(course.target)}<span>%</span>`;
  $('target-caption').textContent=`${course.target_label||'Custom'} target · edit anytime`;
  $('required').innerHTML=result.required_remaining_average==null?(result.target_already_secured?'Done!':'—'):`${fmt(result.required_remaining_average)}<span>%</span>`;
  $('required-caption').textContent=course.model==='weighted'?'If you earn the same % on all remaining work':'Average needed across remaining points';
  const reachable=result.target_reachable??result.conditional_target_reachable;
  $('trajectory-title').textContent=result.status!=='success'?'Let’s fill in the missing pieces.':result.target_already_secured?'Your target is already secured.':reachable?'Your goal is within reach.':'Let’s rethink the finish line.';
  $('reachable-badge').textContent=result.status!=='success'?'More information needed':result.conditional?'Conditional on known coursework':reachable?'Possible under known rules':'Above the known maximum';
  $('reachable-badge').className=`badge ${reachable&&!result.conditional?'green':'amber'}`;
  $('secured-label').textContent=pct(result.secured_contribution);
  const maximum=result.maximum_known_possible_grade??result.conditional_maximum;
  $('maximum-label').textContent=pct(maximum);
  $('track-secured').style.width=`${Math.min(100,result.secured_contribution||0)}%`;
  $('track-possible').style.left=`${Math.min(100,result.secured_contribution||0)}%`;
  $('track-possible').style.width=`${Math.max(0,Math.min(100,maximum||0)-(result.secured_contribution||0))}%`;
  $('target-marker').style.left=`${course.target}%`;
  $('trajectory-caption').textContent=result.status!=='success'?'Projection paused until the grading model can be verified.':result.conditional?'Conditional estimate from currently known coursework. Future assignments may change this path.':'Secured contribution uses the complete final denominator. This is a GradePath estimate, not an official Canvas total.';
  $('warnings').classList.toggle('hidden',!result.warnings.length);$('warnings').textContent=result.warnings.join(' ');
  $('model-caption').textContent=course.model==='weighted'?'Category averages × their final grade weights.':'Every point counts equally toward your final grade.';
  $('category-list').innerHTML=result.categories.map(c=>`<div class="category"><div class="category-header"><div><span class="color-dot"></span>${escapeHTML(c.name)}</div><span>${course.model==='weighted'?pct(c.weight):`${fmt(c.graded+c.remaining)} pts`}</span></div><div class="category-track"><div data-average="${Math.min(100,c.average||0)}"></div></div><div class="category-caption"><span>${c.average==null?'No graded work yet':`${fmt(c.earned)} / ${fmt(c.graded)} graded pts`}</span><span>${c.remaining?`${fmt(c.remaining)} pts remaining`:'Complete'}</span></div></div>`).join('');
  document.querySelectorAll('[data-average]').forEach(bar=>bar.style.width=`${bar.dataset.average}%`);
  $('rule-status').textContent=['confirmed','student_confirmed'].includes(course.rules_status)?'Rules confirmed':'Rules need review';$('source-label').textContent=course.rule_source;
  $('assignment-rows').innerHTML=course.assignments.map((a,i)=>`<tr><td>${escapeHTML(a.name)}</td><td>${escapeHTML(course.categories.find(c=>c.id===a.category)?.name)}</td><td><span class="status ${a.score!=null?'graded':''}">${escapeHTML(a.status.replace('_',' '))}</span></td><td>${a.score==null?'—':fmt(a.score)} <span class="muted">/ ${fmt(a.points_possible)}</span></td><td><button class="text-button edit-score" data-index="${i}" aria-label="Edit ${escapeHTML(a.name)}">Edit ↗</button></td></tr>`).join('');
  document.querySelectorAll('.edit-score').forEach(b=>b.onclick=()=>editAssignment(Number(b.dataset.index)));
  const events=state.events.slice(-3).reverse();
  $('activity-list').innerHTML=events.length?events.map(e=>`<div class="activity"><span>↗</span><div><h4>${escapeHTML(e.name)} ${e.before==null?'was graded':'was updated'}</h4><p>${e.before==null?'Ungraded':fmt(e.before)} → ${fmt(e.after)} / ${fmt(e.points_possible)} · ${new Date(e.observed_at).toLocaleDateString()}</p><p>Saved locally · no message sent</p></div></div>`).join(''):'<div class="activity-empty">A fresh start. When you record or import a new grade, its change will appear here.<br>No refresh spiral necessary.</div>';
  $('positive-toggle').checked=!!course.positive_notifications;
  renderScenario();
}
function remaining() { return course.assignments.filter(a=>a.score==null&&['ungraded','submitted','not_due','missing','late'].includes(a.status)&&a.points_possible>0); }
function renderScenario() {
  const items=remaining();
  if(!items.some(a=>a.id===solveFor))solveFor=items.at(-1)?.id||null;
  const others=items.filter(a=>a.id!==solveFor);
  scenario=Object.fromEntries(others.map(a=>[a.id,scenario[a.id]??95]));
  if(!items.length){$('scenario-inputs').innerHTML='<p class="empty-message">There’s no visible ungraded work to explore yet.</p>'; $('scenario-result').textContent=result.projected_final==null?'No reliable projection yet.':`Final grade: ${pct(result.projected_final)}`;$('scenario-detail').textContent='Add remaining coursework to explore a scenario.';return;}
  $('scenario-inputs').innerHTML=`<label class="solve-label" for="solve-select">What would you like to solve for?</label><select id="solve-select" class="solve-select">${items.map(a=>`<option value="${escapeHTML(a.id)}" ${a.id===solveFor?'selected':''}>${escapeHTML(a.name)}</option>`).join('')}</select>${others.map((a,i)=>`<div class="scenario-input"><label for="scenario-${i}">If I get this on ${escapeHTML(a.name)}<span class="score-value" id="value-${i}">${pct(scenario[a.id])}</span></label><input id="scenario-${i}" data-id="${escapeHTML(a.id)}" type="range" min="0" max="100" step="${a.increment?a.increment/a.points_possible*100:1}" value="${scenario[a.id]}" aria-label="Hypothetical score on ${escapeHTML(a.name)}"><div class="range-labels"><span>0%</span><span>100%</span></div></div>`).join('')}`;
  $('solve-select').onchange=e=>{solveFor=e.target.value;renderScenario();};
  document.querySelectorAll('#scenario-inputs input').forEach((input,i)=>input.oninput=()=>{scenario[input.dataset.id]=Number(input.value);$(`value-${i}`).textContent=pct(Number(input.value));updateScenario();});
  updateScenario();
}
async function updateScenario() {
  const request=++sequence;
  try {
    const calculation=await api('calculate',{course,scenario,solve_for:solveFor});
    if(request!==sequence)return;
    const solved=calculation.solved;
    if(!solved){$('scenario-result').textContent='We need a little more information.';$('scenario-detail').textContent=calculation.warnings.join(' ');return;}
    const name=course.assignments.find(a=>a.id===solveFor).name;
    $('scenario-result').textContent=solved.reachable?`You’d need ${pct(solved.required_percentage)} on ${name}.`:`This path needs more than 100% on ${name}.`;
    $('scenario-detail').textContent=`${fmt(solved.achievable_points)} / ${fmt(solved.points_possible)} points to reach ${pct(course.target)} overall.${solved.rounding_applied?' Rounded up to an achievable score.':''}${calculation.conditional?' Conditional on currently known coursework.':''}`;
    $('answer-label').textContent=calculation.conditional?'CONDITIONAL EXAMPLE PATH':'ONE POSSIBLE PATH';
  } catch(e){if(request===sequence){$('scenario-result').textContent='This scenario needs review.';$('scenario-detail').textContent=e.message;}}
}
function connectionDialog() {
  modal(`<span class="eyebrow">YOUR COURSE, WITH CUBBIE</span><h2>Connect once.<br><span class="handwritten blue">Keep moving.</span></h2><p>Send Cubbie your school’s Canvas link and complete its connection flow. Cubbie owns that connection, so signing out of your own browser doesn’t end it.</p><ol><li>Connect Canvas in your existing Cubbie conversation.</li><li>Install the GradePath Skill from your published repository link.</li><li>Ask Cubbie to track a course and confirm your target.</li><li>Choose a check-in schedule when Cubbie asks.</li></ol><div class="dialog-note">This local app does not connect to Canvas or schedule messages. It uses imported or demo data. The Cubbie Skill runs separately with your connected account.</div><div class="code-box" id="setup-prompt">Track my Software Engineering course with GradePath. Help me finish at my syllabus’s A threshold. Verify the grading rules, explain my baseline, then ask me about a daily check-in.</div><button class="button primary" id="copy-prompt">Copy setup message</button> <a class="text-button" href="https://cubbie.ai/" target="_blank" rel="noopener noreferrer">Open Cubbie ↗</a>`);
  $('copy-prompt').onclick=run(async()=>{await navigator.clipboard.writeText($('setup-prompt').textContent);toast('Setup message copied.');});
}
$('connect-button').onclick=connectionDialog;$('setup-button').onclick=connectionDialog;
$('target-button').onclick=()=>{modal(`<span class="eyebrow">MAKE IT YOURS</span><h2>Choose your finish line.</h2><p>Use the threshold from your syllabus. An A is not always 90%.</p><form id="target-form"><label for="target-label">Grade label</label><input id="target-label" maxlength="30" value="${escapeHTML(course.target_label||'Custom')}"><label for="target-number">Minimum final percentage</label><input id="target-number" type="number" min="0" max="100" step="0.01" required value="${course.target}"><button class="button primary">Save my target ↗</button></form>`);$('target-form').onsubmit=run(async e=>{e.preventDefault();const updated=structuredClone(course);updated.target=Number($('target-number').value);updated.target_label=$('target-label').value;await saveCourse(updated);$('modal').close();toast('Your path has been recalculated.');});};
async function saveCourse(updated){const response=await api('check',{course:updated});if(response.status==='needs_review')throw new Error(response.error||'Rules need review.');await load();return response;}
$('positive-toggle').onchange=run(async()=>{await api('target',{target:course.target,positive_notifications:$('positive-toggle').checked});await load();toast('Notification preference saved locally.');});
$('rules-button').onclick=()=>{modal(`<span class="eyebrow">SHOW YOUR WORK</span><h2>The rules behind the numbers.</h2><p><strong>${escapeHTML(course.model==='weighted'?'Weighted categories':'Points-based grading')}</strong> · ${escapeHTML(course.rules_status.replace('_',' '))}</p><p>${escapeHTML(course.rule_source)}</p><ul>${course.categories.map(c=>`<li>${escapeHTML(c.name)}: ${course.model==='weighted'?pct(c.weight):'points based'}</li>`).join('')}</ul><div class="dialog-note">${escapeHTML(result.requirement_label)}. ${course.model==='weighted'?'Today’s category average is not permanently earned. Future points change the final category average.':'Required future points = target × total course points − points earned.'}</div><p>Completeness: <strong>${escapeHTML(course.data_completeness)}</strong>. Unsupported rules: ${escapeHTML(course.unsupported_rules?.join(', ')||'none recorded')}.</p><p>Target: ${pct(course.target)}. Source: ${escapeHTML(course.rule_source)}. No hidden scores are inferred.</p>`);};
function editAssignment(index) {
  const a=course.assignments[index];
  modal(`<span class="eyebrow">${course.source==='demo'?'TRY A GRADE CHANGE':'UPDATE YOUR SNAPSHOT'}</span><h2>${escapeHTML(a.name)}</h2><p>Record a verified score, or leave it empty if it hasn’t been graded. Changes are stored locally.</p><form id="score-form"><div class="form-row"><div><label for="score">Points earned</label><input id="score" type="number" min="0" max="${a.points_possible??''}" step="${a.increment||'any'}" value="${a.score??''}"></div><div><label>Points possible</label><input value="${a.points_possible??'Unknown'}" disabled></div></div><label for="score-status">Assignment status</label><select id="score-status">${['graded','ungraded','submitted','not_due','missing','late','hidden','unavailable','excused'].map(s=>`<option value="${s}" ${s===a.status?'selected':''}>${s.replace('_',' ')}</option>`).join('')}</select><button class="button primary">Save & recalculate ↗</button></form>`);
  $('score').oninput=()=>{if($('score').value!=='')$('score-status').value='graded';else $('score-status').value='ungraded';};
  $('score-form').onsubmit=run(async e=>{e.preventDefault();const updated=structuredClone(course);updated.assignments[index].score=$('score').value===''?null:Number($('score').value);updated.assignments[index].status=$('score-status').value;const response=await saveCourse(updated);$('modal').close();toast(response.status==='no_change'?'No change. No duplicate event created.':response.status==='pending_grade'?'Score unavailable. Last verified score retained.':'Grade saved. Your path is up to date.');});
}
$('add-button').onclick=()=>{modal(`<span class="eyebrow">A NEW PIECE OF THE PICTURE</span><h2>Add coursework.</h2><form id="add-form"><label for="assignment-name">Assignment name</label><input id="assignment-name" required maxlength="100"><label for="assignment-category">Category</label><select id="assignment-category">${course.categories.map(c=>`<option value="${escapeHTML(c.id)}">${escapeHTML(c.name)}</option>`).join('')}</select><label for="assignment-points">Points possible</label><input id="assignment-points" type="number" min="0.01" step="any" required><p class="small-print">New work changes the denominator. Completeness becomes partial until the full course plan is verified.</p><button class="button primary">Add to my course ＋</button></form>`);$('add-form').onsubmit=run(async e=>{e.preventDefault();const updated=structuredClone(course);updated.data_completeness='partial';updated.assignments.push({id:crypto.randomUUID(),name:$('assignment-name').value.trim(),category:$('assignment-category').value,points_possible:Number($('assignment-points').value),score:null,status:'not_due'});await saveCourse(updated);$('modal').close();toast('Coursework added. Projections are now conditional.');});};
$('export-button').onclick=()=>{const blob=new Blob([JSON.stringify(course,null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='gradepath-course.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);toast('Course snapshot exported.');};
$('import-button').onclick=()=>{modal(`<span class="eyebrow">BRING YOUR OWN COURSE</span><h2>A clearer picture starts here.</h2><p>Import a GradePath course JSON file. Export the example to see the format, or use the <a href="/schema.json" target="_blank">course schema ↗</a>. Don’t include passwords or access tokens.</p><label for="import-file">Choose a JSON file</label><input id="import-file" type="file" accept=".json,application/json"><label for="import-json">Or paste course JSON</label><textarea id="import-json" placeholder="Paste the course object here" spellcheck="false"></textarea><div class="dialog-note">A snapshot with the same course ID updates the current course. A different course replaces it after confirmation; the previous state is archived locally.</div><button class="button primary" id="import-submit">Validate & import ↗</button>`);$('import-file').onchange=run(async e=>{const f=e.target.files[0];if(!f)return;if(f.size>1000000)throw new Error('Choose a file smaller than 1 MB.');$('import-json').value=await f.text();});$('import-submit').onclick=run(async()=>{const parsed=JSON.parse($('import-json').value);await api('calculate',{course:parsed});parsed.source='imported';if(parsed.course_key===course.course_key){await saveCourse(parsed);$('modal').close();toast('Snapshot imported and checked.');}else{confirmReplacement(parsed);}});};
function confirmReplacement(next) { $('modal').close();modal(`<span class="eyebrow">ONE COURSE AT A TIME</span><h2>Switch your tracked course?</h2><p>Replace <strong>${escapeHTML(course.course_name)}</strong> with <strong>${escapeHTML(next.course_name)}</strong>? Your existing state will be saved as a local archive.</p><button class="button primary" id="replace-confirm">Switch course</button> <button class="text-button" id="cancel-replace">Keep my course</button>`);$('cancel-replace').onclick=()=>$('modal').close();$('replace-confirm').onclick=run(async()=>{await api('reset',{confirm:'reset-local-course'});await api('baseline',{course:next});scenario={};solveFor=null;await load();$('modal').close();toast('Your course is ready.');}); }
$('demo-menu').onclick=()=>{modal(`<span class="eyebrow">REAL MATH, EXAMPLE COURSES</span><h2>Pick a starting point.</h2><p>Explore the two grading models. Switching archives your current local course.</p><button class="button outline" id="weighted-demo">Software Engineering · Weighted</button><button class="button outline" id="points-demo">Psychology · Points based</button>`);$('weighted-demo').onclick=run(async()=>confirmReplacement(await api('demo')));$('points-demo').onclick=run(async()=>confirmReplacement(await api('demo?model=points')));};
load().catch(e=>error(`Couldn’t load GradePath: ${e.message}`));
