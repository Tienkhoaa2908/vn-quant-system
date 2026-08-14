(() => {
  const V59_POLL_MS = 1000;
  let timer = null;
  let requestInFlight = false;

  const money = (v) => Number(v || 0).toLocaleString('vi-VN', {maximumFractionDigits: 0}) + ' ₫';
  const num = (v, d = 2) => Number(v || 0).toLocaleString('vi-VN', {maximumFractionDigits: d});
  const esc = (s) => String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');

  function normalizePrice(raw, reference) {
    const value = Number(raw || 0);
    const ref = Number(reference || 0);
    if (!(value > 0)) return 0;
    if (!(ref > 0)) return value < 1000 ? value * 1000 : value;
    const direct = value;
    const scaled = value * 1000;
    return Math.abs(direct / ref - 1) <= Math.abs(scaled / ref - 1) ? direct : scaled;
  }

  function statusClass(status) {
    const text = String(status || '').toUpperCase();
    if (text === 'RUNNING') return 'good';
    if (text === 'STARTING' || text === 'WAITING_FOR_SYMBOLS') return 'warn';
    return 'bad';
  }

  function ensurePanel() {
    if (document.querySelector('#v59-realtime-panel')) return;
    const quick = document.querySelector('.quick-actions-panel');
    const host = quick?.parentElement || document.querySelector('#dashboard');
    if (!host) return;
    const section = document.createElement('section');
    section.id = 'v59-realtime-panel';
    section.className = 'panel v59-realtime-panel';
    section.innerHTML = `
      <div class="v59-realtime-head">
        <div>
          <p class="eyebrow">DNSE REALTIME · READ ONLY</p>
          <h2>Màn hình giao dịch realtime</h2>
          <p class="v59-help">Số lượng/vị thế nhận từ Trading WebSocket; giá/bid/ask nhận từ Market WebSocket. Giá realtime chỉ phục vụ quan sát giao dịch. NAV/P&amp;L chính thức của hệ thống vẫn dùng final EOD local.</p>
        </div>
        <div class="inline-actions">
          <button id="v59-realtime-start" class="secondary">Bật realtime</button>
          <button id="v59-realtime-stop" class="secondary">Dừng realtime</button>
        </div>
      </div>
      <div id="v59-realtime-status" class="v59-realtime-status">Đang đọc trạng thái realtime…</div>
      <div id="v59-realtime-grid" class="v59-realtime-grid"></div>
      <div class="v59-realtime-foot">Không có endpoint đặt/hủy/sửa lệnh trong V59. automatic_live_orders_allowed=false.</div>
    `;
    if (quick && quick.nextSibling) host.insertBefore(section, quick.nextSibling);
    else host.appendChild(section);

    section.querySelector('#v59-realtime-start')?.addEventListener('click', async () => {
      await command('/api/actions/realtime-start');
      await poll();
    });
    section.querySelector('#v59-realtime-stop')?.addEventListener('click', async () => {
      await command('/api/actions/realtime-stop');
      await poll();
    });
  }

  async function command(path) {
    const response = await fetch(path, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: '{}',
      cache: 'no-store'
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || data.error || 'Realtime command failed');
    return data;
  }

  function render(payload) {
    ensurePanel();
    const statusEl = document.querySelector('#v59-realtime-status');
    const grid = document.querySelector('#v59-realtime-grid');
    if (!statusEl || !grid) return;

    const priv = payload?.private || {};
    const market = payload?.market || {};
    const portfolio = payload?.portfolio || {};
    const quotes = new Map((market.quotes || []).map(row => [String(row.symbol || '').toUpperCase(), row]));
    const positions = portfolio.positions || [];

    const lastPrivate = priv.last_event_at
      ? `${esc(priv.last_event_type || '-')} ${esc(priv.last_event_symbol || '')} · ${esc(priv.last_event_at)}`
      : 'chưa có event';
    const lastMarket = market.last_event
      ? `${esc(market.last_event.event_type || '-')} ${esc(market.last_event.symbol || '')} · ${esc(market.last_event.received_at || '')}`
      : 'chưa có event';

    statusEl.innerHTML = `
      <div><span class="badge ${statusClass(priv.status)}">Trading WS ${esc(priv.status || 'UNKNOWN')}</span>
      <span class="badge ${statusClass(market.status)}">Market WS ${esc(market.status || 'UNKNOWN')}</span></div>
      <div class="v59-status-detail">Trading: ${lastPrivate}</div>
      <div class="v59-status-detail">Market: ${lastMarket} · theo dõi ${Number(market.subscribed_symbol_count || 0)} mã</div>
      ${priv.ws_newer_than_rest_modified ? '<div class="v59-lag-alert">Trading WebSocket đang có modified timestamp mới hơn REST snapshot — đã bắt được bằng chứng REST/local snapshot bị trễ so với stream.</div>' : ''}
      ${priv.last_error ? `<div class="v59-error">Trading WS: ${esc(priv.last_error)}</div>` : ''}
      ${market.last_error ? `<div class="v59-error">Market WS: ${esc(market.last_error)}</div>` : ''}
    `;

    if (!positions.length) {
      grid.innerHTML = '<div class="empty">Chưa có vị thế trong REST checkpoint/WS realtime.</div>';
      return;
    }

    grid.innerHTML = positions.map(position => {
      const symbol = String(position.symbol || '').toUpperCase();
      const quote = quotes.get(symbol) || {};
      const eod = Number(position.official_eod_price_vnd || position.valuation_price_vnd || 0);
      const last = normalizePrice(quote.last_price, eod);
      const bid = normalizePrice(quote.bid_price, eod);
      const ask = normalizePrice(quote.ask_price, eod);
      const qty = Number(position.quantity || 0);
      const sellable = Number(position.sellable_quantity || 0);
      const cost = Number(position.average_cost_vnd || 0);
      const liveMark = last > 0 ? last : 0;
      const livePnl = liveMark > 0 ? (liveMark - cost) * qty : null;
      const livePct = cost > 0 && liveMark > 0 ? (liveMark / cost - 1) * 100 : null;
      const changeFromEod = eod > 0 && liveMark > 0 ? (liveMark / eod - 1) * 100 : null;
      const freshAt = quote.updated_at || position.realtime_received_at || '';
      return `
        <article class="v59-live-card">
          <div class="v59-live-title"><strong>${esc(symbol)}</strong><span>${num(qty,0)} cp · bán ${num(sellable,0)}</span></div>
          <div class="v59-live-price">${liveMark > 0 ? money(liveMark) : 'Chờ tick'}</div>
          <div class="v59-live-change ${changeFromEod === null ? '' : changeFromEod >= 0 ? 'good' : 'bad'}">${changeFromEod === null ? 'Chưa có giá realtime' : `${changeFromEod >= 0 ? '+' : ''}${changeFromEod.toFixed(2)}% so EOD`}</div>
          <div class="v59-live-metrics">
            <span>EOD chính thức<strong>${money(eod)}</strong></span>
            <span>Bid<strong>${bid > 0 ? money(bid) : '—'}</strong></span>
            <span>Ask<strong>${ask > 0 ? money(ask) : '—'}</strong></span>
            <span>Giá vốn<strong>${money(cost)}</strong></span>
            <span>P&amp;L realtime<strong class="${livePnl === null ? '' : livePnl >= 0 ? 'good' : 'bad'}">${livePnl === null ? '—' : money(livePnl)}</strong></span>
            <span>% realtime<strong class="${livePct === null ? '' : livePct >= 0 ? 'good' : 'bad'}">${livePct === null ? '—' : `${livePct >= 0 ? '+' : ''}${livePct.toFixed(2)}%`}</strong></span>
          </div>
          <div class="v59-live-time">${freshAt ? `tick local ${esc(freshAt)}` : 'Chờ dữ liệu stream'}</div>
        </article>`;
    }).join('');
  }

  async function poll() {
    if (requestInFlight) return;
    requestInFlight = true;
    try {
      const response = await fetch('/api/realtime', {cache:'no-store'});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.message || payload.error || 'Realtime request failed');
      render(payload);
    } catch (error) {
      ensurePanel();
      const statusEl = document.querySelector('#v59-realtime-status');
      if (statusEl) statusEl.innerHTML = `<div class="v59-error">${esc(error.message || error)}</div>`;
    } finally {
      requestInFlight = false;
    }
  }

  function start() {
    ensurePanel();
    poll();
    if (timer) clearInterval(timer);
    timer = setInterval(poll, V59_POLL_MS);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
