/* Alpine component do preview de CSV (R3). */
document.addEventListener("alpine:init", function () {
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
          var cabecalho = (linhas.shift() || "").trim();
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
