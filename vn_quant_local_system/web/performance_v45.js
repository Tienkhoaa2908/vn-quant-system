(() => {
  const money = value => Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits: 0}) + ' ₫';
  const pct = value => value === null || value === undefined ? 'Chưa đủ dữ liệu' : (Number(value) * 100).toFixed(2) + '%';
  const num = value => Number(value || 0).toLocaleString('vi-VN', {maximumFractionDigits: 2});
  const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  const today = () => new Date().toISOString().slice(0, 10);
  let performanceState = null;

  async function request(path, options = {}) {
    const response = await fetch(path, {headers: {'Content-Type': 'application/json'}, ...options});
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || data.error || 'Yêu cầu thất bại');
    return data;
  }

  function addTab() {
    const nav = document.querySelector('.tabs-nav');
    const docsButton = nav?.querySelector('[data-tab="docs"]');
    if (!nav || document.querySelector('[data-v45-performance-tab]')) return;
    const button = document.createElement('button');
    button.textContent = 'Hiệu quả';
    button.dataset.v45PerformanceTab = 'true';
    nav.insertBefore(button, docsButton || null);
    button.addEventListener('click', () => {
      document.querySelectorAll('.tabs-nav button').forEach(item => item.classList.remove('active'));
      document.querySelectorAll('main > .tab').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      document.querySelector('#performance')?.classList.add('active');
      loadPerformance();
    });

    const section = document.createElement('section');
    section.id = 'performance';
    section.className = 'tab';
    section.innerHTML = `
      <div class="section-head performance-title-row">
        <div>
          <p class="eyebrow">V45 LIVE PERFORMANCE OBSERVATORY</p>
          <h2>Theo dõi hiệu quả thực tế</h2>
          <p>Tách toàn tài khoản DNSE, actual model sleeve, plan shadow và VNINDEX benchmark.</p>
        </div>
        <button id="performance-refresh" class="secondary">Cập nhật hiệu quả</button>
      </div>
      <div id="performance-notice" class="notice">Đang tải trạng thái...</div>
      <div id="performance-content"></div>`;
    const docs = document.querySelector('#docs');
    docs?.parentNode?.insertBefore(section, docs);
    section.querySelector('#performance-refresh').addEventListener('click', refreshPerformance);
  }

  function summaryCard(label, stream, description) {
    if (!stream) {
      return `<article class="performance-summary-card"><span>${esc(label)}</span><strong>Chưa có dữ liệu</strong><small>${esc(description)}</small></article>`;
    }
    return `<article class="performance-summary-card">
      <span>${esc(label)}</span>
      <strong>${money(stream.latest_nav_vnd)}</strong>
      <div class="performance-metrics">
        <b class="${Number(stream.cumulative_return) >= 0 ? 'positive' : 'negative'}">TWR ${pct(stream.cumulative_return)}</b>
        <b>XIRR ${pct(stream.xirr)}</b>
        <b>Max DD ${pct(stream.max_drawdown)}</b>
      </div>
      <small>${esc(description)} · ${esc(stream.latest_day || '')}</small>
    </article>`;
  }

  function lineChart(series) {
    const names = [
      ['ACTUAL_MODEL_SLEEVE', 'Actual model sleeve'],
      ['PLAN_SHADOW', 'Plan shadow'],
      ['VNINDEX_BENCHMARK', 'VNINDEX benchmark'],
    ];
    const available = names.map(([key, label], index) => ({key, label, index, rows: series?.[key] || []})).filter(item => item.rows.length);
    if (!available.length) return '<div class="empty">Chưa có chuỗi lợi nhuận để vẽ.</div>';
    const allValues = available.flatMap(item => item.rows.map(row => Number(row.cumulative_return || 0)));
    const min = Math.min(...allValues, -0.01);
    const max = Math.max(...allValues, 0.01);
    const span = Math.max(max - min, 0.01);
    const width = 980;
    const height = 300;
    const padding = 34;
    const colors = ['#62d7ff', '#6bf0a4', '#f6ca68'];
    const paths = available.map(item => {
      const points = item.rows.map((row, i) => {
        const x = padding + (width - padding * 2) * (item.rows.length === 1 ? 0 : i / (item.rows.length - 1));
        const y = height - padding - (height - padding * 2) * ((Number(row.cumulative_return || 0) - min) / span);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
      return `<polyline points="${points}" fill="none" stroke="${colors[item.index]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>`;
    }).join('');
    const zeroY = height - padding - (height - padding * 2) * ((0 - min) / span);
    const legend = available.map(item => `<span><i style="background:${colors[item.index]}"></i>${esc(item.label)}</span>`).join('');
    return `<div class="performance-chart-wrap">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Biểu đồ lợi nhuận tích lũy">
        <line x1="${padding}" y1="${zeroY}" x2="${width - padding}" y2="${zeroY}" stroke="rgba(255,255,255,.18)" stroke-dasharray="5 5"/>
        ${paths}
        <text x="8" y="${padding}" fill="#8fa9cf" font-size="13">${pct(max)}</text>
        <text x="8" y="${height - padding}" fill="#8fa9cf" font-size="13">${pct(min)}</text>
      </svg>
      <div class="performance-legend">${legend}</div>
    </div>`;
  }

  function classificationRows(broker) {
    const positions = broker?.positions || [];
    if (!positions.length) return '<div class="empty">Snapshot DNSE không có cổ phiếu. Observatory vẫn có thể bắt đầu bằng tiền mặt.</div>';
    return `<div class="performance-classification-grid">${positions.map(position => `
      <article class="performance-position-classification" data-symbol="${esc(position.symbol)}">
        <div><strong>${esc(position.symbol)}</strong><span>${num(position.quantity)} cp · ${money(position.market_value_vnd)}</span></div>
        <select class="performance-classification">
          <option value="LEGACY_EXCLUDED" selected>Legacy — loại khỏi model sleeve</option>
          <option value="ADOPTED_AT_START">Adopt — giao cho policy từ ngày bắt đầu</option>
        </select>
      </article>`).join('')}</div>`;
  }

  function renderNotStarted(data) {
    const broker = data.broker;
    const brokerCash = Number(broker?.planner_cash_vnd || 0);
    const startDay = broker?.market_day || today();
    document.querySelector('#performance-content').innerHTML = `
      <div class="performance-explainer-grid">
        <article><strong>Whole DNSE</strong><span>Toàn bộ tài sản thật, gồm cả vị thế cũ.</span></article>
        <article><strong>Actual model sleeve</strong><span>Chỉ dòng tiền và fill được xác nhận thuộc chiến lược.</span></article>
        <article><strong>Plan shadow</strong><span>Plan đầu tiên mỗi tuần, khớp T+1 open.</span></article>
        <article><strong>Signal scorecard</strong><span>Đánh giá C3 độc lập với việc có mua hay không.</span></article>
      </div>
      <div class="panel performance-start-panel">
        <h3>Chốt snapshot mở đầu bất biến</h3>
        <p>Mặc định mọi cổ phiếu đang có được coi là legacy và không làm sai kết quả model. Chỉ chọn Adopt khi muốn policy quản lý vị thế đó từ ngày bắt đầu.</p>
        <div class="form-grid">
          <label>Ngày bắt đầu<input id="performance-start-day" type="date" value="${esc(startDay)}"></label>
          <label>Tiền mặt đưa vào model sleeve<input id="performance-opening-cash" type="number" min="0" step="1000" value="${brokerCash}"></label>
        </div>
        ${classificationRows(broker)}
        <div class="inline-actions"><button id="performance-start">Bắt đầu theo dõi từ snapshot này</button></div>
        <div class="research-note">Snapshot mở đầu không có nút sửa hoặc xóa. Giá vốn lịch sử không được dùng để tính hiệu quả model; vị thế Adopt được đánh dấu lại theo giá thị trường tại ngày bắt đầu.</div>
      </div>`;
    document.querySelector('#performance-start')?.addEventListener('click', startPerformance);
  }

  function reconciliationCards(rows) {
    if (!rows?.length) return '<div class="empty">Chưa có plan shadow hoặc fill thực tế để đối soát.</div>';
    return `<div class="performance-reconcile-grid">${rows.slice().reverse().map(row => {
      const statusClass = row.status === 'EXECUTED' ? 'positive' : row.status === 'PARTIALLY_EXECUTED' ? 'warning' : 'negative';
      return `<article class="performance-reconcile-card">
        <div class="security-head"><strong>${esc(row.side)} ${esc(row.symbol)}</strong><span class="${statusClass}">${esc(row.status)}</span></div>
        <div class="metric-grid">
          <div><span>Plan</span><strong>${esc(row.plan_id || 'Không ghép')}</strong></div>
          <div><span>Đề xuất / thực tế</span><strong>${num(row.proposed_quantity)} / ${num(row.actual_quantity)} cp</strong></div>
          <div><span>Giá shadow</span><strong>${money(row.shadow_price_vnd)}</strong></div>
          <div><span>Giá thực tế</span><strong>${row.actual_price_vnd ? money(row.actual_price_vnd) : 'Chưa có'}</strong></div>
          <div><span>Độ trễ</span><strong>${row.execution_delay_days === null ? '—' : num(row.execution_delay_days) + ' ngày'}</strong></div>
          <div><span>Slippage</span><strong>${pct(row.price_slippage)}</strong></div>
        </div>
      </article>`;
    }).join('')}</div>`;
  }

  function scorecardRows(rows) {
    if (!rows?.length) return '<div class="empty">Chưa có signal phát sinh sau ngày bắt đầu hoặc chưa đủ forward horizon.</div>';
    return `<div class="performance-score-grid">${rows.slice().reverse().map(item => `
      <article class="performance-score-card">
        <div class="security-head"><strong>Signal ${esc(item.signal_day)}</strong><span>${esc(item.run_id)}</span></div>
        <div class="performance-horizons">${['1W', '1M', '3M'].map(label => {
          const horizon = item.horizons?.[label] || {};
          return `<div><span>${label}</span>${horizon.status === 'COMPLETE'
            ? `<strong class="${Number(horizon.top10_excess_return) >= 0 ? 'positive' : 'negative'}">Excess ${pct(horizon.top10_excess_return)}</strong><small>Top10 ${pct(horizon.top10_mean_return)} · IC ${pct(horizon.rank_ic)}</small>`
            : '<strong>Đang chờ</strong><small>Chưa đủ phiên</small>'}</div>`;
        }).join('')}</div>
      </article>`).join('')}</div>`;
  }

  function eventsTable(events) {
    if (!events?.length) return '<div class="empty">Chưa có dòng tiền hoặc fill thực tế.</div>';
    return `<div class="performance-events">${events.slice().reverse().slice(0, 30).map(event => `
      <article>
        <div><strong>${esc(event.event_day)} · ${esc(event.event_type)}</strong><span>${esc(event.source)}</span></div>
        <div>${event.symbol ? `${esc(event.side)} ${esc(event.symbol)} · ${num(event.quantity)} cp @ ${money(event.price_vnd)}` : money(event.amount_vnd)}</div>
      </article>`).join('')}</div>`;
  }

  function renderActive(data) {
    const summary = data.summary || {};
    const plans = data.shadow_plans || [];
    const planOptions = plans.slice().reverse().map(plan => `<option value="${esc(plan.plan_id)}">${esc(plan.week_key)} · ${esc(plan.plan_id)}</option>`).join('');
    document.querySelector('#performance-content').innerHTML = `
      <div class="performance-summary-grid">
        ${summaryCard('Toàn tài khoản DNSE', summary.WHOLE_DNSE, 'Nguồn snapshot broker')}
        ${summaryCard('Actual model sleeve', summary.ACTUAL_MODEL_SLEEVE, 'Dòng tiền và fill đã xác nhận')}
        ${summaryCard('Plan shadow', summary.PLAN_SHADOW, 'Plan canonical khớp T+1 open')}
        ${summaryCard('VNINDEX benchmark', summary.VNINDEX_BENCHMARK, 'Cùng dòng tiền shadow')}
      </div>
      <div class="panel">
        <div class="section-head compact"><div><h3>Lợi nhuận tích lũy</h3><p>TWR loại ảnh hưởng thời điểm nạp tiền; XIRR phản ánh trải nghiệm tiền thật.</p></div></div>
        ${lineChart(data.series)}
      </div>
      <div class="performance-input-grid">
        <div class="panel">
          <h3>Xác nhận dòng tiền thực</h3>
          <p>Chỉ ghi khi tiền đã thực sự vào hoặc ra khỏi DNSE.</p>
          <div class="form-grid">
            <label>Loại<select id="performance-flow-type"><option value="DEPOSIT">Nạp tiền</option><option value="WITHDRAWAL">Rút tiền</option></select></label>
            <label>Ngày<input id="performance-flow-day" type="date" value="${today()}"></label>
            <label>Số tiền<input id="performance-flow-amount" type="number" min="1" step="1000"></label>
            <label>Ghi chú<input id="performance-flow-note" placeholder="Tuần 1, chuyển khoản..."></label>
          </div>
          <button id="performance-add-flow">Ghi dòng tiền</button>
        </div>
        <div class="panel">
          <h3>Xác nhận fill thực tế</h3>
          <p>Nhập theo lịch sử khớp lệnh DNSE; không dùng giá vốn tổng hợp.</p>
          <div class="form-grid performance-fill-form">
            <label>Chiều<select id="performance-fill-side"><option value="BUY">Mua</option><option value="SELL">Bán</option></select></label>
            <label>Ngày khớp<input id="performance-fill-day" type="date" value="${today()}"></label>
            <label>Mã<input id="performance-fill-symbol" placeholder="FPT"></label>
            <label>Số lượng<input id="performance-fill-quantity" type="number" min="1" step="1"></label>
            <label>Giá khớp (đồng)<input id="performance-fill-price" type="number" min="1" step="10"></label>
            <label>Phí<input id="performance-fill-fees" type="number" min="0" step="100" value="0"></label>
            <label>Thuế<input id="performance-fill-taxes" type="number" min="0" step="100" value="0"></label>
            <label>Ghép plan<select id="performance-fill-plan"><option value="">Tự ghép theo mã/ngày</option>${planOptions}</select></label>
          </div>
          <button id="performance-add-fill">Ghi fill</button>
        </div>
      </div>
      <div id="performance-form-result" class="result-box">Sẵn sàng ghi sự kiện.</div>
      <section class="dashboard-output-section">
        <div class="section-head"><div><h3>Đối soát actual và shadow</h3><p>Đo quantity compliance, execution delay và price slippage.</p></div></div>
        ${reconciliationCards(data.reconciliation)}
      </section>
      <section class="dashboard-output-section">
        <div class="section-head"><div><h3>Chất lượng tín hiệu C3 từ ngày bắt đầu</h3><p>Forward return Top-10 và Rank IC, độc lập với việc mày có mua hay không.</p></div></div>
        ${scorecardRows(data.signal_scorecard)}
      </section>
      <section class="dashboard-output-section">
        <div class="section-head"><div><h3>Event ledger thực tế</h3><p>Append-only; không viết lại lịch sử sau khi đã biết kết quả.</p></div></div>
        ${eventsTable(data.events)}
      </section>
      <div class="research-note">Whole DNSE TWR chỉ chính xác khi mọi khoản nạp/rút được xác nhận. Actual model sleeve chỉ tính những fill đã ghi. Hệ thống không đặt lệnh broker.</div>`;
    document.querySelector('#performance-add-flow')?.addEventListener('click', addFlow);
    document.querySelector('#performance-add-fill')?.addEventListener('click', addFill);
  }

  function setNotice(message, className = '') {
    const element = document.querySelector('#performance-notice');
    if (!element) return;
    element.textContent = message;
    element.className = `notice ${className}`;
  }

  async function loadPerformance() {
    try {
      performanceState = await request('/api/performance');
      if (performanceState.status === 'NOT_STARTED') renderNotStarted(performanceState);
      else renderActive(performanceState);
      setNotice(performanceState.status === 'ACTIVE' ? `Observatory đang hoạt động từ ${performanceState.config.start_day}.` : 'Chưa chốt snapshot mở đầu.', performanceState.status === 'ACTIVE' ? 'good' : 'warn');
    } catch (error) {
      setNotice(error.message, 'bad');
    }
  }

  async function refreshPerformance() {
    setNotice('Đang tái định giá và đối soát...', 'warn');
    try {
      performanceState = await request('/api/performance/refresh', {method: 'POST', body: '{}'});
      if (performanceState.status === 'ACTIVE') renderActive(performanceState);
      else renderNotStarted(performanceState);
      setNotice('Đã cập nhật hiệu quả.', 'good');
    } catch (error) {
      setNotice(error.message, 'bad');
    }
  }

  async function startPerformance() {
    const classifications = {};
    document.querySelectorAll('.performance-position-classification').forEach(row => {
      classifications[row.dataset.symbol] = row.querySelector('.performance-classification').value;
    });
    const body = {
      start_day: document.querySelector('#performance-start-day').value,
      opening_model_cash_vnd: Number(document.querySelector('#performance-opening-cash').value || 0),
      classifications,
    };
    if (!confirm('Chốt snapshot mở đầu? Sau khi tạo, ngày bắt đầu và phân loại opening sẽ không được sửa.')) return;
    setNotice('Đang khởi tạo Observatory...', 'warn');
    try {
      performanceState = await request('/api/performance/start', {method: 'POST', body: JSON.stringify(body)});
      renderActive(performanceState);
      setNotice('Đã chốt snapshot mở đầu.', 'good');
    } catch (error) {
      setNotice(error.message, 'bad');
    }
  }

  async function addFlow() {
    const body = {
      flow_type: document.querySelector('#performance-flow-type').value,
      event_day: document.querySelector('#performance-flow-day').value,
      amount_vnd: Number(document.querySelector('#performance-flow-amount').value || 0),
      note: document.querySelector('#performance-flow-note').value,
    };
    await submitEvent('/api/performance/cashflow', body);
  }

  async function addFill() {
    const body = {
      side: document.querySelector('#performance-fill-side').value,
      event_day: document.querySelector('#performance-fill-day').value,
      symbol: document.querySelector('#performance-fill-symbol').value.trim().toUpperCase(),
      quantity: Number(document.querySelector('#performance-fill-quantity').value || 0),
      price_vnd: Number(document.querySelector('#performance-fill-price').value || 0),
      fees_vnd: Number(document.querySelector('#performance-fill-fees').value || 0),
      taxes_vnd: Number(document.querySelector('#performance-fill-taxes').value || 0),
      plan_id: document.querySelector('#performance-fill-plan').value || null,
    };
    await submitEvent('/api/performance/fill', body);
  }

  async function submitEvent(path, body) {
    const result = document.querySelector('#performance-form-result');
    result.className = 'result-box warn';
    result.textContent = 'Đang ghi sự kiện và tái tính hiệu quả...';
    try {
      await request(path, {method: 'POST', body: JSON.stringify(body)});
      result.className = 'result-box good';
      result.textContent = 'Đã ghi sự kiện vào ledger.';
      await loadPerformance();
    } catch (error) {
      result.className = 'result-box bad';
      result.textContent = error.message;
    }
  }

  addTab();
  loadPerformance();
  document.addEventListener('click', event => {
    if (event.target.closest('[data-action="sync-broker"], [data-action="plan"], [data-action="model"]')) {
      setTimeout(() => loadPerformance(), 1800);
    }
  });
})();
