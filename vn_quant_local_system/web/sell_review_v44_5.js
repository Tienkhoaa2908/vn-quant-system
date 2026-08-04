function humanAction(action) {
  return ({
    HOLD:'Giữ',
    HOLD_NO_ADD:'Giữ, chưa mua thêm',
    WATCH:'Theo dõi',
    EXIT_CANDIDATE:'Ứng viên bán',
    WAIT_SELLABLE:'Chờ cổ phiếu về',
    REVIEW_TRIM:'Rà soát giảm tỷ trọng',
    DATA_REVIEW_REQUIRED:'Cần kiểm tra dữ liệu'
  })[action] || action || 'Chưa đánh giá';
}

function actionClass(action) {
  if (action==='EXIT_CANDIDATE') return 'bad';
  if (['WATCH','REVIEW_TRIM','WAIT_SELLABLE','DATA_REVIEW_REQUIRED'].includes(action)) return 'warn';
  return 'good';
}

function reviewStatusLabel(observation={}) {
  const rank=observation.rank;
  const status=observation.status||'';
  if(rank!==null && rank!==undefined) return `Hạng ${rank}`;
  return ({
    INELIGIBLE:'Không eligible',
    MISSING_EXACT_HISTORY:'Thiếu lịch sử giá',
    OUTSIDE_REFERENCE_UNIVERSE:'Ngoài universe kiểm định',
    NO_MONTHLY_SNAPSHOT:'Thiếu snapshot tháng'
  })[status] || 'Ngoài ranking eligible';
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
    const timeline=history.length
      ? `<div class="monthly-review-history">${history.map((item,index)=>`<div class="monthly-review-item ${index<2?'gate-month':''}">
          <span class="monthly-review-date">${escapeHtml(item.signal_day||'-')}</span>
          <strong class="${reviewStatusClass(item)}">${escapeHtml(reviewStatusLabel(item))}</strong>
          <span class="monthly-review-detail">${escapeHtml((item.reasons||[]).join(', ')||item.status||'')}</span>
        </div>`).join('')}</div>`
      : `<div class="empty compact-empty">Kế hoạch cũ chưa có lịch sử ba tháng. Tạo lại kế hoạch.</div>`;
    const gate=(r.sell_gate_months||[]).filter(Boolean);
    return `<article class="security-card review-card">
      <div class="security-head"><div><span class="ticker">${escapeHtml(r.symbol)}</span><span class="muted-text">${fmtNum(r.quantity,0)} cp</span></div>${badge(humanAction(r.action),actionClass(r.action))}</div>
      <div class="metric-grid review-summary-grid">
        <div><span>Tỷ trọng hiện tại</span><strong>${fmtPct(r.actual_weight)}</strong></div>
        <div><span>Tỷ trọng mục tiêu</span><strong>${fmtPct(r.target_weight)}</strong></div>
        <div><span>Có thể bán</span><strong>${fmtNum(r.sellable_quantity,0)} cp</strong></div>
        <div><span>Sell gate</span><strong class="${r.sell_gate_passed?'bad':'good'}">${r.sell_gate_passed?'Đạt':'Chưa đạt'}</strong></div>
      </div>
      <div class="review-history-title">Lịch sử ranking tháng</div>
      ${timeline}
      ${gate.length?`<div class="sell-gate-evidence">Gate bán dùng: <strong>${gate.map(escapeHtml).join(' + ')}</strong></div>`:''}
      <p class="reason human-reason">${escapeHtml(reviewReasonLabel(r.reason))}</p>
    </article>`;
  }).join('')}</div>`;
}
