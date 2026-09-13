const V = window.FlowerView;
const content = document.querySelector('#content');
const errorBox = document.querySelector('#error');
let token = '', plantId = '', state = null, range = '7d', source = null, refreshTimer, currentPhoto = '';
const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = value => value ? new Date(value).toLocaleString('zh-CN', {hour12: false}) : '--';
const route = () => location.hash.slice(1) || 'home';
const key = () => crypto.randomUUID();
function error(message) { errorBox.textContent = message || ''; errorBox.hidden = !message; }
async function api(path, method = 'GET', data, headers = {}) {
  const response = await fetch('/api/v1' + path, {method, headers: {'Content-Type':'application/json', Authorization:'Bearer ' + token, ...headers}, body: data === undefined ? undefined : JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(V.faultLabel(result.error && result.error.code));
  return result;
}
async function initialize() {
  try {
    const result = await api('/auth/wechat-login', 'POST', {code:'mock-demo'});
    token = result.access_token;
    await render();
    refreshTimer = setInterval(async () => {
      try {
        if (route() === 'home' && !document.querySelector('dialog[open]')) await render(true);
        else if (route() === 'care') {
          await loadState();
          const panel = document.querySelector('#local-weather');
          if (panel) panel.innerHTML = localWeather();
        }
      } catch (e) { error(e.message); }
    }, 5000);
  } catch (e) { error(e.message); }
}
async function loadState() {
  const plants = await api('/plants');
  if (!plants.length) return false;
  plantId = plantId || plants[0].id;
  state = V.statusView(await api(`/plants/${plantId}/status`));
  if (source === null) source = state.device && state.device.source_type || 'real';
  if (state.photo_id && state.photo_id !== currentPhoto) {
    const response = await fetch('/api/v1/images/' + state.photo_id, {headers:{Authorization:'Bearer ' + token}});
    if (response.ok) { if (state.photoUrl) URL.revokeObjectURL(state.photoUrl); window.plantPhotoUrl = URL.createObjectURL(await response.blob()); currentPhoto = state.photo_id; }
  }
  return true;
}
function title(name, subtitle = '') { return `<div class="page-head row"><div><h1>${esc(name)}</h1><small>${esc(subtitle)}</small></div><span class="badge">${esc(state && state.sourceLabel || '模拟数据')}</span></div>`; }
function eventList(items) { return items.length ? items.map(item => `<div class="event"><div><small>${esc(when(item.occurred_at))} · ${esc(V.sourceNames[item.source_type])}</small><p>${esc(item.human_readable)}</p></div></div>`).join('') : '<p class="empty">暂无守候记录</p>'; }
async function render(silent = false) {
  try {
    if (!silent) error('');
    const tab = route();
    document.querySelectorAll('nav a').forEach(a => { a.classList.toggle('active', a.dataset.tab === tab); if (a.dataset.tab === tab) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
    if (!await loadState()) { await renderAdd(); return; }
    if (tab === 'care') await renderCare();
    else if (tab === 'trends') await renderTrends();
    else if (tab === 'records') content.innerHTML = title('守候记录', state.plant.name) + eventList(await api(`/plants/${plantId}/events`));
    else if (tab === 'memories') await renderMemories();
    else if (tab === 'alerts') await renderAlerts();
    else await renderHome();
  } catch (e) { error(e.message); }
}
async function renderHome() {
  const d = state.device || {};
  const events = await api(`/plants/${plantId}/events`);
  content.innerHTML = title(state.plant.name, `${state.plant.scientific_name || '品种待确认'} · ${state.plant.city} · ${state.plant.placement_type === 'indoor' ? '室内' : '户外'}`) + `
  <section class="overview"><div><img class="plant-photo" src="${window.plantPhotoUrl || '/preview-assets/plant.jpg'}" alt="植物照片"><div class="photo-note">${state.photo_id ? '植物照片' : '示例照片 · 非用户实物'}</div></div>
  <div><div class="status-line"><span class="state ${d.operating_mode === 'SAFE_HOLD' ? 'hold' : ''}">${esc(state.modeLabel)}</span><small>${esc(state.faultText || '设备状态已同步')}</small></div>
  <div class="muted">相对土壤湿度</div><div class="soil"><strong>${esc(state.soilText)}</strong><span>%</span></div><div class="meter"><div style="width:${Number(d.soil_moisture) || 0}%"></div></div>
  <div class="metrics"><div><small>空气温度</small><div class="metric-value">${esc(d.temperature_c ?? '--')} <small>°C</small></div></div><div><small>空气湿度</small><div class="metric-value">${esc(d.air_humidity ?? '--')} <small>%</small></div></div><div><small>水箱状态</small><div class="metric-value">${d.water_level_ok ? '正常' : '待检查'}</div></div></div>
  <div class="note">${esc(state.decision && state.decision.explain_zh || '正在等待下一次养护判断')}</div>
  <div class="actions"><button data-action="water" ${state.canWater ? '' : 'disabled'}>补水</button><button class="secondary" data-action="care">查看养护卡</button></div>
  <div class="status-command" role="status"><span class="small-dot"></span><span id="command-status">${esc(state.commandText)}</span></div></div></section>
  <div class="lower"><section class="section"><h2>自动守护</h2><div class="row"><div><div>按养护策略补水</div><small>${state.plant.auto_mode ? '已开启' : '已暂停'}</small></div><label class="toggle"><input type="checkbox" id="auto-switch" aria-label="自动守护" ${state.plant.auto_mode ? 'checked' : ''}><span></span></label></div><div class="note" style="margin-top:22px">最近补水：${esc(when(state.last_watering && state.last_watering.occurred_at))}<br>滚动24小时估算用量：${esc(d.used_24h_ml || 0)} / 120 mL</div><a href="#trends" class="text-link">查看土壤趋势 →</a></section>
  <section class="section"><div class="row"><h2>最近记录</h2><a href="#records" class="text-link">全部记录</a></div>${eventList(events.slice(0, 3))}</section></div>`;
  document.querySelector('#auto-switch').onchange = async event => {
    try { await api(`/plants/${plantId}/auto-mode`, 'PUT', {enabled:event.target.checked}); await render(); }
    catch (e) { event.target.checked = !event.target.checked; error(e.message); }
  };
}
async function renderCare() {
  const recognition = await api(`/plants/${plantId}/recognition`);
  const candidates = recognition.result && recognition.result.candidates || [];
  const profile = state.care_profile, p = profile && profile.profile;
  content.innerHTML = title('植物养护卡', state.plant.name) + `<section class="section"><div class="row"><h2>识别与品种确认</h2><button class="secondary" data-action="capture">重新拍照</button></div><form id="species-form">${candidates.map((c,i) => `<label class="candidate"><input type="radio" name="candidate" value="${i}" ${recognition.default_selection === i ? 'checked' : ''}><span>${esc(c.common_name)}<br><small>${esc(c.scientific_name)}</small></span><small>${Math.round(c.confidence * 100)}%</small></label>`).join('')}<div class="form-grid" style="margin-top:20px"><label>手动名称<input name="common_name" value="${esc(state.plant.common_name)}"></label><label>学名<input name="scientific_name" value="${esc(state.plant.scientific_name)}"></label></div><div class="actions"><button type="submit">确认品种</button><button type="button" class="secondary" data-action="research" ${state.plant.recognition_confirmed ? '' : 'disabled'}>生成养护卡</button></div></form><p id="job-status" class="muted"></p></section>` + (p ? `
  <section class="section"><div class="row"><h2>相对土壤湿度目标</h2><span class="badge">${p.source_type === 'real' ? '真实知识来源' : '模拟知识'}</span></div><div class="soil"><strong>${p.soil_target_min_pct}–${p.soil_target_max_pct}</strong><span>%</span></div>${profile.needs_review ? '<p class="warning">来源存在冲突或需要复核，已采用保守参数。</p>' : ''}<button data-action="confirm-care" ${profile.confirmed ? 'disabled' : ''}>${profile.confirmed ? '养护卡已确认' : '确认养护卡'}</button></section>
  <div class="lower"><section class="section"><h2>园艺资料</h2>${(p.sources || []).map(s => `<div class="source-item"><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)} ↗</a><p class="muted">${esc(s.summary)}</p><small>${esc(V.sourceNames[s.source_type])} · ${esc(when(s.retrieved_at))}</small></div>`).join('')}</section><section class="section" id="local-weather">${localWeather()}</section></div>` : '<p class="empty">养护卡尚未生成</p>');
  document.querySelector('#species-form').onsubmit = async event => { event.preventDefault(); const form = new FormData(event.target); const selected = form.get('candidate'); const candidate = selected !== null ? candidates[Number(selected)] : null; try { await api(`/plants/${plantId}/confirm-species`, 'POST', {common_name:candidate ? candidate.common_name : form.get('common_name'), scientific_name:candidate ? candidate.scientific_name : form.get('scientific_name'), input_method:candidate ? 'recognition' : 'manual', confidence:candidate ? candidate.confidence : null}); await render(); } catch(e) { error(e.message); } };
}
function localWeather() {
  const profile = state.care_profile;
  const weather = V.weatherView(profile && profile.profile.weather, state.device && state.device.source_type);
  return `<h2>当地环境</h2><p>${esc(state.plant.city)} · ${esc(state.plant.timezone)}</p><p class="muted">${esc(weather.sourceLabel)} · ${esc(weather.statusText)}</p>${weather.available ? `<p>气温：${esc(weather.temperatureText)} °C</p><p>未来12小时降雨：${esc(weather.rainText)} mm</p>` : ''}${weather.observedText ? `<p class="muted">观测时间：${esc(weather.observedText)}</p>` : ''}<h2 style="margin-top:32px">家庭经验</h2><a href="#memories" class="text-link">查看已确认的记忆规则 →</a>`;
}
async function renderTrends() {
  const series = await api(`/plants/${plantId}/telemetry/series?range=${range}&source_type=${source}`);
  content.innerHTML = title('土壤趋势', V.coverageLabel(series)) + `<div class="toolbar"><div class="range-group">${[['1d','24小时'],['7d','7天'],['30d','30天']].map(([v,t]) => `<button data-range="${v}" class="${range === v ? 'active' : ''}">${t}</button>`).join('')}</div><select id="source-select" aria-label="数据来源">${Object.entries(V.sourceNames).map(([v,t]) => `<option value="${v}" ${source === v ? 'selected' : ''}>${t}</option>`).join('')}</select></div><section class="section"><div class="chart-key"><span>相对土壤湿度 %</span><span>补水记录 · mL</span></div><div class="chart-wrap"><canvas id="trend-canvas" aria-label="土壤湿度趋势"></canvas></div>${series.points.length ? '' : '<p class="empty">数据积累中</p>'}</section><section class="section"><h2>补水记录</h2>${series.watering_events.length ? series.watering_events.map(w => `<div class="item">${esc(when(w.occurred_at))} · ${esc(w.actual_ml)} mL</div>`).join('') : '<p class="muted">当前范围暂无补水记录</p>'}</section>`;
  document.querySelector('#source-select').onchange = event => { source = event.target.value; render(); };
  document.querySelectorAll('[data-range]').forEach(button => button.onclick = () => { range = button.dataset.range; render(); });
  drawChart(series);
}
function drawChart(series) {
  const canvas = document.querySelector('#trend-canvas'); if (!canvas) return;
  const width = canvas.clientWidth, height = canvas.clientHeight, dpr = devicePixelRatio || 1;
  canvas.width = width * dpr; canvas.height = height * dpr; const ctx = canvas.getContext('2d'); ctx.scale(dpr,dpr);
  ctx.font = '11px sans-serif'; ctx.fillStyle = '#7b8980'; ctx.strokeStyle = '#e1e7e3'; ctx.lineWidth = 1;
  [0,25,50,75,100].forEach(value => { const y = height - 30 - value / 100 * (height - 50); ctx.fillText(String(value),0,y+4); ctx.beginPath(); ctx.moveTo(30,y); ctx.lineTo(width,y); ctx.stroke(); });
  if (!series.points.length) return;
  const first = Date.parse(series.points[0].occurred_at), last = Date.parse(series.points.at(-1).occurred_at);
  const x = time => 34 + (width - 46) * (Date.parse(time) - first) / Math.max(last - first, 1);
  V.chartSegments(series.points).forEach(segment => { ctx.beginPath(); ctx.strokeStyle = '#388460'; ctx.lineWidth = 2; segment.forEach((p,i) => { const y = height - 30 - p.soil_moisture / 100 * (height - 50); if (i) ctx.lineTo(x(p.occurred_at),y); else ctx.moveTo(x(p.occurred_at),y); ctx.fillStyle = '#388460'; ctx.fillRect(x(p.occurred_at)-1.5,y-1.5,3,3); }); ctx.stroke(); });
  ctx.fillStyle = '#bb8c30'; series.watering_events.forEach(w => { ctx.fillRect(x(w.occurred_at)-2,height-35,4,10); });
  ctx.fillStyle = '#7b8980'; ctx.fillText(new Date(first).toLocaleDateString('zh-CN'),34,height-7); ctx.fillText(new Date(last).toLocaleDateString('zh-CN'),Math.max(34,width-78),height-7);
}
async function renderMemories() {
  const memories = await api('/memories');
  content.innerHTML = title('家人的记忆', '那些被记住的故事，继续陪伴植物生长。') + memories.map(m => `<article class="memory"><div class="row"><h2>${esc(m.title)}</h2><small>真实生效 ${m.applied_count} 次</small></div><p>${esc(m.story)}</p><blockquote>${esc(m.original_experience)}</blockquote>${m.structured_rule ? `<p class="muted">${esc(m.structured_rule.preferred_windows.map(w=>w.join('–')).join(' · '))} · ${m.structured_rule.watering_style === 'small_portions' ? '少量分次' : '常规补水'}</p><label class="row"><span>确认并启用经验</span><span class="toggle"><input type="checkbox" data-memory="${m.id}" ${m.rule_enabled ? 'checked' : ''}><span></span></span></label>` : `<button class="secondary" data-action="structure" data-id="${m.id}">整理经验</button>`}</article>`).join('') + `<section class="section"><h2>保存记忆</h2><form id="memory-form" class="form-grid"><label class="full">标题<input name="title" required maxlength="200"></label><label class="full">故事<textarea name="story" maxlength="10000"></textarea></label><label class="full">原始养护经验<textarea name="experience" maxlength="5000"></textarea></label><div><button type="submit">保存记忆</button></div></form><p id="job-status" class="muted"></p></section>`;
  document.querySelector('#memory-form').onsubmit = async event => { event.preventDefault(); const form = new FormData(event.target); try { await api('/memories','POST',{plant_id:plantId,title:form.get('title'),story:form.get('story'),original_experience:form.get('experience')}); await render(); } catch(e) { error(e.message); } };
  document.querySelectorAll('[data-memory]').forEach(input => input.onchange = async () => { try { await api(`/memories/${input.dataset.memory}/enabled`,'PUT',{enabled:input.checked,confirmed:true}); await render(); } catch(e) { input.checked=!input.checked;error(e.message); } });
}
async function renderAlerts() {
  const items = await api('/alerts');
  content.innerHTML = title('告警中心', `${items.filter(a=>!a.is_read).length} 条未读`) + (items.length ? items.map(a => `<section class="section"><div class="row"><h2>${esc(V.faultLabel(a.alert_type))}</h2><small>${esc(when(a.created_at))}</small></div><p>${esc(a.message)}</p><p class="muted">${esc(a.suggestion)}</p>${a.is_read ? '<small>已读</small>' : `<button class="secondary" data-action="read-alert" data-id="${a.id}">标为已读</button>`}</section>`).join('') : '<p class="empty">暂无告警</p>');
}
async function renderAdd() {
  const devices = await api('/devices');
  content.innerHTML = title('添加植物') + `<form id="add-form" class="form-grid"><label>植物昵称<input name="name" required></label><label>设备<select name="device_id">${devices.map(d=>`<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select></label><label>城市<input name="city" required></label><label>时区<input name="timezone" value="Asia/Shanghai" required></label><label>花盆大小<select name="pot_size"><option value="small">小盆</option><option value="medium">中盆</option><option value="large">大盆</option></select></label><label>花盆材质<select name="pot_material"><option value="plastic">塑料</option><option value="terracotta">陶土</option><option value="ceramic">陶瓷</option></select></label><label>放置环境<select name="placement_type"><option value="indoor">室内</option><option value="outdoor">室外</option><option value="balcony">阳台</option></select></label><label><input name="has_drainage" type="checkbox" checked> 有排水孔</label><div><button type="submit" ${devices.length ? '' : 'disabled'}>保存植物</button></div></form>`;
  document.querySelector('#add-form').onsubmit = async event => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); data.has_drainage=!!data.has_drainage; try { const plant=await api('/plants','POST',data); plantId=plant.id;location.hash='care';await render(); }catch(e){error(e.message);} };
}
async function waitJob(id) {
  let result;
  do { await new Promise(resolve => setTimeout(resolve, 2000)); result = await api(`/jobs/${id}`); const text=document.querySelector('#job-status');if(text)text.textContent={queued:'等待处理',running:'正在处理',succeeded:'处理完成',failed:'处理失败'}[result.status]; } while (['queued','running'].includes(result.status));
  if(result.status==='failed')throw new Error('处理失败，请稍后重试'); await render();
}
content.addEventListener('click', async event => {
  const button=event.target.closest('[data-action]'); if(!button)return;
  error('');
  try {
    if(button.dataset.action==='water')document.querySelector('#water-dialog').showModal();
    if(button.dataset.action==='care')location.hash='care';
    if(button.dataset.action==='capture'){await api(`/plants/${plantId}/capture`,'POST',{}, {'Idempotency-Key':key()});document.querySelector('#job-status').textContent='等待设备拍照';}
    if(button.dataset.action==='research'){button.disabled=true;const job=await api(`/plants/${plantId}/care-profile/generate`,'POST');await waitJob(job.job_id);}
    if(button.dataset.action==='confirm-care'){await api(`/plants/${plantId}/care-profile/confirm`,'POST',{profile_id:state.care_profile.id});await render();}
    if(button.dataset.action==='structure'){button.disabled=true;const job=await api(`/memories/${button.dataset.id}/structure-rule`,'POST');await waitJob(job.job_id);}
    if(button.dataset.action==='read-alert'){await api(`/alerts/${button.dataset.id}/read`,'PUT');await render();}
  }catch(e){button.disabled=false;error(e.message);}
});
document.querySelector('#cancel-water').onclick=()=>document.querySelector('#water-dialog').close();
document.querySelector('#water-form').onsubmit=async event=>{event.preventDefault();try{const command=await api(`/plants/${plantId}/water`,'POST',{quantity:Number(document.querySelector('#water-amount').value),unit:'ml'},{'Idempotency-Key':key()});document.querySelector('#water-dialog').close();const label=document.querySelector('#command-status');if(label)label.textContent=V.commandLabel(command.status);await render();}catch(e){document.querySelector('#water-dialog').close();error(e.message);}};
window.addEventListener('hashchange',()=>render());
initialize();
