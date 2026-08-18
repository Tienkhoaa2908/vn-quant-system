(() => {
  const VERSION='V82_PROFIT_PAPER_APPROVED_WEB';
  const q=s=>document.querySelector(s);
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null;};
  const pct=v=>{const n=num(v);return n===null?'—':`${(n*100).toFixed(2)}%`;};
  const money=v=>{const n=num(v);if(n===null)return '—';const a=Math.abs(n);if(a>=1e9)return `${(n/1e9).toFixed(3)} tỷ`;if(a>=1e6)return `${(n/1e6).toFixed(1)} triệu`;return new Intl.NumberFormat('vi-VN').format(Math.round(n));};
  const cls=v=>{const n=num(v);return n===null?'v82-muted':n>0?'v82-pos':n<0?'v82-neg':'';};
  let latest=null;

  async function load(){
    try{
      const r=await fetch('/api/dashboard-v82',{headers:{'Content-Type':'application/json'}});
      const data=await r.json();
      if(!r.ok||data?.status==='FAILED')throw new Error(data?.message||data?.error||'Không đọc được V82');
      latest=data;render(data);return data;
    }catch(e){const m=q('#v82-meta');if(m)m.textContent=e.message;return null;}
  }

  function profitCards(data){
    const p=data?.historical_profit_v81||{}; const rows=p.policies||[];
    if(!rows.length)return '<div class="empty">Chưa có profit snapshot V81 đã audit.</div>';
    return `<div class="v82-profit-grid">${rows.map(r=>`<article class="v82-profit-card ${r.policy_id==='L15_SWAP50_WORST'?'primary':''}"><small>${esc(r.role||'')}</small><h4>${esc(r.policy_id)}</h4><div class="v82-big ${cls(r.total_return)}">${pct(r.total_return)}</div><div>Profit <strong>${money(r.net_profit_vnd)}</strong></div><div>Ending NAV <strong>${money(r.ending_nav_vnd)}</strong></div><div>CAGR <strong>${pct(r.cagr)}</strong> · MDD <strong class="v82-neg">${pct(r.max_drawdown)}</strong></div>${r.policy_id!=='NO_OVERLAY'?`<div>Uplift vs C3 <strong class="${cls(r.total_return_uplift_vs_c3)}">${pct(r.total_return_uplift_vs_c3)}</strong></div><div>Incremental NAV <strong class="${cls(r.incremental_nav_vs_c3_vnd)}">${money(r.incremental_nav_vs_c3_vnd)}</strong></div>`:''}</article>`).join('')}</div>`;
  }

  function paperHtml(data){
    const p=data?.paper_v80||{}; const active=p.latest_exact_l15_active===true;
    const pair=active?`${esc(p.latest_swap_out||'—')} → ${esc(p.latest_leader||'—')}`:'Chưa có exact-L15';
    const statuses=Object.entries(p.action_status_counts||{}).map(([k,v])=>`${esc(k)}: ${esc(v)}`).join(' · ')||'Chưa có action';
    return `<div class="v82-paper-grid"><article class="v82-status-card"><small>V80 fresh forward</small><strong>${esc(p.status||'NOT_READY')}</strong><div>Observation ${esc(p.observation_count??0)} · Actions ${esc(p.action_count??0)} · Outcomes ${esc(p.outcome_count??0)}</div></article><article class="v82-status-card"><small>Latest exact-L15</small><strong class="${active?'v82-pos':''}">${pair}</strong><div>Floor ${esc(p.latest_execution_floor_date||'—')}</div></article><article class="v82-status-card"><small>Action states</small><strong>${statuses}</strong><div>Live orders: KHÔNG</div></article></div>`;
  }

  function evidenceHtml(data){
    const p=data?.historical_profit_v81||{}; const e=p.event_diagnostics||{}; const cap=p.capacity||{};
    return `<div class="v82-evidence"><div><strong>${esc(e.pre2026_actionable_exact_l15_events??'—')}</strong><span>exact-L15 events pre-2026</span></div><div><strong>${esc(e.pre2026_active_months??'—')}</strong><span>tháng active</span></div><div><strong>${esc(e.pre2026_unique_leaders??'—')}</strong><span>leader khác nhau</span></div><div><strong>${pct(cap.swap50_1bn_max_adv20_participation)}</strong><span>max ADV20 @ 1 tỷ</span></div></div>`;
  }

  function render(data){
    const profit=q('#v82-profit');if(profit)profit.innerHTML=profitCards(data);
    const paper=q('#v82-paper');if(paper)paper.innerHTML=paperHtml(data);
    const evidence=q('#v82-evidence');if(evidence)evidence.innerHTML=evidenceHtml(data);
    const meta=q('#v82-meta');if(meta)meta.textContent='V81 = historical post-selection diagnostic · V80 = fresh forward paper · C3 vẫn là champion · không có live order.';
    const dash=q('#v82-dashboard-mini');if(dash){const p=(data?.historical_profit_v81?.policies||[]).find(x=>x.policy_id==='L15_SWAP50_WORST');const f=data?.paper_v80||{};dash.innerHTML=`<strong>SWAP50 historical uplift ${pct(p?.total_return_uplift_vs_c3)}</strong><span> · V80 obs ${esc(f.observation_count??0)} · outcomes ${esc(f.outcome_count??0)} · exact-L15 ${f.latest_exact_l15_active?'ACTIVE':'inactive'}</span>`;}
  }

  function install(){
    const tactical=q('#tactical-v78');
    if(tactical&&!q('#v82-profit-paper-panel')){
      const panel=document.createElement('div');panel.id='v82-profit-paper-panel';panel.innerHTML=`<div id="v82-meta" class="notice">Đang tải Profit & Paper...</div><div class="panel"><div class="section-head compact"><div><p class="eyebrow">PROFIT · HISTORICAL DIAGNOSTIC</p><h3>Lợi nhuận C3 và tactical challengers</h3><p class="help">P&L dưới đây là V81 historical post-selection diagnostic; không phải fresh OOS và không tự cấp quyền live.</p></div></div><div id="v82-profit"></div><div id="v82-evidence"></div></div><div class="panel"><h3>V80 Forward Paper</h3><p class="help">Registry fresh forward giữ nguyên; exact-L15 mới tạo paper action. Không có auto-sell do health alert.</p><div id="v82-paper"></div></div>`;tactical.appendChild(panel);
    }
    const dashboard=q('#v78-dashboard-panel');
    if(dashboard&&!q('#v82-dashboard-mini')){
      const mini=document.createElement('div');mini.id='v82-dashboard-mini';mini.className='v82-dashboard-mini';mini.textContent='Đang tải profit/paper...';dashboard.appendChild(mini);
    }
    load();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(install,0));else setTimeout(install,0);
  window.V82_PROFIT_PAPER={version:VERSION,load,get latest(){return latest;}};
})();
