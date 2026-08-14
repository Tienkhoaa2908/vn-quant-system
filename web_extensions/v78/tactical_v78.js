(() => {
  const VERSION = 'V78_C3_TACTICAL_EXISTING_WEB';
  const q = selector => document.querySelector(selector);
  const qa = selector => [...document.querySelectorAll(selector)];
  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const asNum = value => { const n = Number(value); return Number.isFinite(n) ? n : null; };
  const pct = value => { const n=asNum(value); return n===null ? '—' : `${(n*100).toFixed(2)}%`; };
  const rank = value => { const n=asNum(value); return n===null || n>100000 ? '—' : String(Math.trunc(n)); };
  const cls = value => { const n=asNum(value); return n===null ? 'v78-muted' : n>0 ? 'v78-pos' : n<0 ? 'v78-neg' : ''; };
  let latest = null;
  let loading = false;

  async function request(path, options={}) {
    const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
    const data = await response.json();
    if (!response.ok || data?.status === 'FAILED') throw new Error(data.message || data.error || 'Yêu cầu tactical thất bại');
    return data;
  }
  function reportOf(data){ return data?.report && typeof data.report==='object' ? data.report : {}; }
  function top10Rows(data){ return (data?.tactical_rows || []).filter(row => { const n=asNum(row.canonical_rank); return n!==null && n<=10; }).sort((a,b)=>Number(a.canonical_rank)-Number(b.canonical_rank)); }
  function actionPill(row){
    const action=String(row.action||''); const dragging=String(row.dragging_current_period||'').toLowerCase()==='true';
    if(dragging) return '<span class="v78-pill bad">KÉO XUỐNG</span>';
    if(action.includes('WATCH')||action.includes('RISK')) return `<span class="v78-pill warn">${esc(action)}</span>`;
    return `<span class="v78-pill good">${esc(action||'CORE')}</span>`;
  }
  function top10Table(data){
    const rows=top10Rows(data);
    if(!rows.length) return '<div class="empty">Chưa có dữ liệu Top10 tactical.</div>';
    return `<div class="v78-table-wrap"><table class="v78-table"><thead><tr><th>Mã</th><th>Rank tháng</th><th>Rank hiện tại</th><th>P&L từ open T+1</th><th>VNINDEX</th><th>Alpha</th><th>Rel 5p</th><th>DD20</th><th>DD60</th><th>Trạng thái</th></tr></thead><tbody>${rows.map(row=>`<tr><td><strong>${esc(row.symbol)}</strong></td><td>${rank(row.canonical_rank)}</td><td>${rank(row.preview_rank)}</td><td class="${cls(row.period_return)}">${pct(row.period_return)}</td><td class="${cls(row.period_benchmark_return)}">${pct(row.period_benchmark_return)}</td><td class="${cls(row.period_relative_return)}">${pct(row.period_relative_return)}</td><td class="${cls(row.relative_5)}">${pct(row.relative_5)}</td><td class="${cls(row.drawdown_20)}">${pct(row.drawdown_20)}</td><td class="${cls(row.drawdown_60)}">${pct(row.drawdown_60)}</td><td>${actionPill(row)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function emergingTable(data){
    const rows=data?.emerging_radar || [];
    if(!rows.length) return '<div class="empty">Chưa có leader mới đủ điều kiện radar.</div>';
    return `<div class="v78-table-wrap"><table class="v78-table"><thead><tr><th>Mã</th><th>Rank hiện tại</th><th>P&L kỳ</th><th>Alpha kỳ</th><th>Rel 5p</th><th>Vol 5/20</th><th>Ridge</th><th>Trạng thái</th></tr></thead><tbody>${rows.map(row=>`<tr><td><strong>${esc(row.symbol)}</strong></td><td>${rank(row.preview_rank)}</td><td class="${cls(row.period_return)}">${pct(row.period_return)}</td><td class="${cls(row.period_relative_return)}">${pct(row.period_relative_return)}</td><td class="${cls(row.relative_5)}">${pct(row.relative_5)}</td><td>${asNum(row.volume_ratio_5_20)?.toFixed(2) ?? '—'}</td><td>${String(row.ridge_monthly_top10||'').toLowerCase()==='true'?'Có':'—'}</td><td>${actionPill(row)}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function recentCards(data){
    const report=reportOf(data); const recent=report.recent_regime_evidence || {};
    const rows=[...(recent.v72||[]).map(x=>({...x,family:'Overlay'})), ...(recent.ridge||[]).map(x=>({...x,family:'Ridge'}))];
    if(!rows.length) return '<div class="empty">Chưa có artifact recent 6/12/18 tháng.</div>';
    return `<div class="v78-recent-grid">${rows.map(row=>`<article class="v78-recent-card"><h4>${esc(row.family)} · ${esc(row.candidate_id)} · ${esc(row.window_months)} tháng</h4><div>C3/base <strong class="${cls(row.baseline_return)}">${pct(row.baseline_return)}</strong> · Candidate <strong class="${cls(row.candidate_return)}">${pct(row.candidate_return)}</strong></div><div>Delta <strong class="${cls(row.candidate_minus_baseline)}">${pct(row.candidate_minus_baseline)}</strong> · VNINDEX ${pct(row.benchmark_return)}</div><div class="v78-note">Win-rate tháng: ${pct(row.candidate_month_win_rate)} · chỉ là recent-regime evidence.</div></article>`).join('')}</div>`;
  }
  function summaryHtml(data){
    const r=reportOf(data); const drags=r.dragging_incumbents||[]; const emerging=data?.emerging_radar||[]; const pair=r.l15_swap_pair||{};
    const leader=pair.active ? `${esc(pair.swap_out)} → ${esc(pair.leader)}` : emerging[0]?.symbol ? `${esc(emerging[0].symbol)} (radar)` : 'Chưa có';
    return `<div class="v78-summary-grid"><div class="v78-summary-card"><small>Mô hình chính</small><strong>C3</strong><div class="v78-note">${esc(r.operational_champion||data.operational_champion||'C3_STABLE_3_PAST_IC_SHRUNK')}</div></div><div class="v78-summary-card"><small>Regime</small><strong>${r.risk_on?'RISK ON':'RISK OFF'}</strong><div class="v78-note">Dữ liệu ${esc(r.capture_day||data.capture_day||'—')}</div></div><div class="v78-summary-card"><small>Top10 đang kéo xuống</small><strong class="${drags.length?'v78-neg':''}">${drags.length}</strong><div class="v78-note">${drags.length?esc(drags.join(', ')):'Không có'}</div></div><div class="v78-summary-card"><small>Leader intra-month</small><strong>${leader}</strong><div class="v78-note">L15 chỉ active khi đủ persistence + relative + volume</div></div></div>`;
  }
  function render(data){
    latest=data; const r=reportOf(data);
    const summary=q('#v78-summary'); if(summary) summary.innerHTML=summaryHtml(data);
    const dashboard=q('#v78-dashboard-summary'); if(dashboard) dashboard.innerHTML=summaryHtml(data);
    const top=q('#v78-top10'); if(top) top.innerHTML=top10Table(data);
    const emerging=q('#v78-emerging'); if(emerging) emerging.innerHTML=emergingTable(data);
    const recent=q('#v78-recent'); if(recent) recent.innerHTML=recentCards(data);
    const note=q('#v78-meta'); if(note) note.textContent=`Signal tháng ${r.source_monthly_signal_day||'—'} · execution start ${r.period_execution_start_day||'—'} · P&L gross từ next-session open đến current close · Ridge chỉ shadow confirmation.`;
  }
  async function load(silent=false){
    try{ const data=await request('/api/tactical-v78'); render(data); return data; }
    catch(e){ if(!silent){ const meta=q('#v78-meta'); if(meta) meta.textContent=e.message; } return null; }
  }
  async function refreshTactical(){
    if(loading)return; loading=true; const button=q('#v78-refresh'); if(button){button.disabled=true;button.textContent='Đang cập nhật...';}
    try{ const data=await request('/api/actions/tactical-v78',{method:'POST',body:'{}'}); render(data); }
    catch(e){ const meta=q('#v78-meta'); if(meta) meta.textContent=e.message; }
    finally{loading=false;if(button){button.disabled=false;button.textContent='Cập nhật Tactical';}}
  }
  function activate(section, button){ qa('.tabs-nav button').forEach(x=>x.classList.remove('active')); qa('main > .tab').forEach(x=>x.classList.remove('active')); button.classList.add('active'); section.classList.add('active'); load(false); }
  function install(){
    const nav=q('.tabs-nav'); const docsButton=q('[data-tab="docs"]'); const docsSection=q('#docs');
    if(nav && !q('[data-v78-tactical-tab]')){
      const button=document.createElement('button'); button.textContent='Tactical'; button.dataset.v78TacticalTab='true'; nav.insertBefore(button,docsButton||null);
      const section=document.createElement('section'); section.id='tactical-v78'; section.className='tab'; section.innerHTML=`<div class="section-head"><div><p class="eyebrow">C3 MAIN · INTRA-MONTH ADVISORY</p><h2>Tactical C3</h2><p>Giữ nguyên C3 tháng; theo dõi Top10 cũ, leader mới và recent-regime evidence. Không tự gửi lệnh.</p></div><div class="v78-command"><button id="v78-refresh">Cập nhật Tactical</button></div></div><div id="v78-meta" class="notice">Đang tải snapshot...</div><div id="v78-summary"></div><div class="panel"><h3>Top10 tháng trước: P&L và sức khỏe hiện tại</h3><p class="help">P&L đo từ open phiên kế tiếp sau signal tháng đến close hiện tại; “kéo xuống” chỉ khi vừa âm tuyệt đối vừa thua VNINDEX.</p><div id="v78-top10"></div></div><div class="panel"><h3>Leader intra-month</h3><p class="help">WATCH_EMERGING chưa phải lệnh mua. Exact L15 cần persistence tuần trước + relative5 + volume.</p><div id="v78-emerging"></div></div><div class="panel"><h3>Recent regime: 6 / 12 / 18 tháng</h3><div id="v78-recent"></div></div>`;
      (docsSection?.parentNode || q('main')).insertBefore(section,docsSection||null);
      button.onclick=()=>activate(section,button);
      section.querySelector('#v78-refresh').onclick=refreshTactical;
    }
    const dashboard=q('#dashboard');
    if(dashboard && !q('#v78-dashboard-panel')){
      const panel=document.createElement('section'); panel.id='v78-dashboard-panel'; panel.className='panel v78-dashboard-alert'; panel.innerHTML='<div class="section-head compact"><div><p class="eyebrow">TACTICAL C3</p><h2>Kiểm tra danh mục trong tháng</h2><p>Top10 cũ đang kéo xuống và leader mới trước cuối tháng.</p></div><button id="v78-dashboard-open" class="secondary">Mở Tactical</button></div><div id="v78-dashboard-summary"></div>';
      const modelSection=q('#dashboard-model-section'); dashboard.insertBefore(panel,modelSection||dashboard.firstChild);
      panel.querySelector('#v78-dashboard-open').onclick=()=>q('[data-v78-tactical-tab]')?.click();
    }
    qa('[data-action="model"]').forEach(button=>button.addEventListener('click',()=>{setTimeout(()=>load(true),2500);setTimeout(()=>load(true),6500);}));
    load(true);
  }
  install();
  window.V78_TACTICAL={version:VERSION,load,refresh:refreshTactical,get latest(){return latest;}};
})();
