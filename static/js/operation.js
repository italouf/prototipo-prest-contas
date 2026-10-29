(function () {
  'use strict';
  if (window.quiinOperation) { window.quiinOperation(); return; }
  function init() {
    const board = document.getElementById('operation-board');
    if (!board) return;
    const storageKey = 'quiin-operation-' + board.dataset.user + '-' + board.dataset.period;
    let selected = new URL(location.href).searchParams.get('mobile_status') || board.dataset.mobileStatus || 'ENVIADO';
    try { selected = sessionStorage.getItem(storageKey) || selected; } catch (_) {}
    board.querySelectorAll('.op-column').forEach(col => col.toggleAttribute('data-mobile-active', col.dataset.status === selected));
    board.querySelectorAll('[data-mobile-status]').forEach(tab => tab.setAttribute('aria-pressed', String(tab.dataset.mobileStatus === selected)));
    board.querySelectorAll('a[hx-get], button[data-approved-toggle]').forEach(link => {
      const url = new URL(link.getAttribute('hx-get'), location.href);
      url.searchParams.set('mobile_status', selected);
      link.setAttribute('hx-get', url.pathname + url.search);
      if (link.tagName === 'A') link.href = url.pathname + url.search;
      else link.dataset.url = url.pathname + url.search;
    });
    const button = board.querySelector('[data-approved-toggle]');
    const key = 'quiin-approved-' + board.dataset.user + '-' + board.dataset.period;
    if (button && button.dataset.open === '0' && !new URL(location.href).searchParams.has('aprovados_abertos')) {
      try { if (localStorage.getItem(key) === '1') htmx.ajax('GET', button.dataset.url, { target: '#operation-board', select: '#operation-board', swap: 'outerHTML' }); } catch (_) {}
    }
  }
  document.addEventListener('click', function (event) {
    const close = event.target.closest('[data-close-operation]');
    if (close) document.getElementById('operation-dialog')?.close();
    const approved = event.target.closest('[data-approved-toggle]');
    const board = document.getElementById('operation-board');
    if (approved && board) {
      try { localStorage.setItem('quiin-approved-' + board.dataset.user + '-' + board.dataset.period, approved.dataset.open === '1' ? '0' : '1'); } catch (_) {}
    }
    const status = event.target.closest('button[data-mobile-status]');
    if (status && board) {
      board.dataset.mobileStatus = status.dataset.mobileStatus;
      try { sessionStorage.setItem('quiin-operation-' + board.dataset.user + '-' + board.dataset.period, status.dataset.mobileStatus); } catch (_) {}
      init();
      if (status.dataset.mobileStatus === 'APROVADO' && approved !== status) {
        const load = board.querySelector('[data-approved-toggle][data-open="0"]');
        if (load) load.click();
      }
    }
  });
  document.addEventListener('submit', function (event) {
    const form = event.target.closest('[data-operation-filters]');
    const period = form?.querySelector('[data-operation-period]');
    if (!period) return;
    const parts = location.pathname.split('/');
    if (parts.includes('aprovacao')) form.action = '/aprovacao/' + period.value + '/';
    else if (parts.includes('lancamentos')) form.action = '/lancamentos/' + period.value + '/' + document.getElementById('op-pillar').value + '/';
  });
  document.addEventListener('htmx:afterSwap', function (event) {
    if (event.target.id === 'operation-detail') document.getElementById('operation-dialog')?.showModal();
  });
  document.addEventListener('htmx:afterSettle', init);
  window.quiinOperation = init;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
