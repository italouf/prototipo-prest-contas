/* Gráficos do relatório mensal (Chart.js, sem animação para impressão). */
(function () {
  "use strict";
  var COR_CAPTADO = "#1d72b9";
  var COR_EXECUTADO = "#3b249c";

  function lerJson(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function init() {
    if (typeof Chart === "undefined") return;
    var canvas = document.getElementById("report-grafico-pilares");
    if (!canvas) return;
    if (window.quiinRelatorioCharts) {
      Object.keys(window.quiinRelatorioCharts).forEach(function (k) {
        if (window.quiinRelatorioCharts[k]) window.quiinRelatorioCharts[k].destroy();
      });
    }
    window.quiinRelatorioCharts = {};
    var pilares = lerJson("dados-relatorio-pilares");
    var mensal = lerJson("dados-relatorio-mensal");

    if (pilares && pilares.length) {
      window.quiinRelatorioCharts.pilares = new Chart(canvas, {
        type: "bar",
        data: {
          labels: pilares.map(function (p) { return p.nome; }),
          datasets: [
            { label: "Captado", data: pilares.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: pilares.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO }
          ]
        },
        options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { position: "bottom" } } }
      });
    }

    var canvasMensal = document.getElementById("report-grafico-mensal");
    if (canvasMensal && mensal && mensal.length) {
      window.quiinRelatorioCharts.mensal = new Chart(canvasMensal, {
        type: "bar",
        data: {
          labels: mensal.map(function (p) { return p.rotulo; }),
          datasets: [
            { label: "Captado", data: mensal.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: mensal.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO }
          ]
        },
        options: { responsive: true, maintainAspectRatio: false, animation: false, plugins: { legend: { position: "bottom" } } }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
