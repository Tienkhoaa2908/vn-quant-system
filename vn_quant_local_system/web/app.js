const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const fmtMoney = (v) => Number(v || 0).toLocaleString('vi-VN') + ' ₫';
const fmtPct = (v) => (Number(v || 0) * 100).toFixed(2) + '%';

async function api(path, options={}) {
  const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || JSON.stringify(data));
  return data;
}
function setNotice(text, cls='') { const n=$('#notice'); n.textContent=text; n.className=`notice ${cls}`; }
function card(label,value) { return `<div class="card"><div class="label">${label}</div><div class="value">${value}</div></div>`; }
function renderStatus(data) {
  const coverage=data.market?.coverage||[]; const stock=coverage.find(x=>x.asset_type==='STOCK')||{}; const index=coverage.find(x=>x.asset_type==='INDEX')||{};
  const ranking=data.latest_monthly_ranking; const account=data.account?.account||{};
  $('#cards').innerHTML=[
    card('Dữ liệu cổ phiếu',`${stock.symbol_count||0} mã · ${stock.first_day||'-'} → ${stock.last_day||'-'}`),
    card('VNINDEX',`${index.row_count||0} phiên · đến ${index.last_day||'-'}`),
    card('Ranking tháng',ranking?`${ranking.ranking?.length||0} mã · ${ranking.ranking?.[0]?.signal_day||'-'}`:'Chưa chạy'),
    card('Tiền nạp tuần',fmtMoney(account.weekly_contribution_vnd)),card('Tiền mặt',fmtMoney(account.cash_vnd)),card('Quyền thực thi','Research only')
  ].join('');
  $('#coverage').innerHTML=`<pre>${JSON.stringify(coverage,null,2)}</pre>`; renderRanking(ranking); renderAccount(data.account); renderPlan(data.latest_weekly_plan);
}
function renderRanking(payload) {
  const table=$('#ranking-table'); if(!payload||!payload.ranking?.length){table.innerHTML='<tr><td>Chưa có ranking.</td></tr>';return;}
  const rows=payload.ranking.slice(0,30); $('#model-meta').textContent=`Run: ${payload.run.run_id}\nHoàn tất: ${payload.run.finished_at}\nSignal: ${rows[0].signal_day}`;
  table.innerHTML=`<thead><tr><th>Hạng</th><th>Mã</th><th>Score</th><th>Giá</th><th>Vol60</th><th>Low-vol pct</th><th>RS120 pct</th><th>52W pct</th></tr></thead><tbody>`+rows.map(r=>`<tr><td>${r.rank}</td><td><strong>${r.symbol}</strong></td><td>${Number(r.score).toFixed(4)}</td><td>${fmtMoney(r.close_price)}</td><td>${fmtPct(r.volatility_60)}</td><td>${fmtPct(r.low_volatility_pct)}</td><td>${fmtPct(r.relative_strength_120_pct)}</td><td>${fmtPct(r.high_52_week_pct)}</td></tr>`).join('')+'</tbody>';
}
function renderPlan(plan) {
  const el=$('#plan-content'); if(!plan||!Object.keys(plan).length){el.innerHTML='<div class="notice">Chưa có kế hoạch tuần.</div>';return;}
  const sells=plan.sell_symbols||[]; el.innerHTML=`<div class="cards">${card('Signal tháng',plan.signal_day||plan.rationale?.monthly_signal_day||'-')}${card('Ngày giá',plan.market_day||plan.rationale?.market_day||'-')}${card('Mua đề xuất',plan.buy_symbol?`${plan.buy_symbol} × ${plan.buy_quantity}`:'Giữ tiền')}${card('Giá trị mua ước tính',fmtMoney(plan.estimated_buy_value_vnd))}${card('Mã cần bán',sells.length?sells.join(', '):'Không')}${card('Cash khả dụng ước tính',fmtMoney(plan.available_cash_vnd))}</div><pre>${JSON.stringify(plan.rationale||plan,null,2)}</pre>`;
}
function renderAccount(data){if(!data)return;$('#cash').value=data.account?.cash_vnd??0;$('#contribution').value=data.account?.weekly_contribution_vnd??250000;$('#holdings').value=JSON.stringify((data.holdings||[]).map(x=>({symbol:x.symbol,quantity:x.quantity,average_cost:x.average_cost})),null,2);}
async function refresh(){try{const data=await api('/api/status');renderStatus(data);setNotice('Đã cập nhật trạng thái.','good');}catch(e){setNotice(e.message,'bad');}}
async function action(name){setNotice(`Đang chạy ${name}...`,'warn');try{const data=await api(`/api/actions/${name}`,{method:'POST',body:'{}'});setNotice(JSON.stringify(data,null,2),'good');await refresh();}catch(e){setNotice(e.message,'bad');}}
$$('nav button').forEach(btn=>btn.addEventListener('click',()=>{$$('nav button').forEach(x=>x.classList.remove('active'));btn.classList.add('active');$$('.tab').forEach(x=>x.classList.remove('active'));$(`#${btn.dataset.tab}`).classList.add('active');}));
$$('[data-action]').forEach(btn=>btn.addEventListener('click',()=>action(btn.dataset.action)));$('#refresh').addEventListener('click',refresh);
$('#save-account').addEventListener('click',async()=>{try{const holdings=JSON.parse($('#holdings').value||'[]');const data=await api('/api/account',{method:'POST',body:JSON.stringify({cash_vnd:Number($('#cash').value),weekly_contribution_vnd:Number($('#contribution').value),holdings})});$('#account-result').textContent=JSON.stringify(data,null,2);await refresh();}catch(e){$('#account-result').textContent=e.message;}});
async function loadDocs(){try{const data=await api('/api/docs');$('#docs-content').innerHTML=data.documents.map(d=>`<article class="doc"><h3>${d.name}</h3><pre>${d.content.replaceAll('&','&amp;').replaceAll('<','&lt;')}</pre></article>`).join('');}catch(e){$('#docs-content').textContent=e.message;}}
refresh();loadDocs();
