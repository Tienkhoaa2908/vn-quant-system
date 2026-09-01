(() => {
  const VERSION='V86_DNSE_OPENAPI_REALTIME_HEALTH';
  const q=s=>document.querySelector(s);
  const esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const fmtAge=v=>Number.isFinite(Number(v))?`${Number(v).toFixed(1)}s`:'—';

  function badgeClass(status){
    const s=String(status||'');
    if(s==='HEALTHY')return 'good';
    if(s==='IDLE_MARKET_CLOSED')return 'idle';
    if(s.startsWith('DEGRADED')||s==='ERROR'||s==='STATE_INVALID')return 'bad';
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

  function render(d){
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
      </div>`;
  }

  async function load(){
    ensurePanel();
    try{
      const r=await fetch('/api/realtime-v86',{cache:'no-store'});
      const d=await r.json();
      render(d);
    }catch(e){
      render({status:'WEB_BRIDGE_ERROR',message:String(e)});
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
