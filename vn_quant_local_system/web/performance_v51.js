(() => {
  const VERSION = 'V51_INTENT_RECONCILIATION_CASH_INTEGRITY';
  const CYCLE_VERSION = 'V52_AUDITABLE_CYCLE_DISCARD';
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
  let observer = null;
  let refreshTimer = null;
  let commandBusy = false;

  async function request(path, options = {}) {
    const response = await fetch(path, {
      headers: {'Content-Type': 'application/json'},
      ...options,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || data.error || 'Yêu cầu thất bại');
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
    })[status] || status || 'CHƯA XÁC ĐỊNH';
  }

  function statusClass(status) {
    if (status === 'MATCHED_COMPLETE' || status === 'MATCHED_COMPLETE_SHADOW_PENDING') return 'good';
    if (status === 'MATCHED_PARTIAL' || status === 'MATCHED_PARTIAL_SHADOW_PENDING' || status === 'PLANNED_SHADOW_PENDING') return 'warn';
    return 'bad';
  }

  function cycleStatusLabel(status) {
    return ({
      ACTUAL_COMPLETE: 'Đã nhập đủ fill',
      IN_PROGRESS: 'Đang thực hiện',
      OPEN: 'Chưa nhập fill',
      NO_TRADE_INTENT: 'Không có lệnh',
    })[status] || status || 'Chưa rõ';
  }

  function cyclePanel(cycles) {
    if (!cycles?.length) return '<div class="empty">Không còn capital cycle đang hoạt động.</div>';
    return `<div class="v51-cycle-grid">${cycles.map(cycle => {
      const canDiscard = Number(cycle.actual_quantity || 0) === 0;
      return `
      <article class="v51-cycle-card ${cycle.newest ? 'newest' : ''}">
        <div class="v51-cycle-head">
          <div><strong>${cycle.newest ? 'MỚI NHẤT' : 'CŨ'} · ${esc(cycle.created_at_vn)}</strong><small>${esc(cycle.cycle_id || cycle.week_key || '')}</small></div>
          <div class="v52-cycle-actions">
            <span class="v51-pill ${cycle.status === 'ACTUAL_COMPLETE' ? 'good' : cycle.status === 'IN_PROGRESS' ? 'warn' : ''}">${esc(cycleStatusLabel(cycle.status))}</span>
            ${canDiscard
              ? `<button type="button" class="danger v52-cycle-button" data-v52-discard="${esc(cycle.plan_id)}">Bỏ cycle</button>`
              : '<span class="v52-lock-note">Có actual fill · không thể bỏ</span>'}
          </div>
        </div>
        <div class="v51-cycle-symbols">${esc((cycle.symbols || []).join(', ') || 'Không có mã mua/bán')}</div>
        <div class="v51-cycle-metrics">
          <span>Plan <b>…${esc(String(cycle.plan_id || '').slice(-6))}</b></span>
          <span>Đề xuất <b>${num(cycle.planned_quantity)} cp</b></span>
          <span>Đã nhập <b>${num(cycle.actual_quantity)} cp</b></span>
          <span>Còn <b>${num(cycle.remaining_quantity)} cp</b></span>
          <span>Vốn cycle <b>${money(cycle.new_capital_vnd)}</b></span>
          <span>Shadow <b>${esc(cycle.shadow_status || '—')}</b></span>
        </div>
      </article>`;
    }).join('')}</div>`;
  }

  function discardedPanel(rows) {
    if (!rows?.length) return '';
    return `<details class="v52-discarded-panel">
      <summary>Cycle đã bỏ (${rows.length}) · mở để xem audit hoặc khôi phục</summary>
      <div class="v52-discarded-list">${rows.map(row => `
        <article class="v52-discarded-card">
          <div>
            <strong>${esc(row.created_at_vn)} · plan …${esc(String(row.plan_id || '').slice(-6))}</strong>
            <small>${esc((row.symbols || []).join(', ') || 'Không có mã')} · ${num(row.planned_quantity)} cp</small>
            <small>Bỏ lúc ${esc(row.discarded_at_vn || row.discarded_at || '—')} · ${esc(row.reason || '')}</small>
          </div>
          <button type="button" class="secondary v52-cycle-button" data-v52-restore="${esc(row.plan_id)}">Khôi phục</button>
        </article>`).join('')}</div>
    </details>`;
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
          <div><span>Cách ghép</span><strong>${esc(row.match_method || 'Không ghép')}</strong></div>
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
      <div class="section-head"><div><h3>Capital cycle và plan intent</h3><p>Cycle không thực hiện có thể bỏ khỏi vận hành. Cycle có actual fill được khóa để bảo vệ lịch sử.</p></div><span class="badge good">${CYCLE_VERSION}</span></div>
      <div id="v52-cycle-command-notice" class="notice compact-notice">Bỏ cycle chỉ loại khỏi đối soát và shadow; lịch sử gốc vẫn giữ audit.</div>
      ${cyclePanel(data.cycle_catalog || [])}
      ${discardedPanel(data.discarded_cycle_catalog || [])}`;
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
    if (paragraph) paragraph.textContent = 'Ghép actual với plan intent ngay khi plan được tạo; cycle đã bỏ không còn sinh intent hoặc shadow chờ.';
  }

  function relevantCycles(symbol, side) {
    const cycles = latest?.cycle_catalog || [];
    if (!symbol) return cycles;
    return cycles.filter(cycle => (cycle.intents || []).some(intent =>
      intent.symbol === symbol && intent.side === side && Number(intent.remaining_quantity || 0) > 0
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
    select.innerHTML = '<option value="">Tự ghép cycle mới nhất còn thiếu theo mã</option>' + cycles.map(cycle => {
      const intent = (cycle.intents || []).find(row => row.symbol === symbol && row.side === side);
      const extra = intent ? ` · đề xuất ${intent.planned_quantity} · còn ${intent.remaining_quantity} cp` : '';
      return `<option value="${esc(cycle.plan_id)}" ${cycle.remaining_quantity <= 0 ? 'disabled' : ''}>${esc(cycle.display_label + extra)}</option>`;
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
      help.textContent = 'Nhập mã trước; hệ thống sẽ lọc cycle đang hoạt động có đúng mã và chiều giao dịch.';
      help.className = 'v51-cycle-help';
    } else if (matching.length === 1) {
      help.textContent = `Tự chọn: ${matching[0].display_label}`;
      help.className = 'v51-cycle-help good';
    } else if (matching.length > 1) {
      help.textContent = `Có ${matching.length} cycle còn thiếu ${symbol}. Chọn theo giờ tạo và số lượng còn thiếu.`;
      help.className = 'v51-cycle-help warn';
    } else {
      help.textContent = `Không có cycle đang hoạt động còn thiếu ${side} ${symbol}. Fill sẽ được đánh dấu ngoài kế hoạch nếu vẫn ghi.`;
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
    window.renderPortfolio = function renderPortfolioV51(broker, account) {
      previousRenderPortfolio(broker, account);
      renderCashIntegrity(broker);
    };
  }

  function render(data) {
    latest = data;
    if (observer) observer.disconnect();
    try {
      renderCycleSection(data);
      renderReconciliation(data);
      fillCycleOptions();
      clarifyCapitalInput();
      renderCashIntegrity(data.latest_broker);
    } finally {
      const content = document.querySelector('#performance-content');
      if (content && observer) observer.observe(content, {childList: true, subtree: true});
    }
  }

  async function refreshV51() {
    try {
      const data = await request('/api/performance');
      render(data);
    } catch (error) {
      const notice = document.querySelector('#performance-notice');
      if (notice) {
        notice.textContent = error.message;
        notice.className = 'notice bad';
      }
    }
  }

  function commandNotice(text, cls = '') {
    const notice = document.querySelector('#v52-cycle-command-notice');
    if (!notice) return;
    notice.textContent = text;
    notice.className = `notice compact-notice ${cls}`;
  }

  async function runCycleCommand(kind, planId) {
    if (commandBusy) return;
    const isDiscard = kind === 'DISCARD_CYCLE';
    const defaultReason = isDiscard
      ? 'Chỉ xem tổng quan, không thực hiện kế hoạch'
      : 'Khôi phục cycle để tiếp tục theo dõi';
    const reason = window.prompt(
      isDiscard ? 'Lý do bỏ cycle:' : 'Lý do khôi phục cycle:',
      defaultReason,
    );
    if (reason === null) return;
    if (!String(reason).trim()) {
      window.alert('Phải nhập lý do để lưu audit.');
      return;
    }
    if (isDiscard && !window.confirm('Cycle sẽ biến khỏi danh sách hoạt động và toàn bộ shadow/intent chờ tương ứng sẽ được rebuild bỏ đi. Tiếp tục?')) return;
    commandBusy = true;
    commandNotice(isDiscard ? 'Đang bỏ cycle và rebuild shadow...' : 'Đang khôi phục cycle và rebuild shadow...', 'warn');
    try {
      const result = await request('/api/performance/cashflow', {
        method: 'POST',
        body: JSON.stringify({
          flow_type: kind,
          amount_vnd: 0,
          event_day: vnDay(),
          note: JSON.stringify({plan_id: planId, reason: String(reason).trim()}),
        }),
      });
      await refreshV51();
      commandNotice(result.message || 'Hoàn tất.', 'good');
    } catch (error) {
      commandNotice(error.message, 'bad');
      window.alert(error.message);
    } finally {
      commandBusy = false;
    }
  }

  function scheduleRefresh(delay = 250) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refreshV51, delay);
  }

  function init() {
    clarifyCapitalInput();
    const content = document.querySelector('#performance-content');
    observer = new MutationObserver(() => scheduleRefresh(120));
    if (content) observer.observe(content, {childList: true, subtree: true});
    document.addEventListener('input', event => {
      if (event.target?.matches?.('#performance-fill-symbol, #performance-fill-side')) fillCycleOptions();
    });
    document.addEventListener('change', event => {
      if (event.target?.matches?.('#performance-fill-symbol, #performance-fill-side')) fillCycleOptions();
    });
    document.addEventListener('click', event => {
      const discard = event.target?.closest?.('[data-v52-discard]');
      if (discard) {
        event.preventDefault();
        runCycleCommand('DISCARD_CYCLE', discard.dataset.v52Discard);
        return;
      }
      const restore = event.target?.closest?.('[data-v52-restore]');
      if (restore) {
        event.preventDefault();
        runCycleCommand('RESTORE_CYCLE', restore.dataset.v52Restore);
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
