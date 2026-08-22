(() => {
  const VERSION='V84_MAIN_DAILY_OPERATING_DASHBOARD';
  const q=s=>document.querySelector(s);
  const qa=s=>[...document.querySelectorAll(s)];
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null;};
  const pct=v=>{const x=n(v);return x===null?'—':`${(x*100).toFixed(2)}%`;};
  const money=v=>{const x=n(v);if(x===null)return '—';const a=Math.abs(x);if(a>=1e9)return `${(x/1e9).toFixed(3)} tỷ`;if(a>=1e6)return `${(x/1e6).toFixed(1)} triệu`;if(a>=1e3)return `${(x/1e3).toFixed(1)} nghìn`;return new Intl.NumberFormat('vi-VN').format(Math.round(x));};
  const signedMoney=v=>{const x=n(v);if(x===null)return '—';return `${x>0?'+':''}${money(x)}`;};
  const cls=v=>{const x=n(v);return x===null?'v84-muted':x>0?'v84-pos':x<0?'v84-neg':'';};
  let latest=null;

  async function get(path){
    const r=await fetch(path,{headers:{'Content-Type':'application/json'}});
    const data=await r.json();
    if(!r.ok||data?.status==='FAILED')throw new Error(data?.message||data?.error||`Không đọc được ${path}`);
    return data;
  }

  function coverageLastDay(status){
    const rows=status?.market?.coverage||[];
    return rows.find(x=>String(x.asset_type).toUpperCase()==='STOCK')?.last_day||null;
  }

  function healthMaps(v83){
    const noadd=new Map((v83?.no_add_now||[]).map(x=>[x.symbol,x]));
    const cut=new Map((v83?.cut_watch_now||[]).map(x=>[x.symbol,x]));
    const recovered=new Map((v83?.recovered_now||[]).map(x=>[x.symbol,x]));
    return {noadd,cut,recovered};
  }

  function attentionRows(status,v83,tactical){
    const positions=status?.broker_portfolio?.positions||[];
    const tacticalRows=new Map((tactical?.tactical_rows||[]).map(x=>[x.symbol,x]));
    const maps=healthMaps(v83);
    const nav=n(status?.broker_portfolio?.net_asset_value_vnd)||0;
    return positions.map(p=>{
      const t=tacticalRows.get(p.symbol)||{};
      let level=0,label='PORTFOLIO';
      if(maps.cut.has(p.symbol)){level=4;label='SEVERE WATCH';}
      else if(maps.noadd.has(p.symbol)){level=3;label='ADD REVIEW';}
      else if(maps.recovered.has(p.symbol)){level=2;label='RECOVERED';}
      else if(Number(t.canonical_rank)<=10){level=1;label='C3 HOLD';}
      return {...p,tactical:t,level,label,weight:nav>0?Number(p.market_value_vnd||0)/nav:null};
    }).sort((a,b)=>b.level-a.level||Number(a.unrealized_pnl_pct||0)-Number(b.unrealized_pnl_pct||0)||String(a.symbol).localeCompare(String(b.symbol)));
  }

  function pill(row){
    const c=row.level>=4?'bad':row.level===3?'warn':row.level===2?'good':row.level===1?'core':'muted';
    return `<span class="v84-pill ${c}">${esc(row.label)}</span>`;
  }

  function portfolioTable(rows){
    if(!rows.length)return '<div class="v84-empty">Chưa có snapshot vị thế DNSE.</div>';
    return `<div class="v84-table-wrap"><table class="v84-table"><thead><tr><th>Mã</th><th>SL</th><th>Tỷ trọng</th><th>P&L EOD</th><th>P&L %</th><th>Rank tháng</th><th>Rank hiện tại</th><th>Rel 5p</th><th>Trạng thái</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.symbol)}</strong></td><td>${esc(r.quantity)}</td><td>${pct(r.weight)}</td><td class="${cls(r.unrealized_pnl_vnd)}">${signedMoney(r.unrealized_pnl_vnd)}</td><td class="${cls(r.unrealized_pnl_pct)}">${pct(r.unrealized_pnl_pct)}</td><td>${Number(r.tactical?.canonical_rank)<=100?esc(r.tactical.canonical_rank):'—'}</td><td>${Number(r.tactical?.preview_rank)<=100?esc(r.tactical.preview_rank):'—'}</td><td class="${cls(r.tactical?.relative_5)}">${pct(r.tactical?.relative_5)}</td><td>${pill(r)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function planGuard(status,v83){
    const plan=status?.latest_weekly_plan||status?.latest_capital_plan||{};
    const buys=plan?.buy_orders||[];
    const review=new Set((v83?.no_add_now||[]).map(x=>x.symbol));
    const severe=new Set((v83?.cut_watch_now||[]).map(x=>x.symbol));
    const conflicts=buys.filter(x=>review.has(x.symbol)||severe.has(x.symbol));
    if(conflicts.length){
      return `<div class="v84-guard bad"><strong>PLAN CONFLICT — cần rà soát thủ công</strong><span>Kế hoạch vốn hiện tại đang đề xuất mua thêm: ${conflicts.map(x=>`<b>${esc(x.symbol)}</b>`).join(', ')} trong khi các mã này đang có capital-discipline watch. V83 không tự chặn lệnh và historical no-add chưa outperform C3.</span></div>`;
    }
    if(buys.length){
      return `<div class="v84-guard good"><strong>Kế hoạch vốn không xung đột watch hiện tại</strong><span>${buys.map(x=>`${esc(x.symbol)} ${esc(x.quantity)} cp`).join(' · ')} · vẫn là kế hoạch research-only, không tự gửi lệnh.</span></div>`;
    }
    return '<div class="v84-guard neutral"><strong>Chưa có lệnh mua trong kế hoạch gần nhất</strong><span>Tạo kế hoạch khi cần; dashboard chỉ kiểm tra xung đột, không tự tạo hoặc gửi lệnh.</span></div>';
  }

  function entrySummary(v83){
    const rows=(v83?.entry_gap_current_cycle||[]).filter(x=>n(x.entry_gap)!==null);
    if(!rows.length)return '<div class="v84-empty">Chưa có entry-gap hiện tại.</div>';
    const positives=rows.filter(x=>Number(x.entry_gap)>0).sort((a,b)=>Number(b.entry_gap)-Number(a.entry_gap));
    const avg=rows.reduce((s,x)=>s+Number(x.entry_gap),0)/rows.length;
    const max=positives[0];
    return `<div class="v84-entry-strip"><div><small>Gap trung bình Top10</small><strong class="${cls(-avg)}">${pct(avg)}</strong></div><div><small>Chase gap lớn nhất</small><strong class="${max?'v84-neg':''}">${max?`${esc(max.symbol)} ${pct(max.entry_gap)}`:'Không có'}</strong></div><div><small>Số mã gap dương</small><strong>${positives.length}/${rows.length}</strong></div><span>Chỉ đo execution quality; T+1 vẫn canonical.</span></div>`;
  }

  function render(status,v83,tactical){
    const broker=status?.broker_portfolio||{};
    const positions=broker?.positions||[];
    const totalPnl=positions.reduce((s,p)=>s+Number(p.unrealized_pnl_vnd||0),0);
    const costBasis=positions.reduce((s,p)=>s+Number(p.average_cost_vnd||0)*Number(p.quantity||0),0);
    const pnlPct=costBasis>0?totalPnl/costBasis:null;
    const nav=n(broker.net_asset_value_vnd);
    const stock=n(broker.stock_value_vnd);
    const cash=n(broker.planner_cash_vnd);
    const latestDay=coverageLastDay(status);
    const brokerDay=broker.market_day||null;
    const stale=Boolean(latestDay&&brokerDay&&brokerDay<latestDay);
    const riskOn=Boolean(tactical?.report?.risk_on);
    const rows=attentionRows(status,v83,tactical);
    const noadd=v83?.no_add_now||[], cut=v83?.cut_watch_now||[], recovered=v83?.recovered_now||[];
    const root=q('#v84-operating-body');
    if(!root)return;
    root.innerHTML=`
      <div class="v84-status-line ${stale?'warn':'good'}">
        <div><strong>${stale?'DNSE SNAPSHOT CẦN ĐỒNG BỘ':'DỮ LIỆU VẬN HÀNH SẴN SÀNG'}</strong><span>Market EOD ${esc(latestDay||'—')} · DNSE valuation ${esc(brokerDay||'—')} · captured ${esc(broker.captured_at||'—')}</span></div>
        <button id="v84-sync-broker" class="secondary">Đồng bộ DNSE</button>
      </div>
      <div class="v84-metrics">
        <article><small>NAV EOD</small><strong>${money(nav)}</strong><span>${esc(broker.position_count??0)} vị thế</span></article>
        <article><small>Giá trị cổ phiếu</small><strong>${money(stock)}</strong><span>Exposure ${nav&&stock?pct(stock/nav):'—'}</span></article>
        <article><small>Cash an toàn</small><strong>${money(cash)}</strong><span>${nav&&cash?pct(cash/nav):'—'} NAV</span></article>
        <article><small>P&L vị thế EOD</small><strong class="${cls(totalPnl)}">${signedMoney(totalPnl)}</strong><span class="${cls(pnlPct)}">${pct(pnlPct)}</span></article>
        <article><small>Regime C3</small><strong>${riskOn?'RISK ON':'RISK OFF'}</strong><span>Signal ${esc(tactical?.report?.source_monthly_signal_day||'—')}</span></article>
        <article><small>Capital advisory</small><strong>${noadd.length} / ${cut.length} / ${recovered.length}</strong><span>add-review / severe / recovered</span></article>
      </div>
      <div class="v84-grid2">
        <section><div class="v84-section-head"><div><p class="eyebrow">TODAY'S ATTENTION</p><h3>Danh mục thật × sức khỏe C3</h3></div><span class="v84-advisory">ADVISORY ONLY</span></div>${portfolioTable(rows)}</section>
        <section><div class="v84-section-head"><div><p class="eyebrow">CAPITAL PLAN GUARDRAIL</p><h3>Kiểm tra mua thêm vào mã đang yếu</h3></div></div>${planGuard(status,v83)}${entrySummary(v83)}</section>
      </div>`;
    q('#v84-sync-broker')?.addEventListener('click',()=>{
      const existing=q('[data-action="sync-broker"]');
      if(existing){existing.click();setTimeout(load,2200);setTimeout(load,6000);}
    });
    latest={status,v83,tactical};
    softenV83Labels();
  }

  function softenV83Labels(){
    const panel=q('#v83-capital-panel');
    if(!panel)return;
    qa('#v83-capital-panel small').forEach(el=>{if(el.textContent.trim()==='KHÔNG MUA THÊM')el.textContent='CẢNH BÁO TĂNG VỐN';if(el.textContent.trim()==='CUT WATCH')el.textContent='SEVERE WATCH';});
    qa('#v83-capital-panel h3').forEach(el=>{if(el.textContent.trim()==='Không mua thêm khi đang kéo')el.textContent='Tăng vốn cần rà soát';if(el.textContent.trim()==='Cut watch nghiêm ngặt')el.textContent='Severe deterioration watch';});
    qa('#v83-capital-panel .help').forEach(el=>{
      if(el.textContent.includes('Chặn incremental add'))el.textContent='ADVISORY: mã đang deteriorate. Historical V83 chưa chứng minh auto no-add outperform C3; không tự chặn hoặc gửi lệnh.';
      if(el.textContent.includes('Historical V83 còn phải xác nhận'))el.textContent='ADVISORY: chỉ đánh dấu deterioration dai/severe. Historical V83 không đủ bằng chứng để biến thành auto-cut.';
    });
    const meta=q('#v83-meta');if(meta)meta.textContent='CAPITAL DISCIPLINE · ADVISORY ONLY · C3 vẫn là champion · không tự chặn, không tự gửi lệnh.';
  }

  async function load(){
    const root=q('#v84-operating-body');if(root)root.innerHTML='<div class="v84-empty">Đang tải DNSE + C3 + Capital Discipline...</div>';
    try{
      const [status,v83,tactical]=await Promise.all([get('/api/status'),get('/api/dashboard-v83'),get('/api/tactical-v78')]);
      render(status,v83,tactical);
    }catch(e){if(root)root.innerHTML=`<div class="v84-guard bad"><strong>Không tải được Daily Operating Dashboard</strong><span>${esc(e.message)}</span></div>`;}
  }

  function install(){
    const dashboard=q('#dashboard');
    if(dashboard&&!q('#v84-operating-panel')){
      const panel=document.createElement('section');
      panel.id='v84-operating-panel';panel.className='panel v84-main';
      panel.innerHTML='<div class="section-head compact"><div><p class="eyebrow">DAILY OPERATING DASHBOARD</p><h2>Danh mục thật & quyết định hôm nay</h2><p>NAV/P&L DNSE thật, sức khỏe C3, capital advisory và entry quality trong một màn hình. Không tự gửi lệnh.</p></div><button id="v84-open-tactical" class="secondary">Mở chi tiết C3</button></div><div id="v84-operating-body"></div>';
      const anchor=dashboard.querySelector('.hero-grid')||dashboard.firstChild;
      dashboard.insertBefore(panel,anchor);
      panel.querySelector('#v84-open-tactical')?.addEventListener('click',()=>q('[data-v78-tactical-tab]')?.click());
    }
    softenV83Labels();
    setTimeout(softenV83Labels,400);setTimeout(softenV83Labels,1200);
    load();
    q('#refresh')?.addEventListener('click',()=>setTimeout(load,250));
    qa('[data-action="sync-broker"],[data-action="model"],[data-action="plan"]').forEach(b=>b.addEventListener('click',()=>{setTimeout(load,2500);setTimeout(load,6500);}));
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(install,80));else setTimeout(install,80);
  window.V84_MAIN_OPERATING={version:VERSION,load,get latest(){return latest;}};
})();
