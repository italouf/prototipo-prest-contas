"""Consulta única dos materiais: filtra antes do UNION e pagina no banco."""
from django import forms
from django.db.models import CharField, F, Q, Value

from .at_catalog import TIPOS_MATERIAL_AT
from .models import MaterialProjeto, MaterialProdutoAT, TIPOS_MATERIAL

PILARES = {"AT": "AT", "PDI": "PDI", "FORMACAO": "FCRH", "STARTUPS": "ACS"}
TIPOS = dict(TIPOS_MATERIAL)
TIPOS.update(dict(TIPOS_MATERIAL_AT))
TIPOS.pop("OUTRO", None)
TIPOS["RELATORIO"] = "Relatório"


class ConsultaMateriaisForm(forms.Form):
    q = forms.CharField(label="Buscar", required=False, max_length=200)
    pilar = forms.ChoiceField(label="Pilar", required=False)
    origem = forms.ChoiceField(label="Produto/projeto", required=False)
    tipo = forms.ChoiceField(label="Tipo", required=False, choices=[("", "Todos os tipos"), *sorted(TIPOS.items(), key=lambda t: t[1])])
    ano_material = forms.ChoiceField(label="Ano de publicação/entrega", required=False)
    situacao = forms.ChoiceField(label="Situação", required=False)
    ordem = forms.ChoiceField(label="Ordenar por", required=False, choices=[("", "Adicionados recentemente"), ("publicacao", "Publicação mais recente"), ("titulo", "Título A–Z")])
    tamanho = forms.TypedChoiceField(label="Por página", required=False, coerce=int, empty_value=25, choices=[(10, "10"), (25, "25"), (50, "50")])

    def __init__(self, *args, pilares, origens, anos, editavel, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pilar"].choices = [("", "Todos os pilares autorizados"), *((c, PILARES[c]) for c in PILARES if c in pilares)]
        self.fields["origem"].choices = [("", "Todos os produtos/projetos"), *origens]
        self.fields["ano_material"].choices = [("", "Todos os anos"), ("sem_data", "Sem data"), *((str(a), str(a)) for a in anos)]
        self.fields["situacao"].choices = [("", "Ativos")]
        if editavel:
            self.fields["situacao"].choices += [("arquivados", "Arquivados")]


def fontes(centro, visiveis):
    projetos = MaterialProjeto.objects.filter(projeto__centro=centro, projeto__pilar__codigo__in=set(visiveis) - {"AT"})
    produtos = MaterialProdutoAT.objects.filter(produto__centro=centro) if "AT" in visiveis else MaterialProdutoAT.objects.none()
    return [("PROJETO", "projeto", projetos), ("AT", "produto", produtos)]


def filtrar(fontes_base, filtros, editaveis, dono=None):
    resultado = []
    for origem, fk, qs in fontes_base:
        if dono:
            qs = qs.filter(**{fk + "_id": dono.pk}) if (origem == "AT") == (dono._meta.model_name == "produtoat") else qs.none()
        pilar = filtros.get("pilar")
        if pilar:
            if origem == "PROJETO" and pilar != "AT":
                qs = qs.filter(projeto__pilar__codigo=pilar)
            elif origem != "AT" or pilar != "AT":
                qs = qs.none()
        if filtros.get("origem"):
            tipo_origem, pk = filtros["origem"].split(":", 1)
            qs = qs.filter(**{fk + "_id": pk}) if origem == tipo_origem else qs.none()
        arquivado = Q(ativo=False) | Q(**{fk + "__ativo": False})
        if filtros.get("situacao") == "arquivados":
            qs = qs.filter(arquivado)
            if origem == "PROJETO":
                qs = qs.filter(projeto__pilar__codigo__in=editaveis)
            elif "AT" not in editaveis:
                qs = qs.none()
        else:
            qs = qs.filter(ativo=True, **{fk + "__ativo": True})
        if filtros.get("q"):
            busca = Q(titulo__icontains=filtros["q"])
            if not dono:
                busca |= Q(**{fk + "__nome__icontains": filtros["q"]})
            qs = qs.filter(busca)
        if filtros.get("tipo"):
            tipos = ["OUTRO", "OUTROS"] if filtros["tipo"] == "OUTROS" else [filtros["tipo"]]
            qs = qs.filter(tipo__in=tipos)
        ano = filtros.get("ano_material")
        if ano == "sem_data":
            qs = qs.filter(data_publicacao__isnull=True)
        elif ano:
            qs = qs.filter(data_publicacao__year=int(ano))
        resultado.append((origem, fk, qs))
    return resultado


CAMPOS = ("fonte", "id", "titulo", "tipo", "url", "data_publicacao", "criado_em", "ativo",
          "dono_id", "dono_nome", "dono_ativo", "pilar_codigo")


def combinar(fontes_filtradas, ordem=""):
    partes = []
    for origem, fk, qs in fontes_filtradas:
        qs = qs.order_by().annotate(fonte=Value(origem, output_field=CharField()),
            dono_id=F(fk + "_id"), dono_nome=F(fk + "__nome"), dono_ativo=F(fk + "__ativo"),
            pilar_codigo=Value("AT", output_field=CharField()) if origem == "AT" else F("projeto__pilar__codigo"))
        partes.append(qs.values(*CAMPOS))
    uniao = partes[0].union(partes[1], all=True)
    ordenacao = [F("data_publicacao").desc(nulls_last=True)] if ordem == "publicacao" else ["titulo"] if ordem == "titulo" else ["-criado_em"]
    return uniao.order_by(*ordenacao, "fonte", "id")
