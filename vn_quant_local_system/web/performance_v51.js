(() => {
  const VERSION = 'V54_RESEARCH_SCOPE_SELLABILITY';
  const CYCLE_VERSION = 'V54_RESEARCH_SCOPE_SELLABILITY';
  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
  const money = value => Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits: 0}) + ' ₫';
  const num = value => Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits: 2});
  const pct = value => value === null || value === undefined
    ? 'Chưa đủ dữ liệu'
    : (Number(value) * 100).toFixed(2) + '%';

  let latest = null;
  let refreshTimer = null;
  let commandBusy = false;

  async function request(path, options = {}) {
    const response = await fetch(path, {
      headers: {'Content-Type': 'application/json'},
      ...options,
    });
    const data = await response.json();
    if (!response.ok || data?.status === 'FAILED') {
      throw new Error(data.message || data.error || 'Yêu cầu thất bại');
    }
    return data;
  }

  function vnDay() {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Ho_Chi_Minh',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date());
    const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function humanStatus(status) {
    return ({
      MATCHED_COMPLETE_SHADOW_PENDING: 'ĐÃ GHÉP ĐỦ · SHADOW CHỜ T+1',
      MATCHED_PARTIAL_SHADOW_PENDING: 'ĐÃ GHÉP MỘT PHẦN · SHADOW CHỜ T+1',
      PLANNED_SHADOW_PENDING: 'CHƯA MUA · SHADOW CHỜ T+1',
      MATCHED_COMPLETE: 'ĐÃ GHÉP ĐỦ',
      MATCHED_PARTIAL: 'ĐÃ GHÉP MỘT PHẦN',
      MISSED: 'CHƯA THỰC HIỆN',
      OUTSIDE_PLAN_CONFIRMED: 'NGOÀI KẾ HOẠCH ĐÃ XÁC NHẬN',
      WAIT_SELLABLE_AT_PLAN: 'CHỜ CỔ PHIẾU VỀ · KHÔNG TÍNH TUÂN THỦ',
    })[status] || status || 'CHƯA XÁC ĐỊNH';
  }

  function statusClass(status) {
    if (status === 'MATCHED_COMPLETE' || status === 'MATCHED_COMPLETE_SHADOW_PENDING') return 'good';
    if (status === 'MATCHED_PARTIAL' || status === 'MATCHED_PARTIAL_SHADOW_PENDING' || status === 'PLANNED_SHADOW_PENDING' || status === 'WAIT_SELLABLE_AT_PLAN') return 'warn';
    return 'bad';
  }

  function cycleStatusLabel(status) {
    return ({
      ACTUAL_COMPLETE: 'Đã nhập đủ fill',
      IN_PROGRESS: 'Đang thực hiện',
      OPEN: 'Chưa nhập fill',
      NO_TRADE_INTENT: 'Không có lệnh thực thi',
    })[status] || status || 'Chưa rõ';
  }

  function matchLabel(method) {
    if (!method) return 'Chưa ghép';
    if (method === 'AUTO_NEWEST_OPEN_INTENT') return 'Tự ghép';
    if (method === 'EXPLICIT_PLAN_ID') return 'Chọn đích danh';
    return String(method).replaceAll(',', ' + ');
  }

  function cycleIntentRows(cycle) {
    const intents = cycle.intents || [];
    if (!intents.length) return '<div class="v53-cycle-empty-intent">Cycle không có lệnh mua/bán.</div>';
    return `<div class="v53-cycle-intents">${intents.map(intent => {
      const blocked = intent.compliance_eligible === false || intent.excluded_from_compliance;
      return `
      <div class="v53-cycle-intent-row ${blocked ? 'v54-wait-sellable' : ''}">
        <div class="v53-intent-symbol"><strong>${esc(intent.side)} ${esc(intent.symbol)}</strong><small>${esc(humanStatus(intent.status))}</small></div>
        <div><span>${blocked ? 'Chờ bán' : 'Đề xuất'}</span><b>${num(intent.planned_quantity)} cp</b></div>
        <div><span>Đã nhập</span><b>${num(intent.actual_quantity)} cp</b></div>
        <div><span>Còn tính tuân thủ</span><b>${blocked ? '0 cp' : `${num(intent.remaining_quantity)} cp`}</b></div>
        <div><span>Cách ghép</span><b>${blocked ? 'Không áp dụng' : esc(matchLabel(intent.match_method))}</b></div>
        <div><span>Giá actual</span><b>${intent.actual_vwap_vnd ? money(intent.actual_vwap_vnd) : '—'}</b></div>
      </div>`;
    }).join('')}</div>`;
  }

  function cyclePanel(cycles) {
    if (!cycles?.length) return '<div class="empty">Không còn capital cycle vận hành.</div>';
    return `<div class="v51-cycle-grid">${cycles.map(cycle => `
      <article class="v51-cycle-card ${cycle.newest ? 'newest' : ''}" data-v54-cycle-card="${esc(cycle.plan_id)}">
        <div class="v51-cycle-head">
          <div class="v53-cycle-title">
            ${cycle.research_scope_eligible ? `<label class="v53-cycle-select"><input type="checkbox" data-v54-cycle-select value="${esc(cycle.plan_id)}"><span>Chọn</span></label>` : ''}
            <div><strong>${cycle.newest ? 'MỚI NHẤT' : 'CŨ'} · ${esc(cycle.created_at_vn)}</strong><small>${esc(cycle.cycle_id || cycle.week_key || '')}</small></div>
          </div>
          <div class="v52-cycle-actions">
            <span class="v51-pill ${cycle.status === 'ACTUAL_COMPLETE' ? 'good' : cycle.status === 'IN_PROGRESS' ? 'warn' : ''}">${esc(cycleStatusLabel(cycle.status))}</span>
            ${cycle.research_scope_eligible
              ? `<button type="button" class="danger v52-cycle-button" data-v54-research="${esc(cycle.plan_id)}">Loại khỏi đánh giá</button>`
              : '<span class="v52-lock-note">Đã thực hiện đủ · giữ trong đánh giá</span>'}
          </div>
        </div>
        <div class="v51-cycle-symbols">${esc((cycle.symbols || []).join(', ') || 'Không có mã mua/bán')}</div>
        <div class="v51-cycle-metrics">
          <span>Plan <b>…${esc(String(cycle.plan_id || '').slice(-6))}</b></span>
          <span>Đề xuất có thể thực hiện <b>${num(cycle.compliance_planned_quantity ?? cycle.planned_quantity)} cp</b></span>
          <span>Đã nhập <b>${num(cycle.actual_quantity)} cp</b></span>
          <span>Còn <b>${num(cycle.remaining_quantity)} cp</b></span>
          <span>Chờ cổ phiếu về <b>${num(cycle.wait_sellable_quantity)} cp</b></span>
          <span>Hoàn thành <b>${pct(cycle.completion_ratio)}</b></span>
          <span>Vốn cycle <b>${money(cycle.new_capital_vnd)}</b></span>
          <span>Shadow <b>${esc(cycle.shadow_status || '—')}</b></span>
        </div>
        ${cycle.research_scope_retroactive ? '<div class="notice warn compact-notice"><strong>Shadow đã được quan sát.</strong> Cycle vẫn có thể loại vì chưa thực hiện đủ, nhưng thao tác sẽ được ghi là điều chỉnh hậu nghiệm và dashboard sẽ gắn cờ phạm vi đánh giá đã được biên tập.</div>' : ''}
        ${cycle.discard_reassigns_auto_fills ? '<div class="notice warn compact-notice">Cycle có fill do tự ghép. Khi loại, fill thật không bị xóa; hệ thống sẽ ghép lại sang cycle vận hành khác hoặc đánh dấu ngoài kế hoạch.</div>' : ''}
        ${cycleIntentRows(cycle)}
      </article>`).join('')}</div>`;
  }

  function researchOnlyPanel(rows) {
    if (!rows?.length) return '';
    return `<details class="v52-discarded-panel v54-research-panel" open>
      <summary>Cycle chỉ dùng nghiên cứu đã loại (${rows.length})</summary>
      <div class="v52-discarded-list">${rows.map(row => `
        <article class="v52-discarded-card">
          <div>
            <strong>${esc(row.created_at_vn)} · plan …${esc(String(row.plan_id || '').slice(-6))}</strong>
            <small>${esc((row.symbols || []).join(', ') || 'Không có mã')} · lệnh thực thi ${num(row.compliance_planned_quantity)} cp · chờ bán ${num(row.wait_sellable_quantity)} cp</small>
            <small>Loại lúc ${esc(row.scope_action_time_vn || '—')} · ${esc(row.reason || '')}</small>
            ${row.retroactive ? '<small class="warn">Điều chỉnh sau khi shadow đã được quan sát · có rủi ro hindsight</small>' : ''}
          </div>
          <button type="button" class="secondary v52-cycle-button" data-v54-restore="${esc(row.plan_id)}">Đưa lại vào đánh giá</button>
        </article>`).join('')}</div>
    </details>`;
  }

  function legacyDiscardedPanel(rows) {
    if (!rows?.length) return '';
    return `<details class="v52-discarded-panel">
      <summary>Cycle đã bỏ theo cơ chế cũ (${rows.length})</summary>
      <div class="v52-discarded-list">${rows.map(row => `
        <article class="v52-discarded-card">
          <div>
            <strong>${esc(row.created_at_vn)} · plan …${esc(String(row.plan_id || '').slice(-6))}</strong>
            <small>${esc((row.symbols || []).join(', ') || 'Không có mã')} · ${num(row.planned_quantity)} cp</small>
            <small>Bỏ lúc ${esc(row.discarded_at_vn || row.discarded_at || '—')} · ${esc(row.reason || '')}</small>
          </div>
          ${row.restorable
            ? `<button type="button" class="secondary v52-cycle-button" data-v53-restore="${esc(row.plan_id)}">Khôi phục cơ chế cũ</button>`
            : '<span class="v52-lock-note">Shadow đã được quan sát · không khôi phục theo cơ chế cũ</span>'}
        </article>`).join('')}</div>
    </details>`;
  }

  function bulkToolbar(data) {
    const cycles = (data.cycle_catalog || []).filter(row => row.research_scope_eligible);
    if (!cycles.length) return '<div class="notice compact-notice">Không có cycle chưa hoàn thành để loại khỏi đánh giá.</div>';
    return `<div class="v53-bulk-toolbar">
      <div><strong>Loại nhiều cycle khỏi đánh giá</strong><small>${cycles.length} cycle chưa hoàn thành. Cycle đã mua đủ được khóa.</small></div>
      <div class="inline-actions">
        <button type="button" class="secondary" data-v54-select-all>Chọn tất cả chưa đủ</button>
        <button type="button" class="secondary" data-v54-clear-selection>Bỏ chọn</button>
        <button type="button" class="danger" data-v54-bulk-research disabled>Loại cycle đã chọn (<span data-v54-selected-count>0</span>)</button>
      </div>
    </div>`;
  }

  function scopeWarning(data) {
    if (!data.operational_scope_curated) return '';
    return `<div class="notice warn v54-scope-warning"><strong>Phạm vi đánh giá vận hành đã được biên tập hậu nghiệm.</strong>
      <div>${num(data.retroactive_research_only_count)} cycle được loại sau khi shadow đã quan sát. Chỉ số vận hành hiện tại là chỉ số đã làm sạch theo xác nhận của người dùng, không còn là chuỗi out-of-sample nguyên bản.</div></div>`;
  }

  function reconciliationCards(rows) {
    if (!rows?.length) return '<div class="empty">Chưa có plan intent hoặc fill thực tế để đối soát.</div>';
    return `<div class="performance-reconcile-grid">${rows.slice().reverse().map(row => `
      <article class="performance-reconcile-card v51-reconcile-card">
        <div class="security-head">
          <div><strong>${esc(row.side)} ${esc(row.symbol)}</strong><small>${row.cycle_created_at_vn ? `${esc(row.cycle_created_at_vn)} · plan …${esc(String(row.plan_id || '').slice(-6))}` : 'Không có plan intent phù hợp'}</small></div>
          <span class="${statusClass(row.status)}">${esc(humanStatus(row.status))}</span>
        </div>
        <div class="metric-grid">
          <div><span>Đề xuất / thực tế</span><strong>${num(row.planned_quantity)} / ${num(row.actual_quantity)} cp</strong></div>
          <div><span>Còn thiếu</span><strong>${num(row.remaining_quantity)} cp</strong></div>
          <div><span>Tuân thủ số lượng</span><strong>${row.quantity_compliance === null || row.quantity_compliance === undefined ? '—' : pct(row.quantity_compliance)}</strong></div>
          <div><span>Cách ghép</span><strong>${esc(matchLabel(row.match_method))}</strong></div>
          <div><span>Giá actual VWAP</span><strong>${row.actual_vwap_vnd ? money(row.actual_vwap_vnd) : 'Chưa có'}</strong></div>
          <div><span>Shadow</span><strong>${row.shadow_pending ? `Chờ ${esc(row.shadow_execution_day || 'T+1')}` : `${num(row.shadow_quantity)} cp @ ${money(row.shadow_price_vnd)}`}</strong></div>
          <div><span>Độ trễ actual</span><strong>${row.execution_delay_days === null || row.execution_delay_days === undefined ? '—' : `${num(row.execution_delay_days)} ngày`}</strong></div>
          <div><span>Slippage</span><strong>${pct(row.price_slippage)}</strong></div>
        </div>
        ${row.unmatched_reason ? `<div class="v51-unmatched-reason">${esc(row.unmatched_reason)}</div>` : ''}
      </article>`).join('')}</div>`;
  }

  function findReconciliationSection() {
    return [...document.querySelectorAll('#performance .dashboard-output-section')]
      .find(section => section.querySelector('h3')?.textContent?.includes('Đối soát actual')) || null;
  }

  function renderCycleSection(data) {
    const reconciliation = findReconciliationSection();
    if (!reconciliation) return;
    let section = document.querySelector('#v51-cycle-section');
    if (!section) {
      section = document.createElement('section');
      section.id = 'v51-cycle-section';
      section.className = 'dashboard-output-section';
      reconciliation.parentNode.insertBefore(section, reconciliation);
    }
    section.innerHTML = `
      <div class="section-head"><div><h3>Capital cycle và phạm vi đánh giá</h3><p>Cycle chưa hoàn thành có thể được xác nhận là chỉ dùng nghiên cứu, kể cả cycle cũ đã chạy shadow. Actual fill và plan gốc không bị xóa.</p></div><span class="badge good">${CYCLE_VERSION}</span></div>
      <div id="v52-cycle-command-notice" class="notice compact-notice">Lệnh bán khi cổ phiếu chưa thể bán được giữ để audit nhưng không tính là không tuân thủ và không được shadow thực thi.</div>
      ${scopeWarning(data)}
      ${bulkToolbar(data)}
      ${cyclePanel(data.cycle_catalog || [])}
      ${researchOnlyPanel(data.research_only_cycle_catalog || [])}
      ${legacyDiscardedPanel(data.discarded_cycle_catalog || [])}`;
    updateSelectionState();
  }

  function renderReconciliation(data) {
    const section = findReconciliationSection();
    if (!section) return;
    const oldGrid = section.querySelector('.performance-reconcile-grid, .empty');
    const wrapper = document.createElement('div');
    wrapper.innerHTML = reconciliationCards(data.reconciliation || []);
    if (oldGrid) oldGrid.replaceWith(wrapper.firstElementChild);
    else section.appendChild(wrapper.firstElementChild);
    const paragraph = section.querySelector('.section-head p');
    if (paragraph) paragraph.textContent = 'Chỉ đối soát cycle vận hành; cycle nghiên cứu và lệnh WAIT_SELLABLE không nằm trong mẫu tuân thủ.';
  }

  function relevantCycles(symbol, side) {
    const cycles = latest?.cycle_catalog || [];
    if (!symbol) return cycles;
    return cycles.filter(cycle => (cycle.intents || []).some(intent =>
      intent.compliance_eligible !== false
      && intent.symbol === symbol
      && intent.side === side
      && Number(intent.remaining_quantity || 0) > 0
    ));
  }

  function fillCycleOptions() {
    const select = document.querySelector('#performance-fill-plan');
    const symbolInput = document.querySelector('#performance-fill-symbol');
    const sideInput = document.querySelector('#performance-fill-side');
    if (!select || !latest) return;
    const oldValue = select.value;
    const symbol = String(symbolInput?.value || '').trim().toUpperCase();
    const side = String(sideInput?.value || 'BUY').toUpperCase();
    const matching = relevantCycles(symbol, side);
    const cycles = symbol ? matching : (latest.cycle_catalog || []);
    select.innerHTML = '<option value="">Tự ghép cycle vận hành mới nhất còn thiếu theo mã</option>' + cycles.map(cycle => {
      const intent = (cycle.intents || []).find(row => row.compliance_eligible !== false && row.symbol === symbol && row.side === side);
      const extra = intent ? ` · đề xuất ${intent.planned_quantity} · còn ${intent.remaining_quantity} cp` : '';
      return `<option value="${esc(cycle.plan_id)}" ${cycle.remaining_quantity <= 0 ? 'disabled' : ''}>${esc((cycle.display_label || cycle.created_at_vn || cycle.plan_id) + extra)}</option>`;
    }).join('');
    if ([...select.options].some(option => option.value === oldValue && !option.disabled)) {
      select.value = oldValue;
    } else if (symbol && matching.length === 1) {
      select.value = matching[0].plan_id;
    }

    let help = document.querySelector('#v51-cycle-help');
    if (!help) {
      help = document.createElement('div');
      help.id = 'v51-cycle-help';
      help.className = 'v51-cycle-help';
      select.closest('label')?.appendChild(help);
    }
    if (!symbol) {
      help.textContent = 'Nhập mã trước; hệ thống chỉ lọc cycle vận hành có lệnh thực thi còn thiếu.';
      help.className = 'v51-cycle-help';
    } else if (matching.length === 1) {
      help.textContent = `Tự chọn: ${matching[0].display_label || matching[0].created_at_vn}`;
      help.className = 'v51-cycle-help good';
    } else if (matching.length > 1) {
      help.textContent = `Có ${matching.length} cycle vận hành còn thiếu ${symbol}. Chọn theo giờ tạo và số lượng.`;
      help.className = 'v51-cycle-help warn';
    } else {
      help.textContent = `Không có cycle vận hành còn thiếu ${side} ${symbol}. Fill sẽ được đánh dấu ngoài kế hoạch nếu vẫn ghi.`;
      help.className = 'v51-cycle-help bad';
    }
  }

  function clarifyCapitalInput() {
    const input = document.querySelector('#dashboard-budget');
    if (!input) return;
    input.min = '0';
    const label = input.closest('label');
    if (label && !label.querySelector('.v51-capital-help')) {
      const help = document.createElement('small');
      help.className = 'v51-capital-help';
      help.textContent = 'Nhập 0 khi tiền đã xuất hiện trong DNSE. Chỉ nhập phần tiền chưa nằm trong số dư DNSE.';
      label.appendChild(help);
    }
  }

  function renderCashIntegrity(broker) {
    const target = document.querySelector('#v49-broker-summary');
    if (!target || !broker?.cash_integrity) return;
    target.querySelector('.v51-cash-contract')?.remove();
    const cash = broker.cash_integrity;
    const rejected = String(cash.status || '').includes('REJECT_AVAILABLE_EXCEEDS_TOTAL_CASH');
    const notice = document.createElement('div');
    notice.className = `notice v51-cash-contract ${rejected ? 'warn' : 'good'}`;
    notice.innerHTML = `<strong>${rejected ? 'Đã loại số availableCash bất hợp lý' : 'Cash contract hợp lệ'}</strong>
      <div>Planner dùng ${money(cash.planner_cash_vnd)}. totalCash báo cáo ${money(cash.reported_total_cash_vnd)}; availableCash thô ${money(cash.reported_available_cash_vnd)}.</div>
      <div class="technical">${esc(cash.status)} · PPSE tắt theo lựa chọn V49</div>`;
    target.prepend(notice);
  }

  const previousRenderPortfolio = window.renderPortfolio;
  if (typeof previousRenderPortfolio === 'function') {
    window.renderPortfolio = function renderPortfolioV54(broker, account) {
      previousRenderPortfolio(broker, account);
      renderCashIntegrity(broker);
    };
  }

  function render(data) {
    latest = data;
    renderCycleSection(data);
    renderReconciliation(data);
    fillCycleOptions();
    clarifyCapitalInput();
    renderCashIntegrity(data.latest_broker);
  }

  async function refreshV54() {
    const data = await request('/api/performance');
    render(data);
    return data;
  }

  function commandNotice(text, cls = '') {
    const notice = document.querySelector('#v52-cycle-command-notice');
    if (!notice) return;
    notice.textContent = text;
    notice.className = `notice compact-notice ${cls}`;
  }

  function selectedPlanIds() {
    return [...document.querySelectorAll('[data-v54-cycle-select]:checked')]
      .map(input => input.value)
      .filter(Boolean);
  }

  function updateSelectionState() {
    const selected = selectedPlanIds();
    const count = document.querySelector('[data-v54-selected-count]');
    const button = document.querySelector('[data-v54-bulk-research]');
    if (count) count.textContent = String(selected.length);
    if (button) button.disabled = commandBusy || selected.length === 0;
  }

  function setCommandBusy(value) {
    commandBusy = value;
    document.querySelectorAll('[data-v54-research], [data-v54-restore], [data-v54-bulk-research], [data-v53-restore]')
      .forEach(button => { button.disabled = value; });
    updateSelectionState();
  }

  async function runResearchOnly(planIds) {
    if (commandBusy || !planIds.length) return;
    const reason = window.prompt(
      planIds.length > 1 ? `Lý do loại ${planIds.length} cycle khỏi đánh giá:` : 'Lý do loại cycle khỏi đánh giá:',
      'Cycle chỉ dùng để quan sát thị trường, không phải kế hoạch thực hiện',
    );
    if (reason === null) return;
    if (!String(reason).trim()) {
      window.alert('Phải nhập lý do để lưu audit.');
      return;
    }
    const hasRetroactive = planIds.some(planId => latest?.cycle_catalog?.find(row => row.plan_id === planId)?.research_scope_retroactive);
    const warning = hasRetroactive
      ? '\n\nCó cycle đã chạy shadow. Dashboard sẽ ghi rõ đây là điều chỉnh hậu nghiệm; lịch sử gốc không bị xóa.'
      : '';
    if (!window.confirm(`Loại ${planIds.length} cycle khỏi đánh giá vận hành? Actual fill vẫn được giữ và ghép lại.${warning}`)) return;

    setCommandBusy(true);
    commandNotice(`Đang phân loại ${planIds.length} cycle là research-only và rebuild đánh giá...`, 'warn');
    try {
      const result = await request('/api/performance/cashflow', {
        method: 'POST',
        body: JSON.stringify({
          flow_type: planIds.length > 1 ? 'MARK_RESEARCH_ONLY_BULK' : 'MARK_RESEARCH_ONLY',
          amount_vnd: 0,
          event_day: vnDay(),
          note: JSON.stringify({
            plan_id: planIds[0],
            plan_ids: planIds,
            reason: String(reason).trim(),
          }),
        }),
      });
      setCommandBusy(false);
      await refreshV54();
      commandNotice(result.message || 'Hoàn tất.', 'good');
    } catch (error) {
      setCommandBusy(false);
      commandNotice(error.message, 'bad');
      window.alert(error.message);
    }
  }

  async function runOperationalRestore(planId) {
    if (commandBusy || !planId) return;
    const reason = window.prompt('Lý do đưa cycle trở lại đánh giá vận hành:', 'Xác nhận đây là cycle thực sự muốn thực hiện');
    if (reason === null) return;
    if (!String(reason).trim()) {
      window.alert('Phải nhập lý do để lưu audit.');
      return;
    }
    setCommandBusy(true);
    commandNotice('Đang đưa cycle trở lại và rebuild đánh giá...', 'warn');
    try {
      const result = await request('/api/performance/cashflow', {
        method: 'POST',
        body: JSON.stringify({
          flow_type: 'RESTORE_OPERATIONAL',
          amount_vnd: 0,
          event_day: vnDay(),
          note: JSON.stringify({plan_id: planId, reason: String(reason).trim()}),
        }),
      });
      setCommandBusy(false);
      await refreshV54();
      commandNotice(result.message || 'Hoàn tất.', 'good');
    } catch (error) {
      setCommandBusy(false);
      commandNotice(error.message, 'bad');
      window.alert(error.message);
    }
  }

  async function runLegacyRestore(planId) {
    if (commandBusy || !planId) return;
    const reason = window.prompt('Lý do khôi phục cycle cơ chế cũ:', 'Khôi phục cycle để tiếp tục theo dõi');
    if (reason === null || !String(reason).trim()) return;
    setCommandBusy(true);
    try {
      const result = await request('/api/performance/cashflow', {
        method: 'POST',
        body: JSON.stringify({
          flow_type: 'RESTORE_CYCLE',
          amount_vnd: 0,
          event_day: vnDay(),
          note: JSON.stringify({plan_id: planId, reason: String(reason).trim()}),
        }),
      });
      setCommandBusy(false);
      await refreshV54();
      commandNotice(result.message || 'Hoàn tất.', 'good');
    } catch (error) {
      setCommandBusy(false);
      commandNotice(error.message, 'bad');
      window.alert(error.message);
    }
  }

  function scheduleRefresh(delay = 250) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => {
      refreshV54().catch(error => {
        const notice = document.querySelector('#performance-notice');
        if (notice) {
          notice.textContent = error.message;
          notice.className = 'notice bad';
        }
      });
    }, delay);
  }

  function init() {
    clarifyCapitalInput();
    document.addEventListener('input', event => {
      if (event.target?.matches?.('#performance-fill-symbol, #performance-fill-side')) fillCycleOptions();
    });
    document.addEventListener('change', event => {
      if (event.target?.matches?.('#performance-fill-symbol, #performance-fill-side')) fillCycleOptions();
      if (event.target?.matches?.('[data-v54-cycle-select]')) updateSelectionState();
    });
    document.addEventListener('click', event => {
      const research = event.target?.closest?.('[data-v54-research]');
      if (research) {
        event.preventDefault();
        runResearchOnly([research.dataset.v54Research]);
        return;
      }
      const restore = event.target?.closest?.('[data-v54-restore]');
      if (restore) {
        event.preventDefault();
        runOperationalRestore(restore.dataset.v54Restore);
        return;
      }
      const legacyRestore = event.target?.closest?.('[data-v53-restore]');
      if (legacyRestore) {
        event.preventDefault();
        runLegacyRestore(legacyRestore.dataset.v53Restore);
        return;
      }
      if (event.target?.closest?.('[data-v54-select-all]')) {
        event.preventDefault();
        document.querySelectorAll('[data-v54-cycle-select]').forEach(input => { input.checked = true; });
        updateSelectionState();
        return;
      }
      if (event.target?.closest?.('[data-v54-clear-selection]')) {
        event.preventDefault();
        document.querySelectorAll('[data-v54-cycle-select]').forEach(input => { input.checked = false; });
        updateSelectionState();
        return;
      }
      if (event.target?.closest?.('[data-v54-bulk-research]')) {
        event.preventDefault();
        runResearchOnly(selectedPlanIds());
        return;
      }
      if (event.target?.closest?.('[data-v45-performance-tab], #performance-refresh, #performance-add-fill, [data-action="plan"], [data-action="sync-broker"]')) {
        scheduleRefresh(700);
      }
    });
    scheduleRefresh(250);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
