/* Alpine components do formulário de lançamentos (R3). */
document.addEventListener("alpine:init", function () {
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
});
