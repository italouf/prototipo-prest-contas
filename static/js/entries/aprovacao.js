/* Alpine component do painel de aprovação (R3). */
document.addEventListener("alpine:init", function () {
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
    };
  });
});
