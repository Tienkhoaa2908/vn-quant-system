(() => {
  const VERSION = 'V50_DNSE_AUTHORITATIVE_BUYING_POWER';
  const oldRenderPortfolio = renderPortfolio;
  const oldRenderStatus = renderStatus;
  const money = value => fmtMoney(Number(value || 0));
  const esc = value => escapeHtml(value ?? '');

  function presentation(snapshot) {
    if (snapshot?.status === 'SUCCESS') {
      return {
        cls: 'good',
        label: 'Sức mua DNSE đã được xác nhận',
        description: 'Planner dùng PPSE gói không margin và khóa từng mã bằng qmax.',
      };
    }
    return {
      cls: 'warn',
      label: 'Chưa đọc được sức mua DNSE',
      description: 'Planner đang fallback về availableCash; tiền bán chờ về chưa được tính.',
    };
  }

  function replaceCard(grid, label, value, note) {
    if (!grid) return false;
    const cardNode = [...grid.querySelectorAll('.v49-integrity-card')]
      .find(node => node.querySelector('span')?.textContent?.trim() === label);
    if (!cardNode) return false;
    cardNode.innerHTML = `<span>${esc(label)}</span><strong>${money(value)}</strong><small>${esc(note)}</small>`;
    return true;
  }

  function renderBuyingPower(broker) {
    const target = document.querySelector('#v49-broker-summary');
    if (!target || !broker || broker.status !== 'SUCCESS') return;

    const snapshot = broker.buying_power || null;
    const state = presentation(snapshot);
    const grid = target.querySelector('.v49-integrity-grid');
    const available = Number(broker.available_cash_vnd || 0);
    const buyingPower = Number(
      broker.planning_buying_power_vnd
      ?? snapshot?.conservative_buying_power_vnd
      ?? available
    );
    const reusable = Number(
      broker.reusable_unsettled_vnd
      ?? snapshot?.reusable_unsettled_vnd
      ?? Math.max(buyingPower - available, 0)
    );

    const banner = document.createElement('div');
    banner.className = `notice ${state.cls}`;
    banner.innerHTML = `<strong>${esc(state.label)}</strong><div>${esc(state.description)}</div><div class="technical">${esc(snapshot?.source || 'AVAILABLE_CASH_FALLBACK')} · ${esc(snapshot?.snapshot_id || 'NO_PPSE_SNAPSHOT')}</div>`;
    const old = target.querySelector('#v50-buying-power-banner');
    if (old) old.remove();
    banner.id = 'v50-buying-power-banner';
    const integrityBanner = target.querySelector('.v49-integrity-banner');
    if (integrityBanner) integrityBanner.insertAdjacentElement('afterend', banner);
    else target.prepend(banner);

    replaceCard(
      grid,
      'Tiền khả dụng DNSE',
      available,
      'Tiền mặt đã khả dụng; không bao gồm toàn bộ tiền bán chờ về'
    );
    replaceCard(
      grid,
      'Planner cash',
      buyingPower,
      snapshot?.status === 'SUCCESS'
        ? 'PPSE không margin; dùng để tạo kế hoạch'
        : 'Fallback availableCash vì PPSE chưa dùng được'
    );

    if (grid) {
      let reusableCard = grid.querySelector('[data-v50-reusable]');
      if (!reusableCard) {
        reusableCard = document.createElement('article');
        reusableCard.className = 'v49-integrity-card';
        reusableCard.dataset.v50Reusable = '1';
        grid.appendChild(reusableCard);
      }
      reusableCard.innerHTML = `<span>Tiền bán chờ về tái sử dụng</span><strong>${money(reusable)}</strong><small>Chênh lệch giữa sức mua và availableCash</small>`;
    }

    const summary = document.querySelector('#broker-summary-text');
    if (summary) {
      summary.textContent = `${broker.position_count || 0} mã · ${broker.details?.selected_masked_account || 'tiểu khoản đã chọn'} · tiền mặt ${money(available)} · sức mua ${money(buyingPower)}`;
    }
  }

  function appendDashboardBuyingPower(broker) {
    const cards = document.querySelector('#cards');
    if (!cards || !broker || broker.status !== 'SUCCESS') return;
    cards.querySelectorAll('[data-v50-dashboard-buying-power]').forEach(node => node.remove());
    const wrapper = document.createElement('div');
    wrapper.dataset.v50DashboardBuyingPower = '1';
    const snapshot = broker.buying_power || {};
    const value = Number(
      broker.planning_buying_power_vnd
      ?? snapshot.conservative_buying_power_vnd
      ?? broker.available_cash_vnd
      ?? 0
    );
    wrapper.innerHTML = card(
      'Sức mua DNSE',
      money(value),
      snapshot.status === 'SUCCESS'
        ? 'PPSE không margin'
        : 'Fallback về tiền khả dụng'
    );
    const node = wrapper.firstElementChild;
    if (node) {
      node.dataset.v50DashboardBuyingPower = '1';
      cards.appendChild(node);
    }
  }

  renderPortfolio = function renderPortfolioV50(broker, account) {
    oldRenderPortfolio(broker, account);
    renderBuyingPower(broker);
  };

  renderStatus = function renderStatusV50(data) {
    oldRenderStatus(data);
    renderBuyingPower(data?.broker_portfolio);
    appendDashboardBuyingPower(data?.broker_portfolio);
  };

  window.V50_BUYING_POWER_VERSION = VERSION;
})();
