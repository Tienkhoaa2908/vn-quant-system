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
