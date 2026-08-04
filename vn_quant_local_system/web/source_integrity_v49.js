(() => {
  const VERSION = 'V49_DNSE_SOURCE_INTEGRITY';
  const oldRenderPortfolio = renderPortfolio;
  const oldRenderStatus = renderStatus;
  const esc = value => escapeHtml(value ?? '');
  const money = value => fmtMoney(Number(value || 0));
  const pct = value => fmtPct(Number(value || 0));

  function freshnessPresentation(value) {
    const state = String(value || 'CHUA_DONG_BO');
    return ({
      CURRENT_FINAL_EOD: {
        label: 'Đã có EOD hoàn chỉnh',
        cls: 'current',
        description: 'VNINDEX và phần lớn universe đã có dữ liệu phiên kỳ vọng.',
      },
      PARTIAL_STOCK_COVERAGE: {
        label: 'Dữ liệu cổ phiếu chưa đủ',
        cls: 'partial',
        description: 'VNINDEX đã có nhưng coverage cổ phiếu của phiên kỳ vọng chưa đạt ngưỡng.',
      },
      SOURCE_LAGGING_OR_EMPTY: {
        label: 'Nguồn OHLC chưa trả đủ phiên',
        cls: 'lagging',
        description: 'Hệ thống đã gọi lại API nhưng phiên kỳ vọng vẫn chưa có đầy đủ.',
      },
      EXPECTED_SESSION_UNKNOWN: {
        label: 'Chưa xác định phiên kỳ vọng',
        cls: 'partial',
        description: 'Không đọc được lịch giao dịch DNSE; đang dùng lịch ngày thường dự phòng.',
      },
    })[state] || {
      label: 'Chưa có chẩn đoán V49',
      cls: 'partial',
      description: 'Chạy đồng bộ dữ liệu giá để tạo chẩn đoán freshness mới.',
    };
  }

  function sourceSync(data) {
    return data?.last_sync || data || {};
  }

  function ensureIntegrityPanels() {
    const dataSection = document.querySelector('#data');
    if (dataSection && !document.querySelector('#v49-source-integrity-panel')) {
      const panel = document.createElement('div');
      panel.id = 'v49-source-integrity-panel';
      panel.className = 'panel v49-integrity-panel';
      panel.innerHTML = `
        <div class="section-head compact">
          <div>
            <p class="eyebrow">V49 DNSE SOURCE INTEGRITY</p>
            <h3>Độ mới nguồn và tiểu khoản</h3>
            <p>Tách dữ liệu broker tại thời điểm gọi API khỏi giá EOD dùng cho nghiên cứu.</p>
          </div>
          <div class="inline-actions">
            <button id="v49-load-accounts" class="secondary">Tải tiểu khoản</button>
            <button id="v49-refresh-integrity" class="secondary">Làm mới chẩn đoán</button>
          </div>
        </div>
        <div id="v49-data-freshness"></div>
        <div id="v49-account-picker" class="v49-account-picker">
          <div class="v49-account-empty">Chỉ tải danh sách khi cần chọn hoặc kiểm tra tiểu khoản.</div>
        </div>`;
      const credentialPanel = dataSection.querySelector('.panel');
      if (credentialPanel) dataSection.insertBefore(panel, credentialPanel);
      else dataSection.appendChild(panel);
      panel.querySelector('#v49-load-accounts').addEventListener('click', loadAccountOptions);
      panel.querySelector('#v49-refresh-integrity').addEventListener('click', loadIntegrityFromApi);
    }

    const marketSection = document.querySelector('#market-overview');
    if (marketSection && !document.querySelector('#v49-market-freshness')) {
      const target = document.createElement('div');
      target.id = 'v49-market-freshness';
      target.className = 'v49-integrity-panel';
      const notice = marketSection.querySelector('#market-overview-notice');
      if (notice) notice.insertAdjacentElement('afterend', target);
      else marketSection.prepend(target);
    }

    const portfolioSection = document.querySelector('#portfolio-section');
    if (portfolioSection && !document.querySelector('#v49-broker-summary')) {
      const target = document.createElement('div');
      target.id = 'v49-broker-summary';
      target.className = 'v49-broker-summary';
      const grid = portfolioSection.querySelector('#portfolio-grid');
      if (grid) portfolioSection.insertBefore(target, grid);
      else portfolioSection.appendChild(target);
    }
  }

  function renderFreshness(targetSelector, integrity) {
    const target = document.querySelector(targetSelector);
    if (!target) return;
    const sync = sourceSync(integrity);
    const presentation = freshnessPresentation(sync.source_freshness);
    const ratio = Number(sync.expected_session_stock_coverage_ratio || 0);
    const coverage = ratio > 0 ? `${(ratio * 100).toFixed(1)}%` : '—';
    target.innerHTML = `
      <div class="v49-integrity-banner ${presentation.cls}">
        <div>
          <div class="v49-state">${esc(presentation.label)}</div>
          <div class="v49-source-note">${esc(presentation.description)}</div>
        </div>
        <div class="v49-freshness-technical">${esc(sync.source_freshness || 'NO_V49_SYNC')}</div>
      </div>
      <div class="v49-integrity-grid">
        <article class="v49-integrity-card"><span>Phiên kỳ vọng</span><strong>${esc(sync.expected_final_session || '—')}</strong><small>Sau mốc EOD của ngày giao dịch</small></article>
        <article class="v49-integrity-card"><span>VNINDEX mới nhất</span><strong>${esc(sync.latest_index_day || integrity?.latest_index_day || '—')}</strong><small>Kho OHLC local</small></article>
        <article class="v49-integrity-card"><span>Cổ phiếu mới nhất</span><strong>${esc(sync.latest_stock_day || integrity?.latest_stock_day || '—')}</strong><small>Ngày lớn nhất trong universe</small></article>
        <article class="v49-integrity-card"><span>Coverage phiên kỳ vọng</span><strong>${coverage}</strong><small>${fmtNum(sync.expected_session_stock_count || 0, 0)} mã</small></article>
        <article class="v49-integrity-card"><span>Bar mới / hiệu chỉnh</span><strong>${fmtNum(sync.inserted_row_count || 0,0)} / ${fmtNum(sync.revised_row_count || 0,0)}</strong><small>Recent sessions luôn được gọi lại</small></article>
        <article class="v49-integrity-card"><span>Lỗi mã</span><strong>${fmtNum(sync.symbol_error_count || 0,0)}</strong><small>Không che giấu sync từng phần</small></article>
      </div>`;
  }

  function renderIntegrity(integrity) {
    ensureIntegrityPanels();
    renderFreshness('#v49-data-freshness', integrity || {});
    renderFreshness('#v49-market-freshness', integrity || {});
  }

  async function loadIntegrityFromApi() {
    const button = document.querySelector('#v49-refresh-integrity');
    try {
      if (button) button.disabled = true;
      const data = await api('/api/source-integrity');
      renderIntegrity(data);
    } catch (error) {
      const target = document.querySelector('#v49-data-freshness');
      if (target) target.innerHTML = `<div class="notice bad">${esc(error.message)}</div>`;
    } finally {
      if (button) button.disabled = false;
    }
  }

  function accountRow(row) {
    const selected = Boolean(row.selected);
    const disabled = !row.readable;
    return `<article class="v49-account-row ${selected ? 'selected' : ''}">
      <div class="v49-account-name">
        <strong>${esc(row.masked_account || 'Tiểu khoản')}</strong>
        <small>${selected ? 'Đang được chọn' : row.readable ? 'Có thể chọn' : 'Không đọc được dữ liệu cơ sở'}</small>
      </div>
      <div><small>Tiền khả dụng</small><br><strong>${money(row.available_cash_vnd)}</strong></div>
      <div><small>Có thể rút</small><br><strong>${money(row.withdrawable_cash_vnd)}</strong></div>
      <div><small>Vị thế mở</small><br><strong>${fmtNum(row.open_position_count || 0,0)} mã</strong></div>
      <button class="${selected ? 'secondary' : ''}" data-v49-account-token="${esc(row.selection_token || '')}" ${selected || disabled ? 'disabled' : ''}>${selected ? 'Đang dùng' : 'Chọn tiểu khoản'}</button>
    </article>`;
  }

  async function loadAccountOptions() {
    const target = document.querySelector('#v49-account-picker');
    const button = document.querySelector('#v49-load-accounts');
    if (!target) return;
    try {
      if (button) button.disabled = true;
      target.innerHTML = '<div class="v49-account-empty">Đang gọi DNSE để kiểm tra từng tiểu khoản...</div>';
      const data = await api('/api/broker/accounts');
      const rows = data.accounts || [];
      target.innerHTML = `
        ${data.selection_required ? '<div class="notice warn">Có nhiều tiểu khoản hợp lệ. Chọn đúng tiểu khoản đang xem trong ứng dụng DNSE.</div>' : ''}
        <div class="v49-account-list">${rows.length ? rows.map(accountRow).join('') : '<div class="v49-account-empty">Không tìm thấy tiểu khoản đọc được.</div>'}</div>
        <div class="v49-source-note">Hệ thống chỉ lưu token băm và số tài khoản đã che; không lưu số tiểu khoản đầy đủ ở cấu hình lựa chọn.</div>`;
      target.querySelectorAll('[data-v49-account-token]').forEach(item => {
        item.addEventListener('click', () => selectAccount(item.dataset.v49AccountToken));
      });
    } catch (error) {
      target.innerHTML = `<div class="notice bad">${esc(error.message)}</div>`;
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function selectAccount(token) {
    if (!token || !confirm('Chọn tiểu khoản này làm nguồn danh mục và tiền khả dụng cho planner?')) return;
    const target = document.querySelector('#v49-account-picker');
    try {
      if (target) target.insertAdjacentHTML('afterbegin', '<div class="notice warn">Đang chọn và đồng bộ lại danh mục...</div>');
      await api('/api/broker/select-account', {
        method: 'POST',
        body: JSON.stringify({selection_token: token}),
      });
      await refresh(true);
      await loadAccountOptions();
      setNotice('Đã chọn tiểu khoản và đồng bộ lại danh mục DNSE.', 'good');
    } catch (error) {
      if (target) target.insertAdjacentHTML('afterbegin', `<div class="notice bad">${esc(error.message)}</div>`);
    }
  }

  function renderBrokerSummary(broker) {
    ensureIntegrityPanels();
    const target = document.querySelector('#v49-broker-summary');
    if (!target) return;
    if (!broker || broker.status !== 'SUCCESS') {
      target.innerHTML = '';
      return;
    }
    const details = broker.details || {};
    const selected = details.selected_masked_account || broker.masked_accounts?.[0] || '—';
    target.innerHTML = `
      <div class="v49-integrity-banner current">
        <div><div class="v49-state">Snapshot broker: ${esc(selected)}</div><div class="v49-source-note">Gọi API lúc ${esc(broker.captured_at || '—')} · ${esc(broker.source_freshness || 'BROKER_SNAPSHOT')}</div></div>
        <div class="v49-freshness-technical">${esc(broker.version || details.version || 'LEGACY')}</div>
      </div>
      <div class="v49-integrity-grid">
        <article class="v49-integrity-card"><span>Tiền khả dụng DNSE</span><strong>${money(broker.available_cash_vnd)}</strong><small>Planner dùng số này</small></article>
        <article class="v49-integrity-card"><span>Tiền có thể rút</span><strong>${money(broker.withdrawable_cash_vnd)}</strong><small>Chỉ để đối chiếu</small></article>
        <article class="v49-integrity-card"><span>Planner cash</span><strong>${money(broker.planner_cash_vnd)}</strong><small>${esc(details.planner_cash_source || 'LEGACY')}</small></article>
        <article class="v49-integrity-card"><span>Broker NAV</span><strong>${money(broker.broker_nav_vnd || broker.net_asset_value_vnd)}</strong><small>Giá broker tại lúc gọi API</small></article>
        <article class="v49-integrity-card"><span>Research EOD NAV</span><strong>${money(broker.research_eod_nav_vnd)}</strong><small>Close local ngày ${esc(broker.market_day || '—')}</small></article>
        <article class="v49-integrity-card"><span>Vị thế mở</span><strong>${fmtNum(broker.position_count || 0,0)} mã</strong><small>Không dùng accumulateQuantity lịch sử khi openQuantity = 0</small></article>
      </div>`;
  }

  function renderPortfolioV49(broker, account) {
    const version = broker?.version || broker?.details?.version;
    if (!broker || broker.status !== 'SUCCESS' || version !== VERSION) {
      oldRenderPortfolio(broker, account);
      renderBrokerSummary(broker);
      return;
    }
    const grid = document.querySelector('#portfolio-grid');
    const positions = broker.positions || [];
    const sourceBadge = document.querySelector('#portfolio-source-badge');
    if (sourceBadge) {
      sourceBadge.textContent = 'DNSE · 1 tiểu khoản';
      sourceBadge.className = 'badge good';
    }
    const summary = document.querySelector('#broker-summary-text');
    if (summary) {
      summary.textContent = `${broker.position_count || 0} mã · ${broker.details?.selected_masked_account || 'tiểu khoản đã chọn'} · tiền khả dụng ${money(broker.available_cash_vnd)}`;
    }
    renderBrokerSummary(broker);
    if (!grid) return;
    if (!positions.length) {
      grid.innerHTML = '<div class="empty">Tiểu khoản đã chọn hiện không có vị thế cổ phiếu mở.</div>';
      return;
    }
    grid.innerHTML = positions.map(position => {
      const brokerPrice = Number(position.broker_market_price_vnd || 0);
      const eodPrice = Number(position.local_market_price_vnd || 0);
      const primaryPnl = Number(position.unrealized_pnl_vnd || 0);
      const primaryPct = Number(position.unrealized_pnl_pct || 0);
      return `<article class="security-card portfolio-card">
        <div class="security-head">
          <div><span class="ticker">${esc(position.symbol)}</span><span class="muted-text">${fmtNum(position.quantity,0)} cp</span></div>
          ${badge(pct(primaryPct), primaryPnl >= 0 ? 'good' : 'bad')}
        </div>
        <div class="metric-grid">
          <div><span>Giá vốn</span><strong>${money(position.average_cost_vnd)}</strong></div>
          <div><span>Có thể bán</span><strong>${fmtNum(position.sellable_quantity,0)} cp</strong></div>
          <div><span>Broker P&L</span><strong class="${primaryPnl >= 0 ? 'good' : 'bad'}">${money(primaryPnl)}</strong></div>
          <div><span>Broker modified</span><strong>${esc(position.broker_modified_at || '—')}</strong></div>
        </div>
        <div class="v49-price-split">
          <div class="v49-price-box"><span>Broker snapshot</span><strong>${brokerPrice > 0 ? money(brokerPrice) : 'Không có giá'}</strong><small>${money(position.broker_market_value_vnd || position.market_value_vnd)}</small></div>
          <div class="v49-price-box"><span>Research EOD ${esc(broker.market_day || '')}</span><strong>${eodPrice > 0 ? money(eodPrice) : 'Chưa có EOD'}</strong><small>${money(position.research_eod_market_value_vnd)}</small></div>
        </div>
      </article>`;
    }).join('');
  }

  renderPortfolio = renderPortfolioV49;
  renderStatus = function renderStatusV49(data) {
    oldRenderStatus(data);
    ensureIntegrityPanels();
    renderIntegrity(data?.data_source?.source_integrity || {});
  };

  const observer = new MutationObserver(() => {
    ensureIntegrityPanels();
    const integrity = latestState?.data_source?.source_integrity;
    if (integrity) renderIntegrity(integrity);
  });
  observer.observe(document.body, {childList: true, subtree: true});
  ensureIntegrityPanels();
})();
