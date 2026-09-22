"""Auditoria dos números entre dashboards (L25, QA).

Somente leitura: reconcilia Geral×Pilares×Mensal×Semestral no banco atual e
imprime OK / FALHA / AVISO por invariante. Sai 1 se alguma invariante falhar.

Uso:
    python manage.py auditar_dashboards
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Reconcilia os números dos dashboards (somente leitura)."

    def handle(self, *args, **options):
        from apps.accounts.models import User
        from apps.core.calculos import itens_do_periodo, itens_por_periodo
        from apps.core.prestacao import (
            contexto_mensal,
            painel_semestral,
            periodo_padrao,
            resolver_semestre,
        )
        from apps.indicators.models import Indicador
        from apps.planning.services import painel, painel_pilar
        from apps.pillars.models import Pilar

        falhas, avisos = [], []

        def relatar(nome, ok, detalhe=""):
            marca = "OK " if ok else "FALHA"
            self.stdout.write(f"[{marca}] {nome} {detalhe}".rstrip())
            if not ok:
                falhas.append(nome)

        # 1. Conjunto de indicadores da demo.
        ativos = list(Indicador.objects.filter(ativo=True))
        sem_meta = sorted(i.codigo for i in ativos if not i.metas.exists())
        if len(ativos) == 22 and not sem_meta:
            relatar("demo-22-indicadores", True, "(22 ativos, todos com meta)")
        else:
            avisos.append("demo-22-indicadores")
            self.stdout.write(
                f"[AVISO] demo-22-indicadores "
                f"({len(ativos)} ativos; sem meta: {sem_meta or 'nenhum'})")

        # 2. Geral × Pilares (PlanoAnual).
        for base in ("financeiro", "fisico"):
            geral = painel(None, base)
            blocos = {g["bloco"]: g for g in geral["tabela"]["grupos"]}
            total = next(l for l in blocos["4.1 PPI"]["linhas"] if l.get("total"))
            soma = sum(
                painel_pilar(Pilar.objects.get(codigo=c), None, base)["previsto"]
                for c in ("PDI", "FORMACAO", "STARTUPS", "INFRA"))
            relatar(f"geral-soma-pilares-{base[:3]}", soma == total["previsto"],
                    f"(geral {total['previsto']} × soma {soma})")

        # 3. Usuário de referência para os painéis operacionais.
        usuario = (
            User.objects.filter(username="erica").first()
            or User.objects.filter(groups__name="Master").first()
        )
        if usuario is None:
            avisos.append("sem-usuario")
            self.stdout.write("[AVISO] sem-usuario (sem Master para os painéis)")
        else:
            periodo = periodo_padrao()
            if periodo is None:
                falhas.append("sem-periodo")
                self.stdout.write("[FALHA] sem-periodo (nenhum período)")
            else:
                cm = contexto_mensal(periodo, usuario)
                cs = painel_semestral(
                    periodo.competencia.year,
                    1 if periodo.competencia.month <= 6 else 2, usuario)
                relatar(
                    "mensal-semestral-financeiro",
                    cm["cards"]["execucao"] == cs["cards"]["executado"]
                    and cm["cards"]["captacao_at"] + cm["cards"]["outras_fontes"]
                    == cs["cards"]["captado"],
                    f"(mensal {cm['cards']['execucao']} × semestral {cs['cards']['executado']})")
                inds = list(Indicador.objects.filter(ativo=True))
                mapa = itens_por_periodo(inds, [periodo])[periodo.pk]
                unico = {i["indicador"].codigo: i
                         for i in itens_do_periodo(inds, periodo)}
                divergentes = [
                    codigo for codigo, item in unico.items()
                    if (item["meta"], item["realizado"], item["percentual"])
                    != ((lambda o: (o["meta"], o["realizado"], o["percentual"]))(
                        next(o for o in mapa if o["indicador"].codigo == codigo)))]
                relatar("lote-igual-unico", not divergentes,
                        f"({len(divergentes)} divergentes: {divergentes[:5]})")

        # 4. Default do semestral resolve.
        estado, ano, semestre = resolver_semestre({})
        relatar("semestral-default", estado in ("ok", "canonico"),
                f"({estado} {ano} s{semestre})")

        if falhas:
            raise CommandError(f"auditoria com {len(falhas)} falha(s): {falhas}")
        self.stdout.write(self.style.SUCCESS(
            f"auditoria concluída ({len(avisos)} aviso(s)): "
            f"{avisos or 'nenhum'}"))
