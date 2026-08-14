function humanAction(action) {
  return ({
    HOLD:'Giữ', HOLD_NO_ADD:'Giữ, chưa mua thêm', WATCH:'Theo dõi',
    EXIT_CANDIDATE:'Ứng viên bán', WAIT_SELLABLE:'Chờ cổ phiếu về',
    REVIEW_TRIM:'Rà soát giảm tỷ trọng', DATA_REVIEW_REQUIRED:'Cần kiểm tra dữ liệu'
  })[action] || action || 'Chưa đánh giá';
}
function actionClass(action) {
  if (action==='EXIT_CANDIDATE') return 'bad';
  if (['WATCH','REVIEW_TRIM','WAIT_SELLABLE','DATA_REVIEW_REQUIRED'].includes(action)) return 'warn';
  return 'good';
}
function reviewStatusLabel(observation={}) {
  if(observation.rank!==null && observation.rank!==undefined) return `Hạng ${observation.rank}`;
  return ({INELIGIBLE:'Không eligible',MISSING_EXACT_HISTORY:'Thiếu lịch sử giá',OUTSIDE_REFERENCE_UNIVERSE:'Ngoài universe kiểm định',NO_MONTHLY_SNAPSHOT:'Thiếu snapshot tháng'})[observation.status||''] || 'Ngoài ranking eligible';
}
function reviewStatusClass(observation={}) {
  if(observation.in_top20) return 'good';
  if(['MISSING_EXACT_HISTORY','OUTSIDE_REFERENCE_UNIVERSE','NO_MONTHLY_SNAPSHOT'].includes(observation.status)) return 'warn';
  return 'bad';
}
function reviewReasonLabel(reason='') {
  return ({
    OUTSIDE_TOP20_TWO_CONSECUTIVE_COMPLETED_MONTHS:'Ngoài Top-20 ở cả hai tháng hoàn tất gần nhất.',
    OUTSIDE_TOP20_TWO_MONTHS_BUT_NOT_SELLABLE:'Đủ gate hai tháng nhưng cổ phiếu hiện chưa khả dụng để bán.',
    OUTSIDE_TOP20_LATEST_MONTH_ONLY:'Mới ngoài Top-20 một tháng; tiếp tục theo dõi.',
    INSIDE_TOP20_BUFFER_BUT_OUTSIDE_TOP10:'Đang trong vùng đệm hạng 11–20; giữ nhưng chưa mua thêm.',
    INSIDE_TOP10_OR_RECOVERED_TO_TOP20:'Đang trong Top-10 hoặc đã quay lại Top-20.',
    SELL_HISTORY_HAS_DATA_GAP:'Thiếu dữ liệu lịch sử; không được tự gắn nhãn bán.',
    LESS_THAN_TWO_COMPLETED_MONTHS:'Chưa đủ hai snapshot tháng hoàn tất.',
    POSITION_MATERIALLY_ABOVE_TARGET:'Vị thế cao hơn đáng kể so với tỷ trọng mục tiêu.'
  })[reason] || reason || 'Chưa có lý do.';
}
function renderPositionReviews(rows=[]) {
  if(!rows.length) return '<div class="empty">Chưa có vị thế để rà soát.</div>';
  return `<div class="security-grid">${rows.map(r=>{
    const history=(r.rank_history||[]).slice(0,3);
    const timeline=history.length ? `<div class="monthly-review-history">${history.map((item,index)=>`<div class="monthly-review-item ${index<2?'gate-month':''}"><span class="monthly-review-date">${escapeHtml(item.signal_day||'-')}</span><strong class="${reviewStatusClass(item)}">${escapeHtml(reviewStatusLabel(item))}</strong><span class="monthly-review-detail">${escapeHtml((item.reasons||[]).join(', ')||item.status||'')}</span></div>`).join('')}</div>` : '<div class="empty compact-empty">Kế hoạch cũ chưa có lịch sử ba tháng. Tạo lại kế hoạch.</div>';
    const gate=(r.sell_gate_months||[]).filter(Boolean);
    return `<article class="security-card review-card"><div class="security-head"><div><span class="ticker">${escapeHtml(r.symbol)}</span><span class="muted-text">${fmtNum(r.quantity,0)} cp</span></div>${badge(humanAction(r.action),actionClass(r.action))}</div><div class="metric-grid review-summary-grid"><div><span>Tỷ trọng hiện tại</span><strong>${fmtPct(r.actual_weight)}</strong></div><div><span>Tỷ trọng mục tiêu</span><strong>${fmtPct(r.target_weight)}</strong></div><div><span>Có thể bán</span><strong>${fmtNum(r.sellable_quantity,0)} cp</strong></div><div><span>Sell gate</span><strong class="${r.sell_gate_passed?'bad':'good'}">${r.sell_gate_passed?'Đạt':'Chưa đạt'}</strong></div></div><div class="review-history-title">Lịch sử ranking tháng</div>${timeline}${gate.length?`<div class="sell-gate-evidence">Gate bán dùng: <strong>${gate.map(escapeHtml).join(' + ')}</strong></div>`:''}<p class="reason human-reason">${escapeHtml(reviewReasonLabel(r.reason))}</p></article>`;
  }).join('')}</div>`;
}

function renderPlan(plan, targetSelector='#plan-content') {
  const el=$(targetSelector); if(!el)return;
  if(!plan||!Object.keys(plan).length){el.innerHTML='<div class="empty">Chưa có kế hoạch vốn.</div>';return;}
  const buys=plan.buy_orders||[]; const reviews=plan.position_reviews||[];
  el.innerHTML=`<div class="cards compact-cards">
    ${card('Chu kỳ',escapeHtml(plan.cycle_id||plan.plan_id||'-'))}
    ${card('Signal tháng',escapeHtml(plan.signal_day||plan.rationale?.monthly_signal_day||'-'))}
    ${card('Ngày giá',escapeHtml(plan.market_day||plan.rationale?.market_day||'-'))}
    ${card('Tiền mới lần này',fmtMoney(plan.planned_new_capital_vnd??plan.contribution_vnd))}
    ${card('Có thể giải ngân',fmtMoney(plan.total_planning_buying_power_vnd??plan.spendable_budget_vnd))}
    ${card('Tổng mua đề xuất',fmtMoney(plan.estimated_buy_value_vnd))}
    ${card('Còn lại',fmtMoney(plan.remaining_budget_vnd))}
  </div>
  <div class="section-head compact"><div><h3>Danh sách mua đề xuất</h3><p>Tạo tại thời điểm có vốn; tối đa ${plan.rationale?.maximum_buy_orders||buys.length||1} mã.</p></div></div>
  ${renderBuyOrders(buys)}
  <div class="section-head compact"><div><h3>Rà soát vị thế hiện có</h3><p>Sell gate vẫn dùng hai tháng hoàn tất gần nhất.</p></div></div>
  ${renderPositionReviews(reviews)}
  <div class="research-note">Mỗi lần bấm tạo kế hoạch là một capital cycle độc lập. Shadow nhận từng cycle sau khi Observatory bắt đầu và giả lập ở T+1 open.</div>`;
}
function dashboardActionSummary(name, data) {
  if(name==='sync-broker') return {title:'Đồng bộ danh mục DNSE hoàn tất',details:[`${data.position_count||0} mã đang nắm giữ`,`Tiền khả dụng: ${fmtMoney(data.planner_cash_vnd)}`]};
  if(name==='model') return {title:'C3 đã chạy xong',details:['Top C3 và Tổng quan thị trường đã cập nhật.']};
  if(name==='plan') return {title:'Kế hoạch vốn đã tạo',details:[`Chu kỳ: ${data.cycle_id||'-'}`,`${(data.buy_orders||[]).length} mã mua đề xuất`,`Tổng mua: ${fmtMoney(data.estimated_buy_value_vnd)}`]};
  if(name==='sync') return {title:'Đồng bộ dữ liệu giá hoàn tất',details:['Coverage và Tổng quan thị trường đã cập nhật.']};
  return {title:data.message||data.status||'Hoàn tất',details:[]};
}

(() => {
  const setText=(el,text)=>{if(el&&el.textContent!==text)el.textContent=text;};
  function rewriteLabels(){
    setText(document.querySelector('.subtitle'),'C3 monthly ranking · DNSE read-only portfolio · event-driven capital planner');
    setText(document.querySelector('[data-tab="plan"]'),'Kế hoạch vốn');
    const budget=document.querySelector('.budget-panel');
    if(budget){
      setText(budget.querySelector('.eyebrow'),'TẠO KẾ HOẠCH BẤT KỲ LÚC NÀO');
      setText(budget.querySelector('h2'),'Tiền mới cho lần lập kế hoạch này');
      setText(budget.querySelector('.section-head p:not(.eyebrow)'),'Nhập số tiền mới dự kiến đưa vào. Hệ thống cộng với tiền khả dụng DNSE và tạo một capital cycle ngay lúc bấm.');
      const label=budget.querySelector('label');
      if(label&&label.firstChild&&label.firstChild.nodeValue!=='Tiền mới dự kiến (VND) ') label.firstChild.nodeValue='Tiền mới dự kiến (VND) ';
      setText(document.querySelector('#save-budget'),'Lưu mức mặc định');
      budget.querySelectorAll('[data-action="plan"]').forEach(b=>setText(b,'Tạo kế hoạch ngay'));
    }
    document.querySelectorAll('[data-action="plan"]').forEach(b=>{if(!b.closest('.budget-panel'))setText(b,b.textContent.replace('tuần','vốn').replace('Tuần','Vốn'));});
    document.querySelectorAll('h2,h3,p,span,small,.label').forEach(el=>{
      if(el.children.length)return;
      const next=el.textContent
        .replace('Kế hoạch tuần gần nhất','Kế hoạch vốn gần nhất')
        .replace('Kế hoạch mua và rà soát bán','Kế hoạch vốn và rà soát danh mục')
        .replace('Ngân sách tuần','Tiền mới mặc định')
        .replace('Plan đầu tiên mỗi tuần','Mỗi capital cycle')
        .replace('plan đầu tiên mỗi tuần','mỗi capital cycle')
        .replace('Tuần 1, chuyển khoản','Lần nạp vốn, chuyển khoản');
      setText(el,next);
    });
  }

  async function loadMarket(){
    const notice=document.querySelector('#market-overview-notice');
    const content=document.querySelector('#market-overview-content');
    if(!content)return;
    try{
      setText(notice,'Đang tải ranking thị trường...');
      const data=await api('/api/market-overview?limit=30');
      const m=data.market||{};
      const regime=m.market_risk_on?'Risk-on':'Risk-off';
      content.innerHTML=`<div class="cards compact-cards">${card('Signal',escapeHtml(data.run?.signal_day||'-'))}${card('VNINDEX',fmtNum(m.vnindex_close||0,2),m.market_day||'')}${card('MA250',fmtNum(m.ma250||0,2))}${card('Chế độ thị trường',regime,m.distance_to_ma250===null?'':`Cách MA250 ${fmtPct(m.distance_to_ma250)}`)}</div><div class="market-filter"><button data-market-limit="10">Top 10</button><button data-market-limit="20">Top 20</button><button data-market-limit="30" class="active">Top 30</button></div><div id="market-ranking-grid" class="security-grid"></div><div class="research-note">Trang này chỉ để quan sát ranking và thị trường. Không tạo kế hoạch, không thay đổi shadow, không gửi lệnh.</div>`;
      const render=(limit)=>{
        document.querySelector('#market-ranking-grid').innerHTML=(data.rows||[]).slice(0,limit).map(r=>`<article class="security-card rank-card"><div class="security-head"><div><span class="rank-number">#${r.rank}</span><span class="ticker">${escapeHtml(r.symbol)}</span></div>${r.held_quantity?badge(`Đang giữ ${fmtNum(r.held_quantity,0)} cp`,'good'):badge(r.rank_change===null?'Mới':`${r.rank_change>=0?'↑':'↓'} ${Math.abs(r.rank_change)}`,r.rank_change>=0?'good':'warn')}</div><div class="score-line"><span>Điểm C3</span><strong>${Number(r.score||0).toFixed(4)}</strong></div><div class="metric-grid"><div><span>Giá</span><strong>${fmtMoney(r.close_price)}</strong></div><div><span>Hạng trước</span><strong>${r.previous_rank??'—'}</strong></div><div><span>Low-vol</span><strong>${fmtPct(r.low_volatility_pct)}</strong></div><div><span>RS120</span><strong>${fmtPct(r.relative_strength_120_pct)}</strong></div><div><span>52W</span><strong>${fmtPct(r.high_52_week_pct)}</strong></div></div></article>`).join('');
      };
      render(30);
      content.querySelectorAll('[data-market-limit]').forEach(btn=>btn.onclick=()=>{content.querySelectorAll('[data-market-limit]').forEach(x=>x.classList.remove('active'));btn.classList.add('active');render(Number(btn.dataset.marketLimit));});
      setText(notice,`${data.model_id||'C3'} · cập nhật ${data.run?.finished_at||'-'}`);
    }catch(e){setText(notice,e.message);content.innerHTML='<div class="empty">Không tải được tổng quan thị trường.</div>';}
  }

  const nav=document.querySelector('.tabs-nav');
  const docs=document.querySelector('[data-tab="docs"]');
  if(nav&&!document.querySelector('[data-v46-market]')){
    const button=document.createElement('button');button.textContent='Thị trường';button.dataset.v46Market='true';nav.insertBefore(button,docs||null);
    const section=document.createElement('section');section.id='market-overview';section.className='tab';section.innerHTML='<div class="section-head"><div><p class="eyebrow">READ-ONLY MARKET OVERVIEW</p><h2>Tổng quan thị trường và Top C3</h2><p>Xem ranking bất kỳ lúc nào, tách hoàn toàn khỏi quyết định mua bán.</p></div><button id="market-overview-refresh" class="secondary">Làm mới thị trường</button></div><div id="market-overview-notice" class="notice">Chưa tải.</div><div id="market-overview-content"></div>';
    const docsSection=document.querySelector('#docs');docsSection?.parentNode?.insertBefore(section,docsSection);
    button.onclick=()=>{document.querySelectorAll('.tabs-nav button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('main > .tab').forEach(x=>x.classList.remove('active'));button.classList.add('active');section.classList.add('active');loadMarket();};
    section.querySelector('#market-overview-refresh').onclick=loadMarket;
  }
  const originalRenderStatus=renderStatus;
  renderStatus=function(data){originalRenderStatus(data);rewriteLabels();};
  rewriteLabels();
})();
