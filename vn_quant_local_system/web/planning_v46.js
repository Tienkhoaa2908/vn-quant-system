(() => {
  const VERSION = 'V55_FINAL_EOD_ONLY_VALUATION';
  const previousRenderPortfolio = window.renderPortfolio;
  const esc = value => window.escapeHtml ? escapeHtml(value ?? '') : String(value ?? '');
  const money = value => window.fmtMoney ? fmtMoney(Number(value || 0)) : `${Number(value || 0).toLocaleString('vi-VN')} ₫`;
  const number = value => window.fmtNum ? fmtNum(Number(value || 0), 0) : Number(value || 0).toLocaleString('vi-VN');
  const percent = value => window.fmtPct ? fmtPct(Number(value || 0)) : `${(Number(value || 0) * 100).toFixed(2)}%`;

  function badgeHtml(text, cls) {
    return window.badge ? badge(text, cls) : `<span class="badge ${cls}">${esc(text)}</span>`;
  }

  function renderSummary(broker) {
    const target = document.querySelector('#v49-broker-summary');
    if (!target) return;
    const details = broker.details || {};
    target.innerHTML = `
      <div class="v49-integrity-banner current">
        <div>
          <div class="v49-state">Danh mục DNSE · định giá EOD chính thức</div>
          <div class="v49-source-note">Tiền và số lượng lấy tại DNSE lúc ${esc(broker.captured_at || '—')}; giá trị danh mục dùng close local ngày ${esc(broker.official_valuation_day || broker.market_day || '—')}.</div>
        </div>
        <div class="v49-freshness-technical">${VERSION}</div>
      </div>
      <div class="v49-integrity-grid">
        <article class="v49-integrity-card"><span>Tiền khả dụng DNSE</span><strong>${money(broker.available_cash_vnd)}</strong><small>Planner dùng số này</small></article>
        <article class="v49-integrity-card"><span>Tiền có thể rút</span><strong>${money(broker.withdrawable_cash_vnd)}</strong><small>Chỉ để đối chiếu</small></article>
        <article class="v49-integrity-card"><span>Planner cash</span><strong>${money(broker.planner_cash_vnd)}</strong><small>${esc(details.planner_cash_source || 'DNSE_CASH')}</small></article>
        <article class="v49-integrity-card"><span>NAV EOD chính thức</span><strong>${money(broker.official_eod_nav_vnd || broker.net_asset_value_vnd)}</strong><small>Tiền mặt + close EOD</small></article>
        <article class="v49-integrity-card"><span>Giá trị cổ phiếu EOD</span><strong>${money(broker.official_eod_stock_value_vnd || broker.stock_value_vnd)}</strong><small>Không dùng marketPrice từ position API</small></article>
        <article class="v49-integrity-card"><span>Vị thế mở</span><strong>${number(broker.position_count || 0)} mã</strong><small>Quantity và sellable quantity từ DNSE</small></article>
      </div>`;
  }

  function renderPortfolioV55(broker, account) {
    const version = broker?.version || broker?.details?.version;
    if (!broker || broker.status !== 'SUCCESS' || version !== VERSION) {
      if (typeof previousRenderPortfolio === 'function') previousRenderPortfolio(broker, account);
      return;
    }
    const grid = document.querySelector('#portfolio-grid');
    const positions = broker.positions || [];
    const sourceBadge = document.querySelector('#portfolio-source-badge');
    const summary = document.querySelector('#broker-summary-text');
    if (sourceBadge) {
      sourceBadge.textContent = 'DNSE vị thế · EOD định giá';
      sourceBadge.className = 'badge good';
    }
    if (summary) {
      summary.textContent = `${broker.position_count || 0} mã · ${broker.details?.selected_masked_account || 'tiểu khoản đã chọn'} · NAV EOD ${money(broker.official_eod_nav_vnd || broker.net_asset_value_vnd)}`;
    }
    renderSummary(broker);
    if (!grid) return;
    if (!positions.length) {
      grid.innerHTML = '<div class="empty">Tiểu khoản đã chọn hiện không có vị thế cổ phiếu mở.</div>';
      return;
    }
    grid.innerHTML = positions.map(position => {
      const price = Number(position.official_eod_price_vnd || position.valuation_price_vnd || 0);
      const marketValue = Number(position.official_eod_market_value_vnd || position.market_value_vnd || 0);
      const pnl = Number(position.official_eod_unrealized_pnl_vnd ?? position.unrealized_pnl_vnd ?? 0);
      const pnlPct = Number(position.official_eod_unrealized_pnl_pct ?? position.unrealized_pnl_pct ?? 0);
      return `<article class="security-card portfolio-card">
        <div class="security-head">
          <div><span class="ticker">${esc(position.symbol)}</span><span class="muted-text">${number(position.quantity)} cp</span></div>
          ${badgeHtml(percent(pnlPct), pnl >= 0 ? 'good' : 'bad')}
        </div>
        <div class="metric-grid">
          <div><span>Giá vốn</span><strong>${money(position.average_cost_vnd)}</strong></div>
          <div><span>Có thể bán</span><strong>${number(position.sellable_quantity)} cp</strong></div>
          <div><span>P&L EOD</span><strong class="${pnl >= 0 ? 'good' : 'bad'}">${money(pnl)}</strong></div>
          <div><span>Ngày định giá</span><strong>${esc(broker.official_valuation_day || broker.market_day || '—')}</strong></div>
        </div>
        <div class="v49-price-split v55-single-price">
          <div class="v49-price-box">
            <span>Giá đóng cửa EOD chính thức</span>
            <strong>${price > 0 ? money(price) : 'Chưa có EOD'}</strong>
            <small>Giá trị vị thế ${money(marketValue)}</small>
          </div>
        </div>
      </article>`;
    }).join('');
  }

  window.renderPortfolio = renderPortfolioV55;
  try { renderPortfolio = renderPortfolioV55; } catch (_) {}
})();
