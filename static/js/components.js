/* Componentes Alpine globais do Portal QuIIN (carregados antes do Alpine).
   Ficam globais para continuarem disponíveis após navegação com hx-boost. */

/* Toasts client-side (usados por HX-Trigger e ações de drag). */
window.quiinToast = function (texto, tipo) {
  var container = document.getElementById("toasts");
  if (!container || !texto) return;
  var div = document.createElement("div");
  div.className = "alert alert-" + (tipo || "info") + " pointer-events-auto shadow-lg";
  div.setAttribute("role", "status");
  div.textContent = texto;
  container.appendChild(div);
  setTimeout(function () {
    div.remove();
  }, 6000);
};

document.addEventListener("quiin:toast", function (evento) {
  var detalhe = evento.detail || {};
  window.quiinToast(detalhe.texto || detalhe.value || "", detalhe.tipo || "info");
});

function quiinCsrfToken() {
  var match = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[2]) : "";
}

document.addEventListener("alpine:init", function () {
  /* ---------- Lançamentos ---------- */
  Alpine.data("filtroIndicadores", function () {
    return {
      tipo: "TODOS",
      mostra: function (t) {
        return this.tipo === "TODOS" || this.tipo === t;
      },
      selecionar: function (t) {
        this.tipo = t;
      },
    };
  });

  Alpine.data("campoValor", function (inicial, tipo) {
    return {
      valor: inicial,
      erro: "",
      validar: function () {
        this.erro = "";
        if (this.valor === "" || this.valor === null) return;
        if (tipo === "TXT") return;
        var texto = String(this.valor).replace(/\./g, "").replace(",", ".");
        var numero = parseFloat(texto);
        if (isNaN(numero) || !isFinite(texto)) {
          this.erro = "Valor numérico inválido.";
          return;
        }
        if (tipo === "PER" && numero > 100) {
          this.erro = "Percentual não pode passar de 100.";
        }
      },
      init: function () {
        var self = this;
        this.$watch("valor", function () {
          self.validar();
        });
      },
    };
  });

  /* ---------- Aprovação (kanban + devolução + timeline) ---------- */
  Alpine.data("painelAprovacao", function () {
    return {
      drawerAberto: false,
      devolver: { aberto: false, id: null, codigo: "" },
      abrirDevolucao: function (id, codigo) {
        this.devolver = { aberto: true, id: id, codigo: codigo };
        this.$nextTick(function () {
          var campo = document.getElementById("motivo-devolucao");
          if (campo) campo.focus();
        });
      },
      fecharDevolucao: function () {
        this.devolver = { aberto: false, id: null, codigo: "" };
      },
      abrirTimeline: function () {
        this.drawerAberto = true;
      },
      iniciarArrasto: function (evento, id) {
        if (!evento.dataTransfer) return;
        evento.dataTransfer.setData("text/plain", String(id));
        evento.dataTransfer.effectAllowed = "move";
      },
      soltar: function (evento, destino) {
        var id = evento.dataTransfer ? evento.dataTransfer.getData("text/plain") : "";
        if (!id) return;
        var card = document.querySelector('[data-card-id="' + id + '"]');
        if (!card) return;
        var url = card.getAttribute("data-mover-url");
        if (!url) return;
        if (destino === "DEVOLVIDO") {
          this.abrirDevolucao(id, card.getAttribute("data-codigo") || "");
          return;
        }
        htmx.ajax("POST", url, {
          values: { destino: destino, csrfmiddlewaretoken: quiinCsrfToken() },
          target: "#kanban",
          swap: "outerHTML",
        });
      },
    };
  });

  /* ---------- Preview de CSV ---------- */
  var CABECALHO = "competencia,pilar,tipo_recurso,valor_captado,valor_executado,observacao";
  var TIPOS = ["EMBRAPII", "AT", "OUTRAS_FONTES"];

  function validarLinha(colunas) {
    var erros = [];
    if (colunas.length !== 6) {
      return ["Colunas: esperado 6, encontrado " + colunas.length + "."];
    }
    var competencia = (colunas[0] || "").trim();
    if (!/^\d{4}-\d{2}/.test(competencia)) erros.push("Competência deve ser AAAA-MM.");
    if (!(colunas[1] || "").trim()) erros.push("Pilar vazio.");
    if (TIPOS.indexOf((colunas[2] || "").trim()) === -1) erros.push("Tipo deve ser EMBRAPII, AT ou OUTRAS_FONTES.");
    [3, 4].forEach(function (i) {
      var valor = (colunas[i] || "").trim();
      if (valor !== "" && isNaN(parseFloat(valor))) erros.push("Coluna " + (i + 1) + " deve ser numérica.");
    });
    return erros;
  }

  Alpine.data("previewCsv", function () {
    return {
      nomeArquivo: "",
      linhas: [],
      errosTotais: 0,
      erroCabecalho: "",
      valido: false,
      ler: function (evento) {
        var arquivo = evento.target.files[0];
        this.linhas = [];
        this.errosTotais = 0;
        this.erroCabecalho = "";
        this.valido = false;
        this.nomeArquivo = arquivo ? arquivo.name : "";
        if (!arquivo) return;
        var self = this;
        arquivo.text().then(function (texto) {
          var linhas = texto.split(/\r?\n/).filter(function (l) { return l.trim() !== ""; });
          var cabecalho = (linhas.shift() || "").trim().replace(/^\ufeff/, "");
          if (cabecalho !== CABECALHO) self.erroCabecalho = "Cabeçalho inesperado: " + cabecalho;
          self.linhas = linhas.map(function (linha, indice) {
            var colunas = linha.split(",");
            var erros = validarLinha(colunas);
            self.errosTotais += erros.length;
            return { numero: indice + 2, colunas: colunas, erros: erros, valida: erros.length === 0 };
          });
          if (self.erroCabecalho) self.errosTotais += 1;
          self.valido = self.errosTotais === 0 && self.linhas.length > 0;
        });
      },
    };
  });
});
