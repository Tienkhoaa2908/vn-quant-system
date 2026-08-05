(() => {
  const originalRenderStatus = window.renderStatus;
  if (typeof originalRenderStatus === 'function') {
    window.renderStatus = function renderStatusPreserveCapital(data) {
      const input = document.querySelector('#dashboard-budget');
      const current = input ? input.value : '0';
      const focused = document.activeElement === input;
      originalRenderStatus(data);
      const next = document.querySelector('#dashboard-budget');
      if (next) {
        next.value = current === '' && !focused ? '0' : current;
        next.min = '0';
      }
    };
  }

  function normalizeInitialValue() {
    const input = document.querySelector('#dashboard-budget');
    if (!input) return;
    if (input.value === '' || Number(input.value) < 0) input.value = '0';
    input.min = '0';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', normalizeInitialValue);
  } else {
    normalizeInitialValue();
  }
})();
