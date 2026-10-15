/* Interações progressivas: todos os links e formulários funcionam sem JavaScript. */
(function () {
  document.addEventListener('click', async function (event) {
    const link = event.target.closest('[data-feature-dialog]');
    if (!link || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    try {
      const response = await fetch(link.href, {headers: {'X-Feature-Dialog': '1'}});
      if (!response.ok || response.redirected) { location.href = link.href; return; }
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const main = doc.querySelector('#main');
      if (!main) { location.href = link.href; return; }
      const dialog = document.createElement('dialog');
      dialog.className = 'feature-dialog' + (link.dataset.featureDialog === 'drawer' ? ' drawer' : '');
      const close = document.createElement('button');
      close.className = 'feature-dialog-close'; close.textContent = '×'; close.setAttribute('aria-label', 'Fechar');
      close.addEventListener('click', () => dialog.close());
      dialog.append(close);
      while (main.firstChild) dialog.append(main.firstChild);
      dialog.querySelectorAll('form[method="post"]').forEach(form => { if (!form.hasAttribute('action')) form.action = link.href; });
      document.body.append(dialog);
      dialog.addEventListener('close', () => dialog.remove());
      dialog.showModal();
    } catch (_) { location.href = link.href; }
  });
  document.addEventListener('change', function (event) {
    if (event.target.matches('[data-feature-navigate]')) location.href = event.target.value;
  });
  document.addEventListener('input', function (event) {
    if (!event.target.closest('[data-entry-form]')) return;
    event.target.closest('tr')?.classList.add('feature-edited');
    const form = event.target.closest('form');
    const summary = form.querySelector('[data-entry-summary]');
    if (summary) summary.textContent = form.querySelectorAll('.feature-edited').length + ' indicador(es) editado(s) · salve o rascunho ou envie para validação';
  });
  document.addEventListener('click', function(event) {
    const filter = event.target.closest('[data-entry-type]');
    if (!filter) return;
    const page = filter.closest('.feature-page');
    page.querySelectorAll('[data-entry-type]').forEach(button => button.classList.toggle('active', button === filter));
    page.querySelectorAll('tr[data-indicator-type]').forEach(row => { row.hidden = !!filter.dataset.entryType && row.dataset.indicatorType !== filter.dataset.entryType; });
  });
})();
