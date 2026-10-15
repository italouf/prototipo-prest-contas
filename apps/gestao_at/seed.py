"""Carga versionada do guia, sem sobrescrever cadastros ou edições existentes."""
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PILARES = {"pdi": ("PDI", "PDI / FCCT"), "fcrh": ("FORMACAO", "Formação e Capacitação de RH"), "acs": ("STARTUPS", "Atração e Criação de Startups"), "at": ("AT", "Associação Tecnológica"), "infra": ("INFRA", "Infraestrutura"), "of": ("OUTRASFONTES", "Outras fontes")}

def carregar_prototipo(registry, alias="default", completar_formacao=False):
    data = json.loads(Path(__file__).with_name("data").joinpath("prototipo.json").read_text(encoding="utf-8"))
    def model(app, name):
        return registry.get_model(app, name).objects.using(alias)
    planos, beneficios, associados, pilares = {}, {}, {}, {}
    for ordem, (key, (codigo, nome)) in enumerate(PILARES.items(), 1):
        pilares[codigo], _ = model("pillars", "Pilar").get_or_create(codigo=codigo, defaults={"nome": nome, "ordem": ordem})
    quant = [(k, n, u, "Formação e capacitação" if k in ("lato", "aperf", "mini", "work") else "Mentoria e plataformas", True) for k, n, u in data["QB"]]
    outros = [("prio", "Ordem de prioridade no licenciamento", "", "Mentoria e plataformas", False), ("lic", "Licença para uso comercial", "", "Mentoria e plataformas", False), ("dlic", "Desconto em licença de uso comercial", "", "Mentoria e plataformas", False), ("infra", "Acesso prioritário (Bancada, TestBed, Alice e Bob)", "", "Infraestrutura", False), ("hpc", "Desconto em horas máquina (HPC)", "", "Infraestrutura", False), ("est", "Estudos de mercado e boletins técnicos", "", "Conteúdos e eventos", False), ("gt", "Grupo de trabalho", "", "Conteúdos e eventos", False), ("des", "Lançamento de desafios para startups", "", "Conteúdos e eventos", False)]
    for ordem, (codigo, nome, unidade, categoria, quantitativo) in enumerate(quant + outros):
        beneficios[codigo], _ = model("gestao_at", "Beneficio").get_or_create(codigo=codigo, defaults={"nome": nome, "unidade": unidade, "categoria": categoria, "quantitativo": quantitativo, "ordem": ordem})
    for ordem, (nome, lv) in enumerate(data["LV"].items()):
        plano, _ = model("gestao_at", "Plano").get_or_create(nome=nome, defaults={"valor_anual": lv["v"], "ordem": ordem})
        planos[nome] = plano
        for codigo, beneficio in beneficios.items():
            condicao = "Sim" if codigo in ("est", "gt") else lv.get("desafio" if codigo == "des" else codigo, "–")
            quantitativo = beneficio.quantitativo
            incluido = bool(condicao) if quantitativo else condicao not in ("–", "—", "-", "")
            model("gestao_at", "PlanoBeneficio").get_or_create(plano=plano, beneficio=beneficio, defaults={"incluido": incluido, "cota": condicao if quantitativo else 0, "condicao": "" if quantitativo else condicao})
    def parse_date(s):
        return datetime.strptime(s, "%d/%m/%Y").date()
    for row in data["AS"]:
        vi = data["VIG"][row["n"]]
        a, criado = model("gestao_at", "Associado").get_or_create(nome=row["n"], defaults={"tipo": row["tp"], "plano": planos[row["lv"]], "email": row["em"], "inicio_vigencia": parse_date(vi[0]), "fim_vigencia": parse_date(vi[1]), "primeira_reuniao": parse_date(vi[2]) if "/" in vi[2] else None, "demonstracao": True})
        associados[row["n"]] = a
        if criado:
            for codigo, qtd in {**row["u"], **row["use"]}.items():
                model("gestao_at", "UsoBeneficio").get_or_create(associado=a, beneficio=beneficios[codigo], defaults={"quantidade": qtd})
    responsaveis = {"PDI": "PDI", "Formação": "FORMACAO", "Infraestrutura": "INFRA", "Plataformas e PI": "PDI", "Mentoria": "PDI", "Estudos": "AT", "Startups": "STARTUPS"}
    for row in data["SO"]:
        s, criado = model("gestao_at", "Solicitacao").get_or_create(origem_prototipo=f"sig5-solicitacao-{row['id']}", defaults={"associado": associados[row["a"]], "data": parse_date(row["d"]), "categoria": row["p"], "beneficio": row["b"], "assunto": row["s"], "responsavel_tecnico": row["rt"], "responsavel_pilar": pilares[responsaveis[row["p"]]], "status": row["st"], "respondida_em": parse_date(row["r"]) if row["r"] else None})
        if criado:
            for h in row["h"]:
                timestamp = datetime.combine(parse_date(h["d"]), datetime.min.time(), tzinfo=ZoneInfo("America/Sao_Paulo"))
                model("gestao_at", "HistoricoSolicitacao").create(solicitacao=s, data=timestamp, descricao=h["t"], status=row["st"])
    for row in data["T"]:
        codigo = {"FCRH": "FORMACAO", "ACS": "STARTUPS", "Infraestrutura": "INFRA"}.get(row["p"], row["p"])
        c, criado = model("talentos", "Colaborador").get_or_create(nome=row["n"], defaults={"cargo": row["c"], "pilar_principal": pilares[codigo], "horas_semanais": row["h"], "formacoes": row["f"], "lattes_url": row["l"]})
        if completar_formacao and not c.formacoes:
            c.formacoes = row["f"]
            c.save(using=alias, update_fields=["formacoes"])
        if criado:
            for nome in row["s"]:
                competencia, _ = model("talentos", "Competencia").get_or_create(nome=nome)
                c.competencias.add(competencia)
            if row["a"]:
                model("talentos", "Alocacao").get_or_create(colaborador=c, projeto_ou_area="Apoio AT — Arena QuIIN", data_inicio=date(2026, 6, 1), defaults={"horas_semanais": row["a"]})
    return {"planos": len(planos), "associados": len(associados), "solicitacoes": len(data["SO"])}
