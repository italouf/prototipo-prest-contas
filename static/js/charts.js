/* Gráficos do Portal QuIIN: dashboard e relatório mensal.
   Chart.js é carregado sob demanda (lazy) e reinicializado após swaps HTMX. */
(function () {
  "use strict";

  var COR_CAPTADO = "#1d72b9";
  var COR_EXECUTADO = "#3b249c";
  var CANVAS_IDS = [
    "grafico-mensal",
    "grafico-financeiro",
    "report-grafico-pilares",
    "report-grafico-mensal",
  ];

  function metaUrl() {
    var meta = document.querySelector('meta[name="chart-url"]');
    return meta ? meta.content : "";
  }

  function lerJson(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function temCanvas() {
    return CANVAS_IDS.some(function (id) {
      return !!document.getElementById(id);
    });
  }

  function garantirChart(callback) {
    if (typeof Chart !== "undefined") {
      callback();
      return;
    }
    if (!temCanvas()) return;
    var url = metaUrl();
    if (!url) return;
    if (window.__quiinChartCarregando) {
      document.addEventListener("quiin:chart-pronto", callback, { once: true });
      return;
    }
    window.__quiinChartCarregando = true;
    var script = document.createElement("script");
    script.src = url;
    script.defer = true;
    script.onload = function () {
      document.dispatchEvent(new Event("quiin:chart-pronto"));
    };
    document.head.appendChild(script);
  }

  function opcoesBase(extras) {
    var base = {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { position: "bottom" } },
    };
    return Object.assign(base, extras || {});
  }

  function initDashboard() {
    var canvasMensal = document.getElementById("grafico-mensal");
    var canvasFinanceiro = document.getElementById("grafico-financeiro");
    var instancias = window.quiinDashboardCharts || {};
    Object.keys(instancias).forEach(function (k) {
      if (instancias[k]) instancias[k].destroy();
    });
    window.quiinDashboardCharts = {};
    if (!canvasMensal && !canvasFinanceiro) return;

    var mensal = lerJson("dados-mensal");
    var financeiro = lerJson("dados-financeiro");
    if (canvasMensal && mensal && mensal.length) {
      window.quiinDashboardCharts.mensal = new Chart(canvasMensal, {
        type: "bar",
        data: {
          labels: mensal.map(function (p) { return p.rotulo; }),
          datasets: [
            { label: "Captado", data: mensal.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: mensal.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO },
          ],
        },
        options: opcoesBase({ scales: { y: { beginAtZero: true } } }),
      });
    }
    if (canvasFinanceiro && financeiro && financeiro.length) {
      window.quiinDashboardCharts.financeiro = new Chart(canvasFinanceiro, {
        type: "bar",
        data: {
          labels: financeiro.map(function (p) { return p.nome; }),
          datasets: [
            { label: "Captado", data: financeiro.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: financeiro.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO },
          ],
        },
        options: opcoesBase({ indexAxis: "y", scales: { x: { beginAtZero: true } } }),
      });
    }
  }

  function initRelatorio() {
    var canvasPilares = document.getElementById("report-grafico-pilares");
    var canvasMensal = document.getElementById("report-grafico-mensal");
    var instancias = window.quiinRelatorioCharts || {};
    Object.keys(instancias).forEach(function (k) {
      if (instancias[k]) instancias[k].destroy();
    });
    window.quiinRelatorioCharts = {};
    if (!canvasPilares && !canvasMensal) return;

    var pilares = lerJson("dados-relatorio-pilares");
    var mensal = lerJson("dados-relatorio-mensal");
    if (canvasPilares && pilares && pilares.length) {
      window.quiinRelatorioCharts.pilares = new Chart(canvasPilares, {
        type: "bar",
        data: {
          labels: pilares.map(function (p) { return p.nome; }),
          datasets: [
            { label: "Captado", data: pilares.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: pilares.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO },
          ],
        },
        options: opcoesBase({ indexAxis: "y", scales: { x: { beginAtZero: true } } }),
      });
    }
    if (canvasMensal && mensal && mensal.length) {
      window.quiinRelatorioCharts.mensal = new Chart(canvasMensal, {
        type: "bar",
        data: {
          labels: mensal.map(function (p) { return p.rotulo; }),
          datasets: [
            { label: "Captado", data: mensal.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: mensal.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO },
          ],
        },
        options: opcoesBase({}),
      });
    }
  }

  function inicializar() {
    if (!temCanvas()) return;
    garantirChart(function () {
      initDashboard();
      initRelatorio();
    });
  }

  document.addEventListener("DOMContentLoaded", inicializar);
  document.addEventListener("htmx:afterSwap", inicializar);
  document.addEventListener("quiin:chart-pronto", inicializar);
})();
