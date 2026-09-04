(() => {
  const VERSION='V86_DNSE_OPENAPI_REALTIME_HEALTH';
  const q=s=>document.querySelector(s);
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const fmtAge=v=>Number.isFinite(Number(v))?`${Number(v).toFixed(1)}s`:'—';
  const fmtCaptureAge=v=>{
    const n=Number(v);
    if(!Number.isFinite(n))return '—';
    if(n<120)return `${Math.round(n)}s`;
    if(n<7200)return `${(n/60).toFixed(1)} phút`;
    return `${(n/3600).toFixed(1)} giờ`;
  };

  function badgeClass(status){
    const s=String(status||'');
    if(s==='HEALTHY'||s==='READY'||s==='SUCCESS')return 'good';
    if(s==='IDLE_MARKET_CLOSED')return 'idle';
    if(s.startsWith('DEGRADED')||s==='DEGRADED'||s==='ERROR'||s==='STATE_INVALID'||s==='FAILED')return 'bad';
    return 'warn';
  }

  function ensurePanel(){
    const dashboard=q('#dashboard');
    if(!dashboard||q('#v86-realtime-panel'))return;
    const panel=document.createElement('section');
    panel.id='v86-realtime-panel';
    panel.className='panel v86-realtime';
    panel.innerHTML=`
      <div class="v86-head">
        <div><p class="eyebrow">DNSE OPENAPI REALTIME · ISOLATED SIDECAR</p><h2>Realtime transport health</h2></div>
        <span class="v86-badge warn" id="v86-status-badge">LOADING</span>
      </div>
      <div id="v86-realtime-body" class="v86-body"><div class="v86-empty">Đang đọc sidecar...</div></div>`;
    const anchor=q('#v84-operating-panel')||dashboard.firstChild;
    dashboard.insertBefore(panel,anchor);
  }

  function brokerFreshnessNote(statusPayload){
    const f=statusPayload?.broker_freshness_v86||{};
    const h=statusPayload?.broker_sync_health_v86||{};
    if(!Object.keys(f).length){
      return '<div class="v86-note warn"><strong>Broker freshness chưa có contract V86</strong><span>Không suy diễn trạng thái danh mục chỉ từ realtime market feed.</span></div>';
    }
    const flags=Array.isArray(f.flags)?f.flags:[];
    const cls=f.status==='READY'?'good':'warn';
    const title=f.status==='READY'?'DNSE holdings/EOD freshness đang đạt guard hiện tại':'BROKER STATE CẦN RÀ SOÁT — không đồng nhất freshness';
    const flagText=flags.length?flags.join(' · '):'không có freshness flag';
    return `<div class="v86-note ${cls}">
      <strong>${esc(title)}</strong>
      <span>Holdings capture ${esc(f.holdings_captured_at||'—')} · age ${fmtCaptureAge(f.holdings_capture_age_sec)} · EOD valuation ${esc(f.valuation_market_day||'—')} (${esc(f.valuation_age_calendar_days??'—')} ngày lịch) · last sync ${esc(h.status||f.last_sync_status||'—')}.</span>
      <span>${esc(flagText)}. V55 final-EOD vẫn là định giá chính thức; public realtime tick không tự biến thành broker-position truth.</span>
    </div>`;
  }

  function decorateOperating(statusPayload){
    const f=statusPayload?.broker_freshness_v86||{};
    if(f.status!=='DEGRADED')return;
    const line=q('#v84-operating-body .v84-status-line')||q('.v84-status-line');
    if(!line)return;
    line.classList.remove('good');
    line.classList.add('warn');
    const strong=line.querySelector('strong');
    const span=line.querySelector('span');
    const flags=Array.isArray(f.flags)?f.flags:[];
    if(strong)strong.textContent=flags.includes('EOD_VALUATION_ABSOLUTELY_STALE')?'REALTIME KHỎE NHƯNG EOD ĐANG CŨ':'BROKER STATE CẦN ĐỒNG BỘ/RÀ SOÁT';
    if(span)span.textContent=`DNSE holdings capture ${f.holdings_captured_at||'—'} · EOD valuation ${f.valuation_market_day||'—'} · ${flags.join(' · ')||'freshness degraded'}`;
  }

  function render(d,statusPayload){
    const body=q('#v86-realtime-body'), badge=q('#v86-status-badge');
    if(!body||!badge)return;
    const status=String(d?.status||'UNKNOWN');
    badge.textContent=status;
    badge.className=`v86-badge ${badgeClass(status)}`;
    const rt=d?.runtime||{};
    const tick=d?.last_tick||{};
    body.innerHTML=`
      <div class="v86-metrics">
        <article><small>Transport</small><strong>${d?.transport_connected?'CONNECTED':'DOWN'}</strong><span>process ${d?.process_alive?'alive':'stopped'}</span></article>
        <article><small>Auth</small><strong>${d?.authenticated?'AUTHENTICATED':'NO'}</strong><span>heartbeat ${d?.heartbeat_healthy?'OK':'NOT OK'}</span></article>
        <article><small>Subscriptions</small><strong>${d?.subscriptions_active?'ACTIVE':'NONE'}</strong><span>${esc(d?.symbol_count??0)} mã · ${esc(d?.encoding||'—')}</span></article>
        <article><small>Tick freshness</small><strong>${fmtAge(d?.last_tick_age_sec)}</strong><span>${esc(tick?.symbol||'—')} ${tick?.price??'—'}</span></article>
        <article><small>Reconnect</small><strong>${esc(d?.reconnect_count??0)}</strong><span>pong ${fmtAge(d?.last_pong_age_sec)}</span></article>
        <article><small>Contract</small><strong>${esc(rt?.sdk_version||'—')}</strong><span>API ${esc(rt?.api_version||'—')}</span></article>
      </div>
      <div class="v86-note ${badgeClass(status)}">
        <strong>${esc(d?.message||status)}</strong>
        <span>HTTP 200 không đồng nghĩa feed khỏe. Live-order authority: <b>BLOCKED</b>. REST smoke: ${esc(d?.rest_smoke?.status||'—')}.</span>
      </div>
      ${brokerFreshnessNote(statusPayload)}`;
    decorateOperating(statusPayload);
  }

  async function getJson(path){
    const r=await fetch(path,{cache:'no-store'});
    const d=await r.json();
    if(!r.ok)throw new Error(`${path}:HTTP_${r.status}`);
    return d;
  }

  async function load(){
    ensurePanel();
    try{
      const [d,statusPayload]=await Promise.all([
        getJson('/api/realtime-v86'),
        getJson('/api/status'),
      ]);
      render(d,statusPayload);
    }catch(e){
      render({status:'WEB_BRIDGE_ERROR',message:String(e)},{});
    }
  }

  function install(){
    ensurePanel();
    load();
    setInterval(load,2000);
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
  else install();
  window.V86_REALTIME={VERSION,load};
})();
