"""Formulários dinâmicos baseados nas listas oficiais EMBRAPII v3.1."""
from django import forms

from apps.projects.models import Projeto

from .integracao import listar_projetos_oficiais_para_pilar, validar_vinculo_projeto_oficial
from .models import CicloSemestral, ConfiguracaoPilarSemestral
from .registry import TabFormSpec, get_domain_choices, get_project_code_suggestions


def build_tab_record_form(spec: TabFormSpec, ciclo=None, *args, **kwargs) -> forms.ModelForm:
    """Constrói ModelForm com selects populados de ListaDominioEmbrapii e portfólio oficial."""

    class _DynamicTabForm(forms.ModelForm):
        class Meta:
            model = spec.model
            fields = list(spec.fields)

        def __init__(self, *f_args, **f_kwargs):
            super().__init__(*f_args, **f_kwargs)
            sugestoes = get_project_code_suggestions(ciclo, spec) if ciclo else []
            for fname, field in self.fields.items():
                # 0. Seletor de projeto do portfólio oficial (Fase 1: FINANCEIRO_GERAL -> Semestral)
                if fname == "projeto_oficial" and spec.portfolio_pilar_codigo:
                    projetos_qs = Projeto.objects.filter(
                        ativo=True, pilar__codigo=spec.portfolio_pilar_codigo
                    ).order_by("nome", "pk")
                    meta_map = {
                        item["id"]: item["rotulo"]
                        for item in listar_projetos_oficiais_para_pilar(spec.portfolio_pilar_codigo)
                    }
                    field.queryset = projetos_qs
                    field.required = False
                    field.empty_label = "— Novo projeto (digitar manualmente) —"
                    field.label_from_instance = lambda obj, _m=meta_map: _m.get(str(obj.pk), obj.nome)
                    field.help_text = (
                        "Opcional: selecione um projeto já importado no FINANCEIRO_GERAL para "
                        "pré-preencher título, datas, status e valor planejado sem redigitar."
                    )
                    field.widget.attrs["data-portfolio-selector"] = "1"
                    continue

                # 1. Dropdown oficial EMBRAPII
                if fname in spec.dropdowns:
                    cat = spec.dropdowns[fname]
                    choices = get_domain_choices(cat, required=field.required)
                    # Preserva valor existente mesmo se lista mudar
                    atual = getattr(self.instance, fname, None)
                    if atual and all(c[0] != atual for c in choices):
                        choices.append((atual, atual))
                    self.fields[fname] = forms.ChoiceField(
                        label=field.label,
                        choices=choices,
                        required=field.required,
                        help_text=field.help_text,
                    )
                    continue

                # 2. Datas com input HTML5 compatível
                if isinstance(field, forms.DateField):
                    field.widget = forms.DateInput(
                        attrs={"type": "date"}, format="%Y-%m-%d"
                    )
                    field.input_formats = ["%Y-%m-%d", "%d/%m/%Y"]

                # 3. Textarea compacto
                if isinstance(field.widget, forms.Textarea):
                    field.widget.attrs.setdefault("rows", 3 if not spec.is_comment_sheet else 5)

                # 4. Datalist de códigos gerados para abas vinculadas
                if fname == "codigo_projeto" and sugestoes:
                    field.widget.attrs["list"] = f"dl-{spec.slug}-projetos"
                    field.help_text = (
                        "Selecione um código de projeto gerado no ciclo ou informe o código EMBRAPII."
                    )

        def clean_projeto_oficial(self):
            proj = self.cleaned_data.get("projeto_oficial")
            validar_vinculo_projeto_oficial(spec, proj)
            return proj

        def clean(self):
            cleaned = super().clean()
            # Validações condicionais de observação quando opção "Outro(s)" é escolhida
            obs_field = "observacoes" if "observacoes" in self.fields else (
                "observacao" if "observacao" in self.fields else None
            )
            if obs_field:
                obs_val = (cleaned.get(obs_field) or "").strip()
                for check_name in (
                    "atividade_funcao",
                    "tipo_evento",
                    "tipo_participacao",
                    "vinculo_profissional",
                    "tipo_interacao",
                ):
                    val = str(cleaned.get(check_name) or "").lower()
                    if ("outro" in val or "outra" in val) and not obs_val:
                        self.add_error(
                            obs_field,
                            "Especifique os detalhes nas observações quando selecionar a opção 'Outro(s)'.",
                        )
                        break
            return cleaned

    return _DynamicTabForm(*args, **kwargs)


class SubmissaoCompetenciaForm(forms.Form):
    observacao_submissao = forms.CharField(
        label="Observação / Síntese da entrega mensal",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Opcional: notas para a coordenação..."}),
    )


class CicloSemestralConfigForm(forms.ModelForm):
    class Meta:
        model = CicloSemestral
        fields = [
            "centro_competencia",
            "abreviacao_cc",
            "termo_cooperacao",
            "periodo_referencia_label",
            "coordenacao_nome",
            "coordenacao_email",
            "status",
        ]


class PilarSemestralConfigForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoPilarSemestral
        fields = [
            "responsavel",
            "responsavel_nome",
            "responsavel_email",
            "dia_limite_mensal",
            "ativo",
        ]
