/* Inicialização dos gráficos do dashboard executivo (Chart.js). */
(function () {
  "use strict";

  var COR_CAPTADO = "#1d72b9";
  var COR_EXECUTADO = "#3b249c";

  function lerJson(id) {
    var el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  function destruir() {
    var instancias = window.quiinDashboardCharts || {};
    Object.keys(instancias).forEach(function (chave) {
      if (instancias[chave]) {
        instancias[chave].destroy();
      }
    });
    window.quiinDashboardCharts = {};
  }

  function inicializar() {
    if (typeof Chart === "undefined" || !document.getElementById("grafico-mensal")) {
      return;
    }
    destruir();
    var mensal = lerJson("dados-mensal");
    var financeiro = lerJson("dados-financeiro");

    if (mensal && mensal.length) {
      window.quiinDashboardCharts.mensal = new Chart(document.getElementById("grafico-mensal"), {
        type: "bar",
        data: {
          labels: mensal.map(function (p) { return p.rotulo; }),
          datasets: [
            { label: "Captado", data: mensal.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: mensal.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { position: "bottom" } },
          scales: { y: { beginAtZero: true } }
        }
      });
    }

    if (financeiro && financeiro.length) {
      window.quiinDashboardCharts.financeiro = new Chart(document.getElementById("grafico-financeiro"), {
        type: "bar",
        data: {
          labels: financeiro.map(function (p) { return p.nome; }),
          datasets: [
            { label: "Captado", data: financeiro.map(function (p) { return p.captado; }), backgroundColor: COR_CAPTADO },
            { label: "Executado", data: financeiro.map(function (p) { return p.executado; }), backgroundColor: COR_EXECUTADO }
          ]
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: { legend: { position: "bottom" } },
          scales: { x: { beginAtZero: true } }
        }
      });
    }
  }

  document.addEventListener("DOMContentLoaded", inicializar);
  document.addEventListener("htmx:afterSwap", function (evento) {
    var alvo = evento.detail && evento.detail.target;
    if (alvo && alvo.id === "dashboard-conteudo") {
      inicializar();
    }
  });
})();
