const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const fmtMoney = (v) => Number(v || 0).toLocaleString('vi-VN', {maximumFractionDigits:0}) + ' ₫';
const fmtPct = (v) => (Number(v || 0) * 100).toFixed(2) + '%';
const fmtNum = (v, d=2) => Number(v || 0).toLocaleString('vi-VN', {maximumFractionDigits:d});
const escapeHtml = (s) => String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
let latestState = null;

async function api(path, options={}) {
  const response = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || data.error || 'Yêu cầu thất bại');
  return data;
}
function setNotice(text, cls='') {
  const n=$('#notice');
  if(!n) return;
  n.textContent=text;
  n.className=`notice ${cls}`;
}
function card(label,value,sub='') {
  return `<div class="card"><div class="label">${escapeHtml(label)}</div><div class="value">${value}</div>${sub?`<div class="sub">${sub}</div>`:''}</div>`;
}
function badge(text, cls='') { return `<span class="badge ${cls}">${escapeHtml(text)}</span>`; }
function humanAction(action) {
  return ({
    HOLD:'Giữ', HOLD_NO_ADD:'Giữ, chưa mua thêm', WATCH:'Theo dõi',
    EXIT_CANDIDATE:'Ứng viên bán', WAIT_SELLABLE:'Chờ cổ phiếu về', REVIEW_TRIM:'Rà soát giảm tỷ trọng'
  })[action] || action || 'Chưa đánh giá';
}
function actionClass(action) {
  if (action==='EXIT_CANDIDATE') return 'bad';
  if (action==='WATCH'||action==='REVIEW_TRIM'||action==='WAIT_SELLABLE') return 'warn';
  return 'good';
}
function showResult(selector, data, cls='good') {
  const el=$(selector);
  if(!el) return;
  el.className=`result-box ${cls}`;
  const message=data.message || data.status || 'Hoàn tất';
  const details=[];
  if(data.market_data) details.push(`Market: ${data.market_data.status} · ${data.market_data.latest_day||'-'}`);
  if(data.portfolio) details.push(`Danh mục: ${data.portfolio.status} · ${data.portfolio.account_count??0} tiểu khoản`);
  if(data.inserted_row_count!==undefined) details.push(`Đã chèn ${data.inserted_row_count}/${data.input_row_count} dòng`);
  if(data.position_count!==undefined) details.push(`${data.position_count} mã · cash an toàn ${fmtMoney(data.planner_cash_vnd)}`);
  el.innerHTML=`<strong>${escapeHtml(message)}</strong>${details.length?`<div>${details.map(escapeHtml).join('<br>')}</div>`:''}${data.error?`<div class="technical">${escapeHtml(data.error)}</div>`:''}`;
}

function switchTab(name) {
  $$('nav button').forEach(x=>x.classList.toggle('active',x.dataset.tab===name));
  $$('.tab').forEach(x=>x.classList.toggle('active',x.id===name));
}

function renderCoverage(rows=[]) {
  $('#coverage').innerHTML=rows.map(row=>`<div class="coverage-card"><strong>${escapeHtml(row.asset_type)}</strong><span>${fmtNum(row.symbol_count,0)} mã</span><span>${fmtNum(row.row_count,0)} dòng</span><span>${escapeHtml(row.first_day||'-')} → ${escapeHtml(row.last_day||'-')}</span></div>`).join('') || '<div class="empty">Chưa có coverage.</div>';
}

function renderPortfolio(broker, account) {
  const grid=$('#portfolio-grid');
  const positions=broker?.positions || (account?.holdings||[]).map(x=>({
    symbol:x.symbol, quantity:x.quantity, average_cost_vnd:x.average_cost,
    market_value_vnd:0, unrealized_pnl_vnd:0, unrealized_pnl_pct:0, valuation_price_vnd:0
  }));
  const source=broker?.status==='SUCCESS'?'DNSE read-only':'Dữ liệu nhập tay';
  $('#portfolio-source-badge').textContent=source;
  $('#portfolio-source-badge').className=`badge ${broker?.status==='SUCCESS'?'good':'muted'}`;
  $('#broker-summary-text').textContent=broker?.status==='SUCCESS'
    ? `${broker.position_count} mã · cập nhật ${broker.captured_at} · tiền khả dụng ${fmtMoney(broker.planner_cash_vnd)}`
    : 'Chưa có snapshot DNSE. Có thể dùng dữ liệu nhập tay tạm thời.';
  if(!positions.length){grid.innerHTML='<div class="empty">Chưa có cổ phiếu trong danh mục.</div>';return;}
  grid.innerHTML=positions.map(p=>`<article class="security-card portfolio-card">
    <div class="security-head"><div><span class="ticker">${escapeHtml(p.symbol)}</span><span class="muted-text">${fmtNum(p.quantity,0)} cp</span></div>${badge(fmtPct(p.unrealized_pnl_pct),Number(p.unrealized_pnl_pct)>=0?'good':'bad')}</div>
    <div class="metric-grid">
      <div><span>Giá vốn</span><strong>${fmtMoney(p.average_cost_vnd||p.average_cost)}</strong></div>
      <div><span>Giá tham chiếu</span><strong>${fmtMoney(p.valuation_price_vnd)}</strong></div>
      <div><span>Giá trị</span><strong>${fmtMoney(p.market_value_vnd)}</strong></div>
      <div><span>Lãi/lỗ tạm tính</span><strong class="${Number(p.unrealized_pnl_vnd)>=0?'good':'bad'}">${fmtMoney(p.unrealized_pnl_vnd)}</strong></div>
      <div><span>Có thể bán</span><strong>${fmtNum(p.sellable_quantity??p.quantity,0)} cp</strong></div>
    </div>
  </article>`).join('');
}

function renderRanking(payload, broker, targetSelector='#ranking-grid', metaSelector='#model-meta', limit=20) {
  const grid=$(targetSelector);
  const meta=$(metaSelector);
  if(!grid) return;
  if(!payload||!payload.ranking?.length){
    grid.innerHTML='<div class="empty">Chưa có ranking. Bấm Chạy C3.</div>';
    if(meta) meta.textContent='';
    return;
  }
  const holdings=new Map((broker?.positions||[]).map(p=>[p.symbol,p]));
  const rows=payload.ranking.slice(0,limit);
  if(meta) meta.textContent=`Run ${payload.run.run_id} · signal ${rows[0].signal_day} · hoàn tất ${payload.run.finished_at}`;
  grid.innerHTML=rows.map(r=>{
    const held=holdings.get(r.symbol);
    return `<article class="security-card rank-card">
      <div class="security-head"><div><span class="rank-number">#${r.rank}</span><span class="ticker">${escapeHtml(r.symbol)}</span></div>${held?badge(`Đang giữ ${fmtNum(held.quantity,0)} cp`,'good'):badge('Chưa sở hữu','muted')}</div>
      <div class="score-line"><span>Điểm C3</span><strong>${Number(r.score).toFixed(4)}</strong></div>
      <div class="metric-grid">
        <div><span>Giá</span><strong>${fmtMoney(r.close_price)}</strong></div>
        <div><span>Vol60</span><strong>${fmtPct(r.volatility_60)}</strong></div>
        <div><span>Low-vol pct</span><strong>${fmtPct(r.low_volatility_pct)}</strong></div>
        <div><span>RS120 pct</span><strong>${fmtPct(r.relative_strength_120_pct)}</strong></div>
        <div><span>52W pct</span><strong>${fmtPct(r.high_52_week_pct)}</strong></div>
      </div>
    </article>`;
  }).join('');
}

function renderBuyOrders(orders=[]) {
  if(!orders.length) return '<div class="empty">Ngân sách hiện tại chưa mua được mã phù hợp hoặc danh mục không còn thiếu tỷ trọng.</div>';
  return `<div class="security-grid">${orders.map(o=>`<article class="security-card buy-card">
    <div class="security-head"><div><span class="rank-number">#${o.rank}</span><span class="ticker">${escapeHtml(o.symbol)}</span></div>${badge(`Mua ${fmtNum(o.quantity,0)} cp`,'good')}</div>
    <div class="score-line"><span>Chi phí ước tính</span><strong>${fmtMoney(o.estimated_cost_vnd)}</strong></div>
    <div class="metric-grid">
      <div><span>Giá tham chiếu</span><strong>${fmtMoney(o.price_vnd)}</strong></div>
      <div><span>Tỷ trọng hiện tại</span><strong>${fmtPct(o.actual_weight)}</strong></div>
      <div><span>Tỷ trọng mục tiêu</span><strong>${fmtPct(o.target_weight)}</strong></div>
      <div><span>Thiếu tỷ trọng</span><strong>${fmtPct(o.underweight_pct)}</strong></div>
      <div><span>Target gap</span><strong>${fmtMoney(o.target_gap_vnd)}</strong></div>
    </div>
  </article>`).join('')}</div>`;
}
function renderPositionReviews(rows=[]) {
  if(!rows.length) return '<div class="empty">Chưa có vị thế để rà soát.</div>';
  return `<div class="security-grid">${rows.map(r=>`<article class="security-card review-card">
    <div class="security-head"><div><span class="ticker">${escapeHtml(r.symbol)}</span><span class="muted-text">${fmtNum(r.quantity,0)} cp</span></div>${badge(humanAction(r.action),actionClass(r.action))}</div>
    <div class="metric-grid">
      <div><span>Hạng tháng này</span><strong>${r.current_rank??'Ngoài bảng'}</strong></div>
      <div><span>Hạng tháng trước</span><strong>${r.previous_rank??'Ngoài bảng'}</strong></div>
      <div><span>Tỷ trọng hiện tại</span><strong>${fmtPct(r.actual_weight)}</strong></div>
      <div><span>Tỷ trọng mục tiêu</span><strong>${fmtPct(r.target_weight)}</strong></div>
      <div><span>Có thể bán</span><strong>${fmtNum(r.sellable_quantity,0)} cp</strong></div>
    </div>
    <p class="reason">${escapeHtml(r.reason)}</p>
  </article>`).join('')}</div>`;
}
function renderPlan(plan, targetSelector='#plan-content') {
  const el=$(targetSelector); if(!el)return;
  if(!plan||!Object.keys(plan).length){el.innerHTML='<div class="empty">Chưa có kế hoạch tuần.</div>';return;}
  const buys=plan.buy_orders||[]; const reviews=plan.position_reviews||[];
  el.innerHTML=`
    <div class="cards compact-cards">
      ${card('Signal tháng',escapeHtml(plan.signal_day||plan.rationale?.monthly_signal_day||'-'))}
      ${card('Ngày giá',escapeHtml(plan.market_day||plan.rationale?.market_day||'-'))}
      ${card('Ngân sách tuần',fmtMoney(plan.weekly_budget_vnd||plan.contribution_vnd))}
      ${card('Có thể giải ngân',fmtMoney(plan.spendable_budget_vnd))}
      ${card('Tổng mua đề xuất',fmtMoney(plan.estimated_buy_value_vnd))}
      ${card('Ngân sách còn lại',fmtMoney(plan.remaining_budget_vnd))}
    </div>
    <div class="section-head compact"><div><h3>Danh sách mua đề xuất</h3><p>Tối đa ${plan.rationale?.maximum_buy_orders||buys.length||1} mã, ưu tiên mã thiếu tỷ trọng lớn.</p></div></div>
    ${renderBuyOrders(buys)}
    <div class="section-head compact"><div><h3>Rà soát vị thế hiện có</h3><p>EXIT chỉ khi ngoài Top-20 hai tháng liên tiếp; các nhãn khác chỉ là cảnh báo.</p></div></div>
    ${renderPositionReviews(reviews)}
    <div class="research-note">Chế độ nhiều mã là nghiên cứu V44.2. Baseline V43.1 một mã vẫn được lưu để so sánh, chưa có kết luận lịch sử rằng nhiều mã tốt hơn.</div>`;
}

function renderDataSource(ds) {
  const sdk=ds?.sdk||{}; const tz=sdk.timezone||{};
  $('#data-source-status').innerHTML=[
    card('Credentials',ds?.configured?`Đã lưu · ${escapeHtml(ds.api_key_masked||'')}`:'Chưa cấu hình',ds?.source||''),
    card('DNSE SDK',sdk.version_ok?`Sẵn sàng ${escapeHtml(sdk.version)}`:'Chưa sẵn sàng',`Yêu cầu ${sdk.expected_version||'0.5.0'}`),
    card('Múi giờ VN',tz.ready?'Sẵn sàng':'Thiếu tzdata',escapeHtml(tz.zone||'Asia/Ho_Chi_Minh'))
  ].join('');
}

function renderStatus(data) {
  latestState=data;
  const coverage=data.market?.coverage||[];
  const stock=coverage.find(x=>x.asset_type==='STOCK')||{};
  const index=coverage.find(x=>x.asset_type==='INDEX')||{};
  const ranking=data.latest_monthly_ranking;
  const account=data.account?.account||{};
  const broker=data.broker_portfolio;
  $('#cards').innerHTML=[
    card('Dữ liệu cổ phiếu',`${stock.symbol_count||0} mã`,`${stock.first_day||'-'} → ${stock.last_day||'-'}`),
    card('VNINDEX',`${index.row_count||0} phiên`,`Đến ${index.last_day||'-'}`),
    card('Ranking tháng',ranking?`${ranking.ranking?.length||0} mã`:'Chưa chạy',ranking?.ranking?.[0]?.signal_day||''),
    card('Tiền khả dụng',fmtMoney(account.cash_vnd),broker?'Nguồn DNSE':'Nguồn nhập tay'),
    card('Ngân sách tuần',fmtMoney(account.weekly_contribution_vnd),'Trần chi tiêu'),
    card('Danh mục DNSE',broker?`${broker.position_count} mã`:'Chưa đồng bộ',broker?.captured_at||'')
  ].join('');
  $('#dashboard-budget').value=account.weekly_contribution_vnd??250000;
  renderCoverage(coverage);
  renderPortfolio(broker,data.account);
  renderRanking(ranking,broker,'#ranking-grid','#model-meta',20);
  renderRanking(ranking,broker,'#dashboard-ranking-grid','#dashboard-model-meta',10);
  renderPlan(data.latest_weekly_plan,'#plan-content');
  renderPlan(data.latest_weekly_plan,'#dashboard-plan');
  renderAccountEditor(data.account);
  renderDataSource(data.data_source);
}

function holdingRow(row={symbol:'',quantity:0,average_cost:''}) {
  return `<div class="holding-row">
    <label>Mã<input class="holding-symbol" value="${escapeHtml(row.symbol||'')}" placeholder="FPT"></label>
    <label>Số lượng<input class="holding-quantity" type="number" min="0" step="1" value="${Number(row.quantity||0)}"></label>
    <label>Giá vốn<input class="holding-cost" type="number" min="0" step="100" value="${row.average_cost??''}"></label>
    <button class="remove-holding danger" type="button">Xóa</button>
  </div>`;
}
function renderAccountEditor(data){
  if(!data)return;
  $('#cash').value=data.account?.cash_vnd??0;
  $('#contribution').value=data.account?.weekly_contribution_vnd??250000;
  const rows=data.holdings||[];
  $('#holdings-editor').innerHTML=(rows.length?rows:[{}]).map(holdingRow).join('');
  bindHoldingRemove();
}
function bindHoldingRemove(){ $$('.remove-holding').forEach(btn=>btn.onclick=()=>btn.closest('.holding-row').remove()); }

function dashboardActionSummary(name, data) {
  if(name==='sync-broker') {
    return {
      title:'Đồng bộ danh mục DNSE hoàn tất',
      details:[
        `${data.position_count||0} mã đang nắm giữ`,
        `Tiền khả dụng an toàn: ${fmtMoney(data.planner_cash_vnd)}`,
        `${data.details?.readable_account_count||data.masked_accounts?.length||0} tiểu khoản đọc được`
      ]
    };
  }
  if(name==='model') {
    return {title:'C3 đã chạy xong',details:['Top C3 ở ngay bên dưới đã được cập nhật.']};
  }
  if(name==='plan') {
    return {
      title:'Kế hoạch tuần đã tạo',
      details:[
        `${(data.buy_orders||[]).length} mã mua đề xuất`,
        `Tổng mua ước tính: ${fmtMoney(data.estimated_buy_value_vnd)}`,
        `Ngân sách còn lại: ${fmtMoney(data.remaining_budget_vnd)}`
      ]
    };
  }
  if(name==='sync') {
    return {title:'Đồng bộ dữ liệu giá hoàn tất',details:['Coverage dữ liệu ở cuối trang đã được cập nhật.']};
  }
  return {title:data.message||data.status||'Hoàn tất',details:[]};
}
function renderDashboardActionResult(name, data, cls='good') {
  const el=$('#dashboard-action-result');
  if(!el) return;
  const summary=dashboardActionSummary(name,data);
  el.className=`result-box dashboard-result ${cls}`;
  el.innerHTML=`<strong>${escapeHtml(summary.title)}</strong>${summary.details.length?`<div>${summary.details.map(escapeHtml).join('<br>')}</div>`:''}${data.error?`<div class="technical">${escapeHtml(data.error)}</div>`:''}`;
}
function dashboardTarget(name) {
  return ({
    'sync':'#coverage-section',
    'sync-broker':'#portfolio-section',
    'model':'#dashboard-model-section',
    'plan':'#dashboard-plan-section'
  })[name] || '#dashboard-action-result';
}

async function refresh(silent=false){
  try{
    const data=await api('/api/status');
    renderStatus(data);
    if(!silent) setNotice('Đã cập nhật trạng thái.','good');
    return data;
  } catch(e) {
    if(!silent) setNotice(e.message,'bad');
    throw e;
  }
}
async function action(name, trigger=null){
  const fromDashboard=Boolean(trigger?.closest('#dashboard'));
  setNotice(`Đang chạy ${name}...`,'warn');
  if(fromDashboard) renderDashboardActionResult(name,{message:'Đang xử lý...'},'warn');
  try{
    let body={};
    if(name==='plan') {
      body={
        weekly_budget_vnd:Number($('#dashboard-budget').value),
        maximum_buy_orders:Number($('#dashboard-max-orders').value)
      };
    }
    const data=await api(`/api/actions/${name}`,{method:'POST',body:JSON.stringify(body)});

    if(name==='sync-broker') renderPortfolio(data,latestState?.account);
    if(name==='plan') {
      renderPlan(data,'#plan-content');
      renderPlan(data,'#dashboard-plan');
    }
    if(fromDashboard) renderDashboardActionResult(name,data,'good');
    if(trigger?.closest('#data')) showResult('#credential-result',data,'good');
    setNotice(data.message||`${data.status||'SUCCESS'}: ${name}`,'good');
    await refresh(true);

    if(fromDashboard) {
      const target=$(dashboardTarget(name));
      if(target) target.scrollIntoView({behavior:'smooth',block:'start'});
    }
    return data;
  } catch(e) {
    setNotice(e.message,'bad');
    if(fromDashboard) renderDashboardActionResult(name,{message:e.message},'bad');
    if(trigger?.closest('#data')) showResult('#credential-result',{message:e.message},'bad');
    return null;
  }
}

$$('nav button').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.tab)));
$$('[data-tab-jump]').forEach(btn=>btn.addEventListener('click',()=>switchTab(btn.dataset.tabJump)));
$$('[data-action]').forEach(btn=>btn.addEventListener('click',event=>action(btn.dataset.action,event.currentTarget)));
$('#refresh').addEventListener('click',()=>refresh(false));
$('#refresh-data-source').addEventListener('click',async()=>{try{const d=await api('/api/data-source');renderDataSource(d);showResult('#credential-result',{status:'Đã làm mới trạng thái.'});}catch(e){showResult('#credential-result',{message:e.message},'bad');}});
$('#save-budget').addEventListener('click',async()=>{try{await api('/api/account/budget',{method:'POST',body:JSON.stringify({weekly_budget_vnd:Number($('#dashboard-budget').value)})});setNotice('Đã lưu ngân sách tuần.','good');renderDashboardActionResult('budget',{message:'Đã lưu ngân sách tuần.'},'good');await refresh(true);}catch(e){setNotice(e.message,'bad');renderDashboardActionResult('budget',{message:e.message},'bad');}});
$('#save-credentials').addEventListener('click',async()=>{try{const data=await api('/api/data-source/credentials',{method:'POST',body:JSON.stringify({api_key:$('#dnse-api-key').value,api_secret:$('#dnse-api-secret').value})});$('#dnse-api-key').value='';$('#dnse-api-secret').value='';renderDataSource(data);showResult('#credential-result',{status:'Đã lưu credentials local.'});}catch(e){showResult('#credential-result',{message:e.message},'bad');}});
$('#test-credentials').addEventListener('click',async()=>{try{const data=await api('/api/data-source/test',{method:'POST',body:'{}'});showResult('#credential-result',data,data.status==='SUCCESS'?'good':'warn');await refresh(true);}catch(e){showResult('#credential-result',{message:e.message},'bad');}});
$('#install-sdk').addEventListener('click',async()=>{try{showResult('#credential-result',{status:'Đang cài DNSE SDK và tzdata...'},'warn');const data=await api('/api/data-source/install-sdk',{method:'POST',body:'{}'});showResult('#credential-result',{status:data.status==='ALREADY_READY'?'Runtime đã sẵn sàng.':'Đã cài runtime thành công.'});await refresh(true);}catch(e){showResult('#credential-result',{message:e.message},'bad');}});
$('#clear-credentials').addEventListener('click',async()=>{if(!confirm('Xóa API Key và Secret đang lưu local?'))return;try{const data=await api('/api/data-source/clear',{method:'POST',body:'{}'});renderDataSource(data);showResult('#credential-result',{status:'Đã xóa credentials local.'},'warn');}catch(e){showResult('#credential-result',{message:e.message},'bad');}});
$('#import-manual-csv').addEventListener('click',async()=>{const file=$('#manual-csv-file').files[0];if(!file){showResult('#manual-import-result',{message:'Chưa chọn file CSV.'},'bad');return;}try{const content=await file.text();const data=await api('/api/data-source/import-csv',{method:'POST',body:JSON.stringify({filename:file.name,price_unit:$('#manual-price-unit').value,content})});showResult('#manual-import-result',data);await refresh(true);}catch(e){showResult('#manual-import-result',{message:e.message},'bad');}});
$('#add-holding').addEventListener('click',()=>{$('#holdings-editor').insertAdjacentHTML('beforeend',holdingRow());bindHoldingRemove();});
$('#save-account').addEventListener('click',async()=>{try{const holdings=$$('.holding-row').map(row=>({symbol:row.querySelector('.holding-symbol').value.trim().toUpperCase(),quantity:Number(row.querySelector('.holding-quantity').value),average_cost:Number(row.querySelector('.holding-cost').value)||null})).filter(x=>x.symbol&&x.quantity>0);const data=await api('/api/account',{method:'POST',body:JSON.stringify({cash_vnd:Number($('#cash').value),weekly_contribution_vnd:Number($('#contribution').value),holdings})});showResult('#account-result',{status:`Đã lưu ${data.holdings.length} mã nhập tay.`});await refresh(true);}catch(e){showResult('#account-result',{message:e.message},'bad');}});
async function loadDocs(){try{const data=await api('/api/docs');$('#docs-content').innerHTML=data.documents.map(d=>`<article class="doc"><h3>${escapeHtml(d.name)}</h3><pre>${escapeHtml(d.content)}</pre></article>`).join('');}catch(e){$('#docs-content').textContent=e.message;}}
refresh(false); loadDocs();
