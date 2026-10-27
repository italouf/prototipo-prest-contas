/* One controller across direct loads and HTMX navigation; assets are served locally. */
(function () {
  'use strict';
  if (window.quiinPresentation) {
    window.quiinPresentation.init();
    return;
  }
  const instances = new Map();
  let libraryPromise;

  function loadLibrary(url) {
    if (window.Reveal) return Promise.resolve(window.Reveal);
    if (!libraryPromise) {
      libraryPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = () => resolve(window.Reveal);
        script.onerror = () => { libraryPromise = null; reject(new Error('reveal-load')); };
        document.head.appendChild(script);
      });
    }
    return libraryPromise;
  }

  function remove(root) {
    const state = instances.get(root);
    if (!state) return;
    state.cancelled = true;
    state.observer?.disconnect();
    state.listeners.forEach(([element, event, handler]) => element.removeEventListener(event, handler));
    state.deck?.destroy();
    instances.delete(root);
  }

  async function start(root) {
    if (instances.has(root)) return;
    const state = {cancelled: false, listeners: [], deck: null, observer: null};
    instances.set(root, state);
    const bind = (element, event, handler) => {
      if (!element) return;
      element.addEventListener(event, handler);
      state.listeners.push([element, event, handler]);
    };
    try {
      const Reveal = await loadLibrary(root.dataset.revealUrl);
      if (state.cancelled || !root.isConnected) return;
      const print = root.hasAttribute('data-presentation-print');
      if (print) {
        await document.fonts.ready;
        await Promise.all(Array.from(root.querySelectorAll('img')).map(img => img.decode().catch(() => {})));
      }
      if (state.cancelled || !root.isConnected) return;
      const deck = new Reveal(root, {
        embedded: !print, width: 1280, height: 720, margin: 0,
        minScale: 0.1, maxScale: 2, center: false,
        controls: false, progress: false, slideNumber: false,
        hash: false, history: false, respondToHashChanges: false,
        // Reveal's embedded focus tracker follows pointer clicks; DOM focus also
        // covers Tab navigation and assistive technologies.
        keyboardCondition: () => root.contains(document.activeElement),
        transition: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'none' : 'fade',
        transitionSpeed: 'fast', view: print ? 'print' : 'slide', scrollActivationWidth: null,
        pdfMaxPagesPerSlide: 1, pdfSeparateFragments: false,
        postMessage: false, postMessageEvents: false,
      });
      state.deck = deck;
      await deck.initialize();
      if (state.cancelled || !root.isConnected) return;
      root.dataset.ready = 'true';
      if (print) {
        const button = document.querySelector('[data-presentation-print-button]');
        if (button) button.disabled = false;
        bind(button, 'click', () => window.print());
        return;
      }
      const stage = root.closest('[data-presentation-stage]');
      const previous = stage.querySelector('[data-presentation-prev]');
      const next = stage.querySelector('[data-presentation-next]');
      const fullscreen = stage.querySelector('[data-presentation-fullscreen]');
      const counter = stage.querySelector('[data-presentation-counter]');
      function update() {
        const index = deck.getIndices().h;
        const total = deck.getTotalSlides();
        counter.textContent = `${index + 1} / ${total}`;
        previous.disabled = index === 0;
        next.disabled = index === total - 1;
      }
      bind(previous, 'click', () => { deck.prev(); root.focus({preventScroll: true}); });
      bind(next, 'click', () => { deck.next(); root.focus({preventScroll: true}); });
      fullscreen.disabled = !stage.requestFullscreen;
      bind(fullscreen, 'click', async () => {
        try {
          if (document.fullscreenElement === stage) await document.exitFullscreen();
          else await stage.requestFullscreen();
          root.focus({preventScroll: true});
        } catch (_) {
          fullscreen.textContent = 'Tela cheia indisponível';
        }
      });
      bind(document, 'fullscreenchange', () => {
        fullscreen.textContent = document.fullscreenElement === stage ? 'Sair da tela cheia ⛶' : 'Tela cheia ⛶';
        deck.layout();
      });
      deck.on('slidechanged', update);
      state.observer = new ResizeObserver(() => deck.layout());
      state.observer.observe(root);
      update();
    } catch (_) {
      if (state.cancelled || !root.isConnected) return;
      state.deck?.destroy();
      root.classList.add('presentation-reading');
      const message = document.createElement('p');
      message.className = 'presentation-error';
      message.setAttribute('role', 'status');
      message.textContent = 'A navegação por slides está indisponível. O conteúdo aparece abaixo em leitura contínua.';
      root.before(message);
    }
  }

  function init() {
    for (const root of instances.keys()) if (!root.isConnected) remove(root);
    document.querySelectorAll('[data-presentation-deck]').forEach(start);
  }
  window.quiinPresentation = {init};
  document.addEventListener('htmx:afterSettle', init);
  document.addEventListener('htmx:beforeCleanupElement', event => {
    for (const root of instances.keys()) {
      if (event.target === root || event.target.contains(root)) remove(root);
    }
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();
