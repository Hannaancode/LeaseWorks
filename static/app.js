'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge = status => `<span class="badge ${esc(status.toLowerCase())}">${esc(status.replaceAll('_',' '))}</span>`;
let selectedUnit = null, unit = null, currentLease = null, reviewTask = null, unmatched = [];
let busy = false;

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let body;
  try { body = await response.json(); } catch { throw new Error('Server returned an unreadable response'); }
  if (!response.ok) {
    const detail = body.detail || body;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return body;
}
function message(text, error = false) {
  $('message').textContent = text; $('message').hidden = false;
  $('message').className = error ? 'error' : '';
}
async function task(action, loading) {
  if (busy) return;
  busy = true; message(loading);
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  try { await action(); $('message').hidden = true; }
  catch (error) { message(error.message, true); }
  finally { busy = false; document.querySelectorAll('button').forEach(b => b.disabled = false); }
}
async function refresh(leaseId = null) {
  const [units, leases] = await Promise.all([api('/api/units'), api('/api/leases')]);
  if (!selectedUnit) selectedUnit = units.find(u => u.unit_id === 'MC-B-1204')?.unit_id || units[0].unit_id;
  $('units').innerHTML = units.map(u => `<button class="unit-nav ${u.unit_id === selectedUnit ? 'active' : ''}" data-unit="${esc(u.unit_id)}">${esc(u.label)}<small><span class="dot ${esc(u.status)}"></span>${esc(u.building)} · ${esc(u.status)}</small></button>`).join('');
  unit = await api(`/api/units/${encodeURIComponent(selectedUnit)}`);
  $('unit-title').textContent = `${unit.label} · ${unit.building}`;
  $('unit-meta').textContent = `${unit.property} / ${unit.type} / ${unit.area_sqm} m² / Parking ${unit.parking_bay}`;
  $('status').textContent = unit.status.toUpperCase();
  unmatched = leases.filter(l => !l.unit_id);
  $('unmatched-section').hidden = !unmatched.length;
  $('unmatched').innerHTML = unmatched.map(l => `<button class="secondary" data-unmatched="${l.id}">${esc(l.filename)}</button>`).join(' ');
  const chosen = leaseId || currentLease?.id;
  currentLease = unit.leases.find(l => l.id === chosen) || unmatched.find(l => l.id === chosen) || unit.leases[0] || null;
  $('stats').innerHTML = [
    [unit.leases.length, 'Lease records'],
    [currentLease?.rules.filter(r => r.status === 'PASS').length ?? '—', 'Policy checks passed / 7'],
    [currentLease ? Object.values(currentLease.fields).filter(f => f.decision === 'pending').length : '—', 'Fields awaiting review'],
    [unit.issues.filter(i => i.work_order.decision !== 'rejected').length, 'Open property reports'],
  ].map(([value, label]) => `<div class="stat"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join('');
  renderLease(); renderIssues();
  if (window.innerWidth <= 700) document.querySelector('.unit-nav.active')?.scrollIntoView({block:'nearest',inline:'center'});
}
function renderLease() {
  const l = currentLease;
  if (!l) { $('lease').innerHTML = '<div class="empty">No lease linked yet. Upload a document or use a sample.</div>'; return; }
  const editable = l.status !== 'active';
  const picker = unit.leases.length > 1 ? `<label class="lease-picker">Lease record<select id="lease-picker">${unit.leases.map(item => `<option value="${item.id}" ${item.id === l.id ? 'selected' : ''}>${esc(item.filename)} · ${esc(item.status)}</option>`).join('')}</select></label>` : '';
  $('lease').innerHTML = picker + `<div class="record-head"><h3>${esc(l.filename)} ${badge(l.status)}</h3><p class="muted">${esc(l.provider)} · Revision ${l.revision} · ${l.unit_id ? esc(l.unit_id) : 'No unit match — correct the unit ID'}<br>Original document SHA-256: ${esc(l.sha256.slice(0,20))}…</p><button class="source-link" data-source="all">Read extracted source</button> · <a href="/api/leases/${l.id}/source">Download original</a></div>` +
  Object.entries(l.fields).map(([name,f]) => `<div class="field"><div><div class="field-name">${esc(name.replaceAll('_',' '))}</div><div class="field-value" dir="auto">${f.value === null ? '<em>Not determined</em>' : esc(f.value)}</div><button class="source-link" data-evidence="${esc(name)}">${f.evidence.length ? `${f.evidence.length} source citation(s)` : 'No source evidence'}</button> ${f.origin === 'human' ? '<small>· owner correction</small>' : ''} ${f.invalid ? badge('unverified') : ''}</div><div class="actions">${badge(f.decision)}${editable ? `<button data-field="${esc(name)}" data-decision="accepted">Accept</button><button class="danger" data-field="${esc(name)}" data-decision="rejected">Reject</button><button class="secondary" data-field="${esc(name)}" data-decision="edit">Edit</button>` : ''}</div></div>`).join('') +
  `<details open><summary>Owner policy checks · ${esc(l.ruleset.ruleset_name)} v${esc(l.ruleset.version)}</summary>${l.rules.map(r => `<div class="rule"><strong>${esc(r.id)} · ${esc(r.description)}</strong> ${badge(r.status)}<small>${esc(r.reason)}</small>${r.evidence.length ? `<button class="source-link" data-rule="${esc(r.id)}">View relied-on clauses</button>` : ''}</div>`).join('')}</details>` +
  `<details ${l.flags.some(f => f.decision === 'pending') ? 'open' : ''}><summary>Review flags · ${l.flags.length}</summary><p class="muted">Accept means the concern is valid and acknowledged. Reject means you dismiss it with a reason. Neither action bypasses a policy failure.</p>${l.flags.map(f => `<div class="flag">${esc(f.message)}<div class="actions">${badge(f.decision)}${editable ? `<button data-flag="${f.id}" data-decision="accepted">Accept flag</button><button class="danger" data-flag="${f.id}" data-decision="rejected">Reject flag</button>` : ''}</div></div>`).join('')}</details>` +
  `<details><summary>Agent workflow</summary><pre>${esc(l.trace.map(s => `${s.step}: ${s.detail}`).join('\n'))}</pre>${l.model_calls?.length ? '<pre>' + esc(JSON.stringify(l.model_calls,null,2)) + '</pre>' : ''}</details>` +
  `<button class="text-btn" data-audit="${l.id}">View audit history</button>${editable ? '<button class="activate" id="activate">Approve lease and mark unit occupied</button><p class="muted">All fields need accepted values and all checks must pass. Every flag must be reviewed. Unit availability is checked again at approval.</p>' : '<p class="notice">Approved lease · Occupancy updated · Original acceptance checks preserved</p>'}`;
}
function renderIssues() {
  $('issues').innerHTML = unit.issues.length ? unit.issues.map(i => `<article class="issue-card"><h3>Report · ${esc(i.unit_id)} ${badge(i.work_order.decision)}</h3><p class="muted">${esc(i.provider)} · Revision ${i.revision}</p><div class="photos">${i.photos.map((p,n) => `<a href="/api/issues/${i.id}/photos/${p.id}" target="_blank" rel="noopener"><img src="/api/issues/${i.id}/photos/${p.id}" alt="Reported property image ${n+1}" loading="lazy"></a>`).join('')}</div>${i.report ? `<p class="muted">Reporter states: ${esc(i.report)}</p>` : ''}${i.observations.map((o,n) => `<div class="observation"><strong>${esc(o.equipment)}</strong> · ${badge(o.condition)}<div>${esc(o.visible_damage)}</div><small>Image ${o.image_indexes.map(n => n+1).join(', ')} · ${esc(o.explanation)}</small>${o.origin === 'human' ? '<small>Owner assessment · ' + esc(o.decision) + '</small>' : ''}<button class="text-btn" data-observation="${i.id}:${n}">Correct assessment</button></div>`).join('')}<div class="work-order"><p class="eyebrow">${i.work_order.decision === 'accepted' ? 'APPROVED' : i.work_order.decision === 'rejected' ? 'REJECTED' : 'DRAFT'} WORK ORDER · ${esc(i.work_order.priority)} PRIORITY</p><h3>${esc(i.work_order.title)}</h3><p>${esc(i.work_order.description)}</p><div class="actions"><button data-work="${i.id}" data-decision="accepted">Review and accept</button><button class="danger" data-work="${i.id}" data-decision="rejected">Reject</button><button class="secondary" data-work="${i.id}" data-decision="edit">Edit draft</button></div></div><p class="limitations">${esc(i.limitations.join(' '))}</p><button class="text-btn" data-audit="${i.id}">View audit history</button></article>`).join('') : '<div class="empty">No property issues for this unit. Upload photos or use the real sample photos.</div>';
}
function showEvidence(evidence, title) {
  $('evidence-body').innerHTML = `<h3>${esc(title)}</h3>` + (evidence.length ? evidence.map(e => `<small>${esc(e.location)} · ${esc(e.segment_id)} · characters ${e.start}–${e.end}</small><blockquote dir="auto">${esc(e.quote)}</blockquote>`).join('') : '<p>No verified source citation. A human correction requires a recorded reason.</p>');
  $('evidence-dialog').showModal();
}
function openReview(type, id, decision) {
  reviewTask = {type,id,decision};
  const edit = decision === 'edit';
  $('review-reason').value = '';
  if (type === 'field') {
    const f = currentLease.fields[id];
    $('review-title').textContent = `${edit ? 'Correct' : decision === 'accepted' ? 'Accept' : 'Reject'} ${id.replaceAll('_',' ')}`;
    $('review-value').innerHTML = edit ? `<label>Corrected value<input type="text" id="corrected-value" value="${esc(f.value)}"></label><p class="muted">Use YYYY-MM-DD for dates, true/false for signatures, a whole number for term months, and decimal amounts without currency. Leave blank for unknown. Your correction is recorded separately from the original AI value.</p>` : `<p>${esc(f.value ?? 'Not determined')}</p>`;
  } else if (type === 'flag') {
    $('review-title').textContent = decision === 'accepted' ? 'Acknowledge flag' : 'Dismiss flag';
    $('review-value').innerHTML = `<p>${esc(currentLease.flags.find(f => f.id === id).message)}</p>`;
  } else if (type === 'observation') {
    const [issueId,index] = id.split(':'); const o = unit.issues.find(i => i.id === issueId).observations[Number(index)];
    $('review-title').textContent = 'Correct photo assessment';
    $('review-value').innerHTML = `<label>Equipment<input id="observation-equipment" type="text" required maxlength="300" value="${esc(o.equipment)}"></label><label>Condition<select id="observation-condition">${['appears_new','worn','damaged','unknown'].map(c => `<option value="${c}" ${c === o.condition ? 'selected' : ''}>${c.replaceAll('_',' ')}</option>`).join('')}</select></label><label>Visible damage<textarea id="observation-damage" required maxlength="2000">${esc(o.visible_damage)}</textarea></label><p class="muted">The original assessment and image citations are preserved. This correction returns the work order to pending review.</p>`;
  } else {
    const i = unit.issues.find(i => i.id === id);
    $('review-title').textContent = decision === 'rejected' ? 'Reject work order' : 'Review work order';
    $('review-value').innerHTML = `<label>Title<input type="text" id="work-title" maxlength="200" required value="${esc(i.work_order.title)}"></label><label>What needs checking or fixing<textarea id="work-description" maxlength="4000" required>${esc(i.work_order.description)}</textarea></label><p class="muted">Correct any condition assessment in the description and explain the change below. Acceptance records owner approval and does not dispatch a contractor.</p>`;
  }
  $('confirm-review').textContent = edit ? 'Save correction and accept' : 'Save decision';
  $('review-dialog').showModal();
}
async function uploadLease(blob, name) {
  const form = new FormData(); form.append('file', blob, name);
  const lease = await api('/api/leases', {method:'POST',body:form});
  if (lease.unit_id) selectedUnit = lease.unit_id;
  currentLease = lease;
  await refresh(lease.id);
}
document.addEventListener('click', event => {
  const b = event.target.closest('button'); if (!b || busy) return;
  if (b.dataset.unit) { selectedUnit = b.dataset.unit; currentLease = null; task(() => refresh(), 'Loading unit…'); }
  if (b.dataset.lease) task(async () => { const response = await fetch('/samples/' + b.dataset.lease); await uploadLease(await response.blob(), b.dataset.lease); }, 'Reading sample and checking owner policy…');
  if (b.dataset.unmatched) task(() => refresh(b.dataset.unmatched), 'Opening unmatched draft…');
  if (b.dataset.field) openReview('field', b.dataset.field, b.dataset.decision);
  if (b.dataset.flag) openReview('flag', b.dataset.flag, b.dataset.decision);
  if (b.dataset.observation) openReview('observation', b.dataset.observation, 'edit');
  if (b.dataset.work) openReview('work', b.dataset.work, b.dataset.decision);
  if (b.dataset.evidence) showEvidence(currentLease.fields[b.dataset.evidence].evidence, b.dataset.evidence.replaceAll('_',' '));
  if (b.dataset.rule) { const r = currentLease.rules.find(r => r.id === b.dataset.rule); showEvidence(r.evidence, r.description); }
  if (b.dataset.source) { $('evidence-body').innerHTML = currentLease.segments.map(s => `<div class="source-segment"><strong>${esc(s.location)} · ${esc(s.id)}</strong><div>${esc(s.text)}</div></div>`).join(''); $('evidence-dialog').showModal(); }
  if (b.dataset.audit) task(async () => { const events = await api('/api/audit/' + b.dataset.audit); $('evidence-body').innerHTML = `<pre>${esc(JSON.stringify(events,null,2))}</pre>`; $('evidence-dialog').showModal(); }, 'Loading audit history…');
});
document.addEventListener('change', event => { if (event.target.id === 'lease-picker') task(() => refresh(event.target.value), 'Opening lease…'); });
$('lease-upload').addEventListener('submit', event => { event.preventDefault(); const f = $('lease-file').files[0]; if (f) task(() => uploadLease(f, f.name), 'Reading document and checking owner policy…'); });
$('issue-upload').addEventListener('submit', event => { event.preventDefault(); task(async () => { const form = new FormData(); for (const f of $('photos').files) form.append('photos',f); form.append('report',$('report').value); await api(`/api/units/${selectedUnit}/issues`,{method:'POST',body:form}); await refresh(); }, 'Inspecting images and drafting work order…'); });
$('all-photo-issue').addEventListener('click', () => task(async () => { const form = new FormData(); for (const name of ['photo_wall_ac.jpg','photo_corrosion.jpg','photo_water_heater.jpg','photo_faucet.jpg']) { const r = await fetch('/samples/' + name); if (!r.ok) throw new Error('Sample photograph unavailable'); form.append('photos',await r.blob(),name); } form.append('report','Inspect four separate public equipment photographs; these are not photos of this unit.'); await api(`/api/units/${selectedUnit}/issues`,{method:'POST',body:form}); await refresh(); }, 'Assessing four real equipment photographs…'));
$('real-photo-issue').addEventListener('click', () => task(async () => { const form = new FormData(); for (const name of ['photo_wall_ac.jpg','photo_corrosion.jpg']) { const r = await fetch('/samples/' + name); form.append('photos',await r.blob(),name); } form.append('report','Public-photo evaluation: inspect the visible air conditioning equipment and coil.'); await api(`/api/units/${selectedUnit}/issues`,{method:'POST',body:form}); await refresh(); }, 'Assessing actual equipment photographs…'));
$('review-form').addEventListener('submit', event => {
  event.preventDefault();
  const t = reviewTask;
  task(async () => {
    let path, body = {decision:t.decision === 'edit' ? 'accepted' : t.decision,reason:$('review-reason').value};
    if (t.type === 'field') {
      path = `/api/leases/${currentLease.id}/fields/${t.id}/review`; body.expected_revision = currentLease.revision;
      if (t.decision === 'edit') {
        let value = $('corrected-value').value.trim();
        if (!value) value = null;
        else if (['landlord_signed','tenant_signed','escalation_defined'].includes(t.id)) {
          if (!['true','false'].includes(value)) throw new Error('Use true or false for this field');
          value = value === 'true';
        } else if (t.id === 'term_months') { if (!/^\d+$/.test(value)) throw new Error('Use a positive whole number'); value = Number(value); }
        body.value = value; body.replace_value = true;
      }
    } else if (t.type === 'flag') { path = `/api/leases/${currentLease.id}/flags/${t.id}/review`; body.expected_revision = currentLease.revision; }
    else if (t.type === 'observation') { const [issueId,index] = t.id.split(':'); const i = unit.issues.find(i => i.id === issueId); path = `/api/issues/${issueId}/observations/${index}/review`; body.expected_revision = i.revision; body.equipment = $('observation-equipment').value; body.condition = $('observation-condition').value; body.visible_damage = $('observation-damage').value; }
    else { const i = unit.issues.find(i => i.id === t.id); path = `/api/issues/${t.id}/review`; body.expected_revision = i.revision; body.title = $('work-title').value; body.description = $('work-description').value; }
    const result = await api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if (t.type === 'field' && result.unit_id) selectedUnit = result.unit_id;
    $('review-dialog').close(); await refresh(['work','observation'].includes(t.type) ? null : result.id);
  }, 'Recording owner decision…');
});
document.addEventListener('click', event => { if (event.target.id === 'activate') task(async () => { const l = await api(`/api/leases/${currentLease.id}/activate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:currentLease.revision})}); await refresh(l.id); }, 'Checking approval requirements and current availability…'); });
$('cancel-review').addEventListener('click',() => $('review-dialog').close());
$('close-evidence').addEventListener('click',() => $('evidence-dialog').close());
$('export').addEventListener('click',() => task(async () => { const record = await api(`/api/units/${selectedUnit}/export`); const url = URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'})); const a = document.createElement('a'); a.href = url; a.download = selectedUnit + '-record.json'; a.click(); URL.revokeObjectURL(url); }, 'Exporting unit record…'));
task(async () => { const health = await api('/api/health'); const live = !health.provider.startsWith('demo'); $('prose-lease').hidden = !live; $('provider').textContent = health.provider.startsWith('demo') ? 'OFFLINE DEMO · No API key needed. Lease extraction uses sample labels. The four real sample photographs use fixed reference assessments offline; other images stay unknown. Enable live mode for AI inference.' : 'LIVE AI · Text and image inference enabled. Every proposal still needs owner review.'; await refresh(); }, 'Loading workspace…');
