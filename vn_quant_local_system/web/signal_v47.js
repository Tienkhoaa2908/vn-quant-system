(() => {
  const esc = value => escapeHtml(value ?? '');
  const rankText = value => value === null || value === undefined ? 'Ngoài bảng' : `#${value}`;

  function rankCard(row, mode) {
    const canonicalRank = mode === 'canonical' ? row.rank : row.canonical_rank;
    const previewRank = mode === 'preview' ? row.rank : row.preview_rank;
    const held = Number(row.held_quantity || 0);
    const guardAllowed = mode === 'canonical' && Number(row.rank) <= 10
      ? Boolean(row.preview_eligible && row.preview_rank !== null && row.preview_rank !== undefined && Number(row.preview_rank) <= 20)
      : null;
    return `<article class="security-card rank-card">
      <div class="security-head">
        <div><span class="rank-number">#${Number(row.rank)}</span><span class="ticker">${esc(row.symbol)}</span></div>
        ${held > 0 ? badge(`Đang giữ ${fmtNum(held,0)} cp`,'good') : badge('Chưa sở hữu','muted')}
      </div>
      <div class="score-line"><span>Điểm C3</span><strong>${Number(row.score || 0).toFixed(4)}</strong></div>
      <div class="metric-grid">
        <div><span>Hạng canonical</span><strong>${rankText(canonicalRank)}</strong></div>
        <div><span>Hạng preview</span><strong>${rankText(previewRank)}</strong></div>
        <div><span>Giá</span><strong>${fmtMoney(row.close_price)}</strong></div>
        <div><span>Low-vol</span><strong>${fmtPct(row.low_volatility_pct)}</strong></div>
        <div><span>RS120</span><strong>${fmtPct(row.relative_strength_120_pct)}</strong></div>
        <div><span>52W</span><strong>${fmtPct(row.high_52_week_pct)}</strong></div>
      </div>
      ${guardAllowed === null ? '' : `<div class="preview-guard-line"><span class="preview-guard-pill ${guardAllowed?'allow':'block'}">${guardAllowed?'Được phép mua':'Tạm hoãn mua'}</span>${!guardAllowed && row.preview_reasons?.length ? `<span class="muted-text">${esc(row.preview_reasons.join(', '))}</span>` : ''}</div>`}
    </article>`;
  }

  function statusCard(label, value, sub='') {
    return `<article class="signal-v47-status"><span>${esc(label)}</span><strong>${esc(value)}</strong>${sub?`<small>${esc(sub)}</small>`:''}</article>`;
  }

  function renderMarket(data) {
    const content = document.querySelector('#market-overview-content');
    const notice = document.querySelector('#market-overview-notice');
    if (!content) return;
    const canonicalStatus = data.canonical_status || data.signal_status?.canonical || {};
    const preview = data.preview || data.signal_status?.preview || null;
    const market = data.market || {};
    const canonicalRows = data.canonical_rows || [];
    const previewRows = data.preview_rows || [];
    const canonicalCurrent = Boolean(canonicalStatus.current);
    const canonicalButton = document.querySelector('#market-canonical-refresh');
    if (canonicalButton) {
      canonicalButton.disabled = canonicalCurrent;
      canonicalButton.textContent = canonicalCurrent ? 'Canonical đã cập nhật' : 'Chạy canonical tháng';
    }
    content.innerHTML = `
      <div class="signal-v47-status-grid">
        ${statusCard('Canonical chính thức', data.run?.signal_day || 'Chưa có', canonicalCurrent ? 'Đúng tháng hoàn tất mới nhất' : `Cần ${canonicalStatus.expected_signal_day || '-'}`)}
        ${statusCard('Latest preview', preview?.market_day || 'Chưa chạy', preview?.created_at ? `Tính lúc ${preview.created_at}` : 'Bấm cập nhật đánh giá')}
        ${statusCard('VNINDEX', market.vnindex_close ? fmtNum(market.vnindex_close,2) : '—', market.market_day || '')}
        ${statusCard('Chế độ thị trường', market.market_risk_on ? 'Risk-on' : 'Risk-off', market.ma250 ? `MA250 ${fmtNum(market.ma250,2)}` : '')}
      </div>
      <div class="signal-v47-split">
        <section class="signal-v47-panel">
          <div class="signal-v47-section-title"><div><h3>Danh sách canonical tháng</h3><p>Dùng cho Top-10, target weight và sell gate.</p></div><span class="badge good">Chính thức</span></div>
          <div class="security-grid">${canonicalRows.slice(0,20).map(row=>rankCard(row,'canonical')).join('') || '<div class="empty">Chưa có canonical.</div>'}</div>
        </section>
        <section class="signal-v47-panel">
          <div class="signal-v47-section-title"><div><h3>Quan sát phiên mới nhất</h3><p>Dùng làm purchase guard; không tự tạo lệnh bán.</p></div><span class="badge warn">Preview</span></div>
          <div class="security-grid">${previewRows.slice(0,20).map(row=>rankCard(row,'preview')).join('') || '<div class="empty">Chưa có preview. Bấm cập nhật đánh giá mới nhất.</div>'}</div>
        </section>
      </div>
      <div class="signal-v47-note">Mã chỉ được đề xuất mua khi nằm trong canonical Top-10, vẫn eligible và còn trong preview Top-20. Mã chỉ xuất hiện trong preview Top-10 nhưng không có trong canonical Top-10 chỉ để quan sát.</div>`;
    if (notice) notice.textContent = `${data.model_id || 'C3'} · canonical ${data.run?.signal_day || '-'} · preview ${preview?.market_day || 'chưa có'}`;
  }

  async function loadMarket() {
    const notice = document.querySelector('#market-overview-notice');
    try {
      if (notice) notice.textContent = 'Đang tải canonical và preview...';
      const data = await api('/api/market-overview?limit=30');
      renderMarket(data);
    } catch (error) {
      if (notice) notice.textContent = error.message;
      const content = document.querySelector('#market-overview-content');
      if (content) content.innerHTML = '<div class="empty">Không tải được tổng quan thị trường.</div>';
    }
  }

  async function runSignalAction(path, pendingText) {
    const notice = document.querySelector('#market-overview-notice');
    try {
      if (notice) notice.textContent = pendingText;
      await api(path, {method:'POST', body:'{}'});
      await loadMarket();
      await refresh(true);
    } catch (error) {
      if (notice) notice.textContent = error.message;
    }
  }

  function createMarketTab() {
    document.querySelector('[data-v46-market]')?.remove();
    document.querySelector('#market-overview')?.remove();
    const nav = document.querySelector('.tabs-nav');
    const docsButton = document.querySelector('[data-tab="docs"]');
    if (!nav || document.querySelector('[data-v47-market]')) return;
    const button = document.createElement('button');
    button.textContent = 'Thị trường';
    button.dataset.v47Market = 'true';
    nav.insertBefore(button, docsButton || null);
    const section = document.createElement('section');
    section.id = 'market-overview';
    section.className = 'tab';
    section.innerHTML = `
      <div class="section-head">
        <div><p class="eyebrow">CANONICAL + LATEST PREVIEW</p><h2>Tổng quan thị trường</h2><p>Xem Top C3 chính thức và biến động mới nhất mà không tạo kế hoạch.</p></div>
        <div class="signal-v47-actions"><button id="market-preview-refresh">Cập nhật đánh giá mới nhất</button><button id="market-canonical-refresh" class="secondary">Chạy canonical tháng</button></div>
      </div>
      <div id="market-overview-notice" class="notice">Chưa tải.</div>
      <div id="market-overview-content"></div>`;
    const docsSection = document.querySelector('#docs');
    docsSection?.parentNode?.insertBefore(section, docsSection);
    button.onclick = () => {
      document.querySelectorAll('.tabs-nav button').forEach(item=>item.classList.remove('active'));
      document.querySelectorAll('main > .tab').forEach(item=>item.classList.remove('active'));
      button.classList.add('active');
      section.classList.add('active');
      loadMarket();
    };
    section.querySelector('#market-preview-refresh').onclick = () => runSignalAction('/api/actions/market-refresh','Đang đồng bộ giá và tính preview...');
    section.querySelector('#market-canonical-refresh').onclick = () => runSignalAction('/api/actions/canonical','Đang kiểm tra canonical tháng...');
  }

  function guardedBuyCards(orders=[]) {
    if (!orders.length) return '<div class="empty">Không có mã canonical Top-10 vượt qua preview guard với ngân sách hiện tại.</div>';
    return `<div class="security-grid">${orders.map(order=>`<article class="security-card buy-card">
      <div class="security-head"><div><span class="rank-number">#${order.rank}</span><span class="ticker">${esc(order.symbol)}</span></div>${badge(`Mua ${fmtNum(order.quantity,0)} cp`,'good')}</div>
      <div class="score-line"><span>Chi phí ước tính</span><strong>${fmtMoney(order.estimated_cost_vnd)}</strong></div>
      <div class="metric-grid">
        <div><span>Hạng canonical</span><strong>#${order.rank}</strong></div>
        <div><span>Hạng preview</span><strong>${rankText(order.preview_rank)}</strong></div>
        <div><span>Giá tham chiếu</span><strong>${fmtMoney(order.price_vnd)}</strong></div>
        <div><span>Tỷ trọng hiện tại</span><strong>${fmtPct(order.actual_weight)}</strong></div>
        <div><span>Tỷ trọng mục tiêu</span><strong>${fmtPct(order.target_weight)}</strong></div>
        <div><span>Thiếu tỷ trọng</span><strong>${fmtPct(order.underweight_pct)}</strong></div>
      </div><div class="preview-guard-line"><span class="preview-guard-pill allow">Canonical + preview đạt</span></div>
    </article>`).join('')}</div>`;
  }

  function renderPlanV47(plan, targetSelector='#plan-content') {
    const element = document.querySelector(targetSelector);
    if (!element) return;
    if (!plan || !Object.keys(plan).length) {
      element.innerHTML = '<div class="empty">Chưa có kế hoạch vốn.</div>';
      return;
    }
    const guard = plan.preview_purchase_guard || plan.rationale?.preview_purchase_guard || {};
    const buys = plan.buy_orders || [];
    const reviews = plan.position_reviews || [];
    const blocked = guard.blocked || [];
    element.innerHTML = `
      <div class="cards compact-cards">
        ${card('Chu kỳ',esc(plan.cycle_id || plan.plan_id || '-'))}
        ${card('Canonical',esc(plan.canonical_signal_day || plan.signal_day || '-'))}
        ${card('Preview',esc(plan.preview_signal_day || guard.preview_day || '-'))}
        ${card('Tiền mới lần này',fmtMoney(plan.planned_new_capital_vnd ?? plan.contribution_vnd))}
        ${card('Có thể giải ngân',fmtMoney(plan.total_planning_buying_power_vnd ?? plan.spendable_budget_vnd))}
        ${card('Tổng mua đề xuất',fmtMoney(plan.estimated_buy_value_vnd))}
      </div>
      <div class="signal-v47-note">Kế hoạch đã tự đồng bộ dữ liệu giá, danh mục DNSE, kiểm tra canonical và tính preview. Preview chỉ chặn mua; sell gate vẫn dùng hai tháng canonical.</div>
      <div class="section-head compact"><div><h3>Danh sách mua đề xuất</h3><p>${guard.allowed_candidate_count ?? buys.length} mã canonical vượt purchase guard; tối đa ${plan.rationale?.maximum_buy_orders || buys.length || 1} lệnh.</p></div></div>
      ${guardedBuyCards(buys)}
      ${blocked.length ? `<div class="section-head compact"><div><h3>Tạm hoãn mua</h3><p>Các mã vẫn thuộc canonical Top-10 nhưng không vượt preview guard.</p></div></div><div class="preview-blocked-grid">${blocked.map(row=>`<article class="preview-blocked-card"><strong>${esc(row.symbol)}</strong><span>Canonical ${rankText(row.canonical_rank)} · Preview ${rankText(row.preview_rank)}</span><span>${esc(row.reason || '')}</span></article>`).join('')}</div>` : ''}
      <div class="section-head compact"><div><h3>Rà soát vị thế hiện có</h3><p>Ứng viên bán chỉ khi ngoài Top-20 ở hai tháng canonical hoàn tất liên tiếp.</p></div></div>
      ${renderPositionReviews(reviews)}`;
  }

  createMarketTab();
  renderPlan = renderPlanV47;
  document.querySelectorAll('[data-action="model"]').forEach(button=>button.textContent='Cập nhật đánh giá C3');
  const subtitle = document.querySelector('.subtitle');
  if (subtitle) subtitle.textContent='C3 canonical tháng · latest preview guard · event-driven capital planner';
})();

(() => {
  const V48_ID = 'v48-event-manager';
  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
  const money = value => Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits: 0}) + ' ₫';
  let latestPerformance = null;

  function addStyles() {
    if (document.querySelector('#v48-correction-style')) return;
    const style = document.createElement('style');
    style.id = 'v48-correction-style';
    style.textContent = `
      .v48-event-list{display:grid;gap:10px}.v48-event-card{border:1px solid #28476f;border-radius:14px;padding:14px 16px;background:#0d1b31;display:grid;gap:9px}.v48-event-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.v48-event-main{display:grid;gap:4px}.v48-event-main small,.v48-event-meta{color:#8fb7e8}.v48-event-badges,.v48-event-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.v48-pill{border-radius:999px;padding:4px 9px;font-size:12px;border:1px solid #35577f}.v48-pill.active{color:#71efad}.v48-pill.pending{color:#ffd277}.v48-pill.voided,.v48-pill.replaced{color:#ff9e9e}.v48-pill.audit{color:#a9b8d0}.v48-event-actions button{padding:7px 11px}.v48-event-id{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:12px;color:#6f91bd}.v48-price-tools{display:grid;gap:7px}.v48-fill-preview{padding:9px 11px;border:1px solid #29466b;border-radius:10px;color:#a9c8ef;background:#0a1628}.v48-manager-note{margin-bottom:12px}.v48-hidden-ledger{display:none!important}`;
    document.head.appendChild(style);
  }

  async function request(path, options = {}) {
    const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || data.error || 'Yêu cầu thất bại');
    return data;
  }

  function eventDescription(event) {
    if (event.event_type === 'ACTUAL_FILL') {
      return `${esc(event.side)} ${esc(event.symbol)} · ${Number(event.quantity || 0)} cp @ ${money(event.price_vnd)}`;
    }
    if (event.event_type === 'ACTUAL_CASHFLOW') return money(event.amount_vnd);
    const details = event.details || {};
    const target = details.target_event_id ? ` → ${esc(details.target_event_id)}` : '';
    return `${esc(event.event_type)}${target}`;
  }

  function statusPills(event) {
    const correction = String(event.correction_status || 'ACTIVE');
    const valuation = String(event.valuation_status || '');
    const correctionClass = correction === 'ACTIVE' ? 'active' : correction === 'AUDIT_ONLY' ? 'audit' : correction.toLowerCase();
    const valuationClass = valuation === 'PENDING_VALUATION' ? 'pending' : valuation === 'INVALID_MARKET_DAY' ? 'voided' : 'active';
    const labels = [`<span class="v48-pill ${correctionClass}">${esc(correction)}</span>`];
    if (valuation && !['VOIDED','REPLACED','AUDIT_ONLY'].includes(valuation)) {
      labels.push(`<span class="v48-pill ${valuationClass}">${esc(valuation)}</span>`);
    }
    return labels.join('');
  }

  function eventCard(event) {
    const details = event.details || {};
    const correctionText = event.correction?.reason ? `<div class="v48-event-meta">Lý do hiệu chỉnh: ${esc(event.correction.reason)}</div>` : '';
    const valuationText = event.valuation_status === 'PENDING_VALUATION'
      ? `<div class="v48-event-meta">Chưa ảnh hưởng NAV. Kho giá mới nhất: ${esc(latestPerformance?.latest_market_day || 'chưa có')}.</div>`
      : event.valuation_day && event.valuation_day !== event.event_day
        ? `<div class="v48-event-meta">Định giá tại phiên ${esc(event.valuation_day)}.</div>`
        : '';
    const linkText = details.replaces_event_id ? `<div class="v48-event-meta">Thay thế event ${esc(details.replaces_event_id)}</div>` : '';
    const actions = event.editable ? `<div class="v48-event-actions"><button class="secondary" data-v48-edit="${esc(event.event_id)}">Sửa có audit</button><button class="danger" data-v48-void="${esc(event.event_id)}">Hủy có audit</button></div>` : '';
    return `<article class="v48-event-card">
      <div class="v48-event-head">
        <div class="v48-event-main"><strong>${esc(event.event_day)} · ${esc(event.event_type)}</strong><span>${eventDescription(event)}</span><span class="v48-event-id">${esc(event.event_id)}</span></div>
        <div class="v48-event-badges">${statusPills(event)}</div>
      </div>
      ${valuationText}${correctionText}${linkText}
      ${event.note ? `<div class="v48-event-meta">Ghi chú: ${esc(event.note)}</div>` : ''}
      ${actions}
    </article>`;
  }

  async function renderManager() {
    const content = document.querySelector('#performance-content');
    if (!content || document.querySelector(`#${V48_ID}`)) return;
    try {
      latestPerformance = await request('/api/performance');
      if (latestPerformance.status !== 'ACTIVE') return;
      const sections = [...content.querySelectorAll('section.dashboard-output-section')];
      const legacyLedger = sections.find(section => section.querySelector('h3')?.textContent?.includes('Event ledger thực tế'));
      if (!legacyLedger) return;
      legacyLedger.classList.add('v48-hidden-ledger');
      const manager = document.createElement('section');
      manager.id = V48_ID;
      manager.className = 'dashboard-output-section';
      const events = (latestPerformance.events || []).slice().reverse();
      manager.innerHTML = `
        <div class="section-head"><div><h3>Event ledger thực tế</h3><p>Append-only. Sửa hoặc hủy tạo correction event mới; row gốc không bị xóa.</p></div></div>
        <div class="signal-v47-note v48-manager-note">Kho giá mới nhất: ${esc(latestPerformance.latest_market_day || 'chưa có')} · Pending valuation: ${Number(latestPerformance.pending_valuation_count || 0)}. Event pending chỉ đi vào NAV sau khi có dữ liệu phiên tương ứng.</div>
        <div class="v48-event-list">${events.length ? events.map(eventCard).join('') : '<div class="empty">Chưa có event thực tế.</div>'}</div>`;
      content.insertBefore(manager, legacyLedger);
      manager.querySelectorAll('[data-v48-void]').forEach(button => button.addEventListener('click', () => voidEvent(button.dataset.v48Void)));
      manager.querySelectorAll('[data-v48-edit]').forEach(button => button.addEventListener('click', () => editEvent(button.dataset.v48Edit)));
    } catch (error) {
      console.error('V48 event manager:', error);
    }
  }

  async function sendCorrection(flowType, payload) {
    const body = {
      flow_type: flowType,
      amount_vnd: 1,
      event_day: new Date().toISOString().slice(0, 10),
      note: JSON.stringify(payload),
    };
    await request('/api/performance/cashflow', {method: 'POST', body: JSON.stringify(body)});
    document.querySelector('#performance-refresh')?.click();
  }

  async function voidEvent(eventId) {
    const reason = prompt('Lý do hủy event. Lịch sử gốc vẫn được giữ:', 'Nhập thử');
    if (!reason?.trim()) return;
    if (!confirm(`Hủy hiệu lực event ${eventId}?`)) return;
    try {
      await sendCorrection('VOID_EVENT', {event_id: eventId, reason: reason.trim()});
    } catch (error) {
      alert(error.message);
    }
  }

  async function editEvent(eventId) {
    const event = (latestPerformance?.events || []).find(item => item.event_id === eventId);
    if (!event) return;
    const reason = prompt('Lý do sửa event:', event.event_type === 'ACTUAL_FILL' ? 'Sửa thông tin fill' : 'Sửa dòng tiền');
    if (!reason?.trim()) return;
    let replacement;
    if (event.event_type === 'ACTUAL_CASHFLOW') {
      const currentType = event.details?.flow_type || (Number(event.amount_vnd) >= 0 ? 'DEPOSIT' : 'WITHDRAWAL');
      const flowType = prompt('Loại dòng tiền: DEPOSIT hoặc WITHDRAWAL', currentType)?.trim().toUpperCase();
      const eventDay = prompt('Ngày YYYY-MM-DD', event.event_day)?.trim();
      const amount = Number(prompt('Số tiền tuyệt đối (đồng)', String(Math.abs(Number(event.amount_vnd || 0)))));
      const note = prompt('Ghi chú', event.note || '') ?? '';
      if (!['DEPOSIT','WITHDRAWAL'].includes(flowType) || !eventDay || !(amount > 0)) return alert('Thông tin dòng tiền không hợp lệ.');
      replacement = {flow_type: flowType, event_day: eventDay, amount_vnd: amount, note};
    } else {
      const side = prompt('Chiều BUY hoặc SELL', event.side || 'BUY')?.trim().toUpperCase();
      const eventDay = prompt('Ngày khớp YYYY-MM-DD', event.event_day)?.trim();
      const symbol = prompt('Mã cổ phiếu', event.symbol || '')?.trim().toUpperCase();
      const quantity = Number(prompt('Số lượng cổ phiếu', String(event.quantity || 0)));
      const unit = prompt('Đơn vị giá: VND hoặc THOUSAND_VND', 'VND')?.trim().toUpperCase();
      const defaultPrice = unit === 'THOUSAND_VND' ? Number(event.price_vnd || 0) / 1000 : Number(event.price_vnd || 0);
      const price = Number(prompt(unit === 'THOUSAND_VND' ? 'Giá khớp (nghìn đồng)' : 'Giá khớp (đồng)', String(defaultPrice)));
      const fees = Number(prompt('Phí (đồng)', String(event.fees_vnd || 0)));
      const taxes = Number(prompt('Thuế (đồng)', String(event.taxes_vnd || 0)));
      const planId = prompt('Plan ID, để trống nếu tự ghép', event.plan_id || '') ?? '';
      const note = prompt('Ghi chú', event.note || '') ?? '';
      if (!['BUY','SELL'].includes(side) || !eventDay || !symbol || !(quantity > 0) || !(price > 0) || !['VND','THOUSAND_VND'].includes(unit)) return alert('Thông tin fill không hợp lệ.');
      replacement = {side, event_day: eventDay, symbol, quantity, price_vnd: price, price_unit: unit, fees_vnd: fees || 0, taxes_vnd: taxes || 0, plan_id: planId || null, note};
    }
    if (!confirm('Ghi replacement event và vô hiệu hóa event cũ?')) return;
    try {
      await sendCorrection('REPLACE_EVENT', {event_id: eventId, reason: reason.trim(), replacement});
    } catch (error) {
      alert(error.message);
    }
  }

  function augmentFillForm() {
    const priceInput = document.querySelector('#performance-fill-price');
    const button = document.querySelector('#performance-add-fill');
    if (!priceInput || !button || document.querySelector('#performance-fill-price-unit')) return;
    const label = document.createElement('label');
    label.innerHTML = `Đơn vị giá<select id="performance-fill-price-unit"><option value="VND">Đồng</option><option value="THOUSAND_VND">Nghìn đồng</option></select>`;
    priceInput.closest('label')?.insertAdjacentElement('afterend', label);
    const preview = document.createElement('div');
    preview.id = 'v48-fill-preview';
    preview.className = 'v48-fill-preview';
    button.insertAdjacentElement('beforebegin', preview);
    const update = () => {
      const raw = Number(priceInput.value || 0);
      const unit = document.querySelector('#performance-fill-price-unit')?.value || 'VND';
      const normalized = unit === 'THOUSAND_VND' ? raw * 1000 : raw;
      const quantity = Number(document.querySelector('#performance-fill-quantity')?.value || 0);
      preview.textContent = normalized > 0 ? `Giá chuẩn hóa: ${money(normalized)} · Giá trị: ${money(normalized * quantity)}` : 'Nhập giá để xem giá trị chuẩn hóa.';
    };
    priceInput.addEventListener('input', update);
    label.querySelector('select').addEventListener('change', update);
    document.querySelector('#performance-fill-quantity')?.addEventListener('input', update);
    update();
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('#performance-add-fill');
    if (!button) return;
    const input = document.querySelector('#performance-fill-price');
    const unit = document.querySelector('#performance-fill-price-unit')?.value || 'VND';
    const raw = Number(input?.value || 0);
    const normalized = unit === 'THOUSAND_VND' ? raw * 1000 : raw;
    if (!(normalized >= 1000)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      alert(`Giá đang được hiểu là ${money(normalized)}. Nhập 72000 nếu đơn vị là đồng, hoặc chọn “Nghìn đồng” rồi nhập 72.`);
      return;
    }
    const symbol = document.querySelector('#performance-fill-symbol')?.value?.trim().toUpperCase() || '';
    const quantity = Number(document.querySelector('#performance-fill-quantity')?.value || 0);
    if (!confirm(`Xác nhận fill ${symbol}: ${quantity} cp @ ${money(normalized)}?`)) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (unit === 'THOUSAND_VND' && input) {
      input.value = String(normalized);
      document.querySelector('#performance-fill-price-unit').value = 'VND';
    }
  }, true);

  function enhance() {
    addStyles();
    augmentFillForm();
    renderManager();
  }

  let scheduled = false;
  const observer = new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    setTimeout(() => {
      scheduled = false;
      enhance();
    }, 80);
  });
  observer.observe(document.body, {childList: true, subtree: true});
  document.addEventListener('click', event => {
    if (event.target.closest('[data-v45-performance-tab], #performance-refresh')) setTimeout(enhance, 250);
  });
  setTimeout(enhance, 300);
})();
