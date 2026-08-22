(() => {
  const VERSION='V83_CAPITAL_DISCIPLINE_MAIN_WEB';
  const q=s=>document.querySelector(s);
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null;};
  const pct=v=>{const n=num(v);return n===null?'—':`${(n*100).toFixed(2)}%`;};
  const money=v=>{const n=num(v);if(n===null)return '—';const a=Math.abs(n);if(a>=1e9)return `${(n/1e9).toFixed(3)} tỷ`;if(a>=1e6)return `${(n/1e6).toFixed(1)} triệu`;return new Intl.NumberFormat('vi-VN').format(Math.round(n));};
  const cls=v=>{const n=num(v);return n===null?'v83-muted':n>0?'v83-pos':n<0?'v83-neg':'';};
  let latest=null;

  async function load(){
    try{
      const r=await fetch('/api/dashboard-v83',{headers:{'Content-Type':'application/json'}});
      const data=await r.json();
      if(!r.ok||data?.status==='FAILED')throw new Error(data?.message||data?.error||'Không đọc được V83');
      latest=data; render(data); return data;
    }catch(e){const m=q('#v83-meta');if(m)m.textContent=e.message;return null;}
  }

  function rowTable(rows, kind){
    if(!rows?.length)return `<div class="v83-empty">${kind==='cut'?'Chưa có mã đạt CUT WATCH nghiêm ngặt.':'Không có mã.'}</div>`;
    return `<div class="v83-table-wrap"><table class="v83-table"><thead><tr><th>Mã</th><th>Rank</th><th>P&L kỳ</th><th>Alpha</th><th>Rel 5p</th><th>DD20</th><th>DD60</th><th>Lý do</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.symbol)}</strong></td><td>${esc(r.current_rank)}</td><td class="${cls(r.period_return)}">${pct(r.period_return)}</td><td class="${cls(r.period_relative_return)}">${pct(r.period_relative_return)}</td><td class="${cls(r.relative_5)}">${pct(r.relative_5)}</td><td class="${cls(r.drawdown_20)}">${pct(r.drawdown_20)}</td><td class="${cls(r.drawdown_60)}">${pct(r.drawdown_60)}</td><td>${esc(r.reason)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function entryTable(rows){
    if(!rows?.length)return '<div class="v83-empty">Chưa tính được entry gap.</div>';
    return `<div class="v83-table-wrap"><table class="v83-table"><thead><tr><th>Mã</th><th>Signal close</th><th>T+1 open</th><th>Gap</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.symbol)}</strong></td><td>${money(r.signal_close_vnd)}</td><td>${money(r.entry_open_vnd)}</td><td class="${cls(-Number(r.entry_gap||0))}">${pct(r.entry_gap)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function historical(data){
    const h=data?.historical_v83||{}; const rows=h.primary_base_dnse||[];
    if(h.status!=='SUCCESS'||!rows.length)return '<div class="v83-empty">V83 historical capital-discipline audit chưa chạy trên workstation. Web hiện chỉ hiển thị current guardrail.</div>';
    return `<div class="v83-policy-grid">${rows.map(r=>`<article class="v83-policy-card ${r.policy_id==='C3_BASE'?'base':''}"><small>${esc(r.policy_id)}</small><strong>${pct(r.total_return)}</strong><div>Profit ${money(r.net_profit_vnd)}</div><div>NAV ${money(r.ending_nav_vnd)}</div>${r.policy_id!=='C3_BASE'?`<div>Δ NAV vs C3 <b class="${cls(r.incremental_nav_vs_c3_vnd)}">${money(r.incremental_nav_vs_c3_vnd)}</b></div>`:''}<div>CAGR ${pct(r.cagr)} · MDD ${pct(r.max_drawdown)}</div></article>`).join('')}</div><div class="v83-entry-audit"><strong>Entry timing pre-2026:</strong> T+2 cheaper rate ${pct(h.entry_timing_primary_pre2026?.t2_cheaper_rate)} · mean price improvement ${pct(h.entry_timing_primary_pre2026?.mean_t2_price_improvement_vs_t1)} · staged improvement ${pct(h.entry_timing_primary_pre2026?.mean_staged_price_improvement_vs_t1)}</div>`;
  }

  function panelHtml(data){
    const noadd=data?.no_add_now||[], cut=data?.cut_watch_now||[], recovered=data?.recovered_now||[], gaps=data?.entry_gap_current_cycle||[];
    return `<div id="v83-meta" class="notice">CAPITAL DISCIPLINE · C3 vẫn là champion · không tự gửi lệnh.</div><div class="v83-summary-grid"><article><small>KHÔNG MUA THÊM</small><strong class="${noadd.length?'v83-neg':''}">${noadd.length}</strong><span>${noadd.map(x=>esc(x.symbol)).join(', ')||'Không có'}</span></article><article><small>CUT WATCH</small><strong class="${cut.length?'v83-neg':''}">${cut.length}</strong><span>${cut.map(x=>esc(x.symbol)).join(', ')||'Chưa có'}</span></article><article><small>ĐÃ HỒI</small><strong class="${recovered.length?'v83-pos':''}">${recovered.length}</strong><span>${recovered.map(x=>esc(x.symbol)).join(', ')||'Chưa có'}</span></article><article><small>NEW-LEADER RESEARCH</small><strong>ĐÓNG</strong><span>V80/V81 giữ ở archive evidence</span></article></div><div class="v83-grid2"><section><h3>Không mua thêm khi đang kéo</h3><p class="help">Chặn incremental add; không đồng nghĩa bán vị thế hiện tại.</p>${rowTable(noadd,'noadd')}</section><section><h3>Cut watch nghiêm ngặt</h3><p class="help">Chỉ watch khi persistent rank decay + drag + severe health. Historical V83 còn phải xác nhận trước khi thành policy.</p>${rowTable(cut,'cut')}</section></div><div class="v83-grid2"><section><h3>Recovery evidence</h3><p class="help">Các mã từng drag ở snapshot trước nhưng hiện đã thoát drag. Đây là lý do không dùng one-shot loss làm sell signal.</p>${rowTable(recovered,'recovered')}</section><section><h3>Entry gap C3 hiện tại</h3><p class="help">Gap từ close signal tháng sang open T+1; chỉ đo chất lượng điểm vào, chưa tự delay lệnh.</p>${entryTable(gaps)}</section></div><section class="v83-historical"><h3>Historical capital-discipline audit</h3>${historical(data)}</section>`;
  }

  function archiveOldResearch(){
    const tactical=q('#tactical-v78'); if(!tactical||q('#v83-research-archive'))return;
    const emerging=q('#v78-emerging')?.closest('.panel');
    const recent=q('#v78-recent')?.closest('.panel');
    const v82=q('#v82-profit-paper-panel');
    if(!emerging&&!recent&&!v82)return;
    const details=document.createElement('details');details.id='v83-research-archive';details.className='panel v83-archive';details.innerHTML='<summary><strong>Research archive: leader/L15, recent regime, V80/V81</strong><span>Không còn là trọng tâm vận hành.</span></summary><div id="v83-archive-body"></div>';
    tactical.appendChild(details); const body=details.querySelector('#v83-archive-body');
    [emerging,recent,v82].filter(Boolean).forEach(node=>body.appendChild(node));
  }

  function render(data){
    const root=q('#v83-capital-body'); if(root)root.innerHTML=panelHtml(data);
    const d=q('#v83-dashboard-body');if(d){const noadd=data?.no_add_now||[],cut=data?.cut_watch_now||[],rec=data?.recovered_now||[];d.innerHTML=`<div class="v83-summary-grid"><article><small>KHÔNG MUA THÊM</small><strong class="${noadd.length?'v83-neg':''}">${noadd.length}</strong><span>${noadd.map(x=>esc(x.symbol)).join(', ')||'Không có'}</span></article><article><small>CUT WATCH</small><strong class="${cut.length?'v83-neg':''}">${cut.length}</strong><span>${cut.map(x=>esc(x.symbol)).join(', ')||'Chưa có'}</span></article><article><small>RECOVERED</small><strong class="${rec.length?'v83-pos':''}">${rec.length}</strong><span>${rec.map(x=>esc(x.symbol)).join(', ')||'Chưa có'}</span></article></div>`;}
  }

  function install(){
    const tactical=q('#tactical-v78');
    if(tactical&&!q('#v83-capital-panel')){
      const head=tactical.querySelector('.section-head');
      if(head){const eyebrow=head.querySelector('.eyebrow');if(eyebrow)eyebrow.textContent='C3 MAIN · CAPITAL DISCIPLINE';const h=head.querySelector('h2');if(h)h.textContent='C3 Position Management';const p=head.querySelector('p:not(.eyebrow)');if(p)p.textContent='Ưu tiên quản trị mã đang nắm: không add khi yếu, cut-watch khi deterioration đủ dai, và kiểm tra entry gap. Không săn leader mới.';}
      const panel=document.createElement('div');panel.id='v83-capital-panel';panel.className='panel v83-main';panel.innerHTML='<div class="section-head compact"><div><p class="eyebrow">PRIMARY OPERATING VIEW</p><h2>Capital Discipline</h2><p>Giảm vốn sai chỗ trước khi nghĩ tới mua thêm mã mới.</p></div></div><div id="v83-capital-body">Đang tải...</div>';
      const firstPanel=tactical.querySelector('.panel'); tactical.insertBefore(panel,firstPanel||null);
    }
    const dash=q('#v78-dashboard-panel');
    if(dash){const title=dash.querySelector('h2');if(title)title.textContent='Capital Discipline hôm nay';const desc=dash.querySelector('.section-head p:not(.eyebrow)');if(desc)desc.textContent='Mã nào không nên add, mã nào đủ severe để cut-watch, mã nào đã hồi.';let body=q('#v83-dashboard-body');if(!body){body=document.createElement('div');body.id='v83-dashboard-body';dash.appendChild(body);}}
    setTimeout(archiveOldResearch,100);
    load();
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(install,50));else setTimeout(install,50);
  window.V83_CAPITAL_DISCIPLINE={version:VERSION,load,get latest(){return latest;}};
})();
