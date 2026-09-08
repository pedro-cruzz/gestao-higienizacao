import textwrap
from datetime import timedelta, time
from io import BytesIO
from urllib.parse import quote_plus

from django.contrib import messages
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from service.forms import AdicionalOrcamentoForm, ClienteVinculoOrcamentoForm, MultiplicadorOrcamentoForm, OrcamentoForm
from service.models import AdicionalOrcamento, Cliente, Lead, MultiplicadorOrcamento, Orcamento, OrdemServico
from service.ownership import owned_queryset
from service.services.nominatim import (
    NominatimLookupError,
    NominatimService,
    NominatimTemporaryUnavailableError,
)
from service.services.viacep import ViaCepLookupError, ViaCepService, ViaCepTemporaryUnavailableError


def _endereco_para_mapa(orcamento: Orcamento) -> str:
    partes = [
        orcamento.logradouro,
        orcamento.numero,
        orcamento.bairro,
        orcamento.cidade,
        orcamento.uf,
        orcamento.cep,
    ]
    endereco_estruturado = ", ".join(str(parte).strip() for parte in partes if parte)
    return endereco_estruturado or (orcamento.endereco or "").strip()


def _links_mapa_orcamento(orcamento: Orcamento) -> dict[str, str]:
    endereco = _endereco_para_mapa(orcamento)
    if not endereco:
        return {}

    query = quote_plus(endereco)
    return {
        "endereco": endereco,
        "embed_url": f"https://www.google.com/maps?q={query}&output=embed",
        "maps_url": f"https://www.google.com/maps/search/?api=1&query={query}",
        "rota_url": f"https://www.google.com/maps/dir/?api=1&destination={query}&travelmode=driving",
    }


def _criar_ou_atualizar_cliente_do_orcamento(orcamento: Orcamento) -> Cliente:
    cliente = Cliente.objects.filter(owner=orcamento.owner, email=orcamento.email).first()
    if cliente is None:
        return Cliente.objects.create(
            owner=orcamento.owner,
            name=orcamento.name,
            email=orcamento.email,
            telefone=orcamento.telefone,
            endereco=orcamento.endereco,
            cep=orcamento.cep,
            logradouro=orcamento.logradouro,
            numero=orcamento.numero,
            complemento=orcamento.complemento,
            bairro=orcamento.bairro,
            cidade=orcamento.cidade,
            uf=orcamento.uf,
            status=Cliente.Status.CONVERTIDO,
        )

    cliente.name = orcamento.name
    cliente.telefone = orcamento.telefone
    cliente.endereco = orcamento.endereco
    cliente.cep = orcamento.cep
    cliente.logradouro = orcamento.logradouro
    cliente.numero = orcamento.numero
    cliente.complemento = orcamento.complemento
    cliente.bairro = orcamento.bairro
    cliente.cidade = orcamento.cidade
    cliente.uf = orcamento.uf
    cliente.status = Cliente.Status.CONVERTIDO
    cliente.save()
    return cliente


def listar_orcamentos(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    todos_orcamentos = owned_queryset(
        Orcamento.objects.prefetch_related("itens", "cliente"),
        request.user,
    ).order_by("-created_at", "-id")
    orcamentos = todos_orcamentos

    if busca:
        orcamentos = orcamentos.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(telefone__icontains=busca)
            | Q(descricao__icontains=busca)
        )

    total_orcamentos = todos_orcamentos.count()
    total_rascunhos = todos_orcamentos.filter(aprovado=False).count()
    total_enviados = 0
    total_aprovados = todos_orcamentos.filter(aprovado=True).count()
    total_recusados = 0

    linhas_orcamentos = []
    for orcamento in orcamentos:
        itens = list(orcamento.itens.all())
        servico = " + ".join(item.name for item in itens[:2]) if itens else (orcamento.descricao or "Serviço não informado")
        if len(itens) > 2:
            servico = f"{servico} +{len(itens) - 2}"

        if orcamento.aprovado:
            status_label = "Aprovado"
            status_class = "status-soft-blue"
        else:
            status_label = "Rascunho"
            status_class = "status-gray"

        linhas_orcamentos.append(
            {
                "obj": orcamento,
                "numero": f"#{orcamento.pk}",
                "cliente": orcamento.name,
                "contato": orcamento.telefone or orcamento.email or "-",
                "servico": servico,
                "valor": orcamento.valor,
                "status_label": status_label,
                "status_class": status_class,
                "data": orcamento.created_at,
                "validade": orcamento.created_at + timedelta(days=15),
                "pode_aprovar": not orcamento.aprovado,
            }
        )

    context = {
        "busca": busca,
        "orcamentos": linhas_orcamentos,
        "total_orcamentos": total_orcamentos,
        "total_filtrado": len(linhas_orcamentos),
        "total_rascunhos": total_rascunhos,
        "total_enviados": total_enviados,
        "total_aprovados": total_aprovados,
        "total_recusados": total_recusados,
    }
    return render(request, "service/orcamentos.html", context)


def _ajustes_orcamento_context(request: HttpRequest, busca: str = "") -> dict:
    adicionais = owned_queryset(AdicionalOrcamento.objects, request.user).order_by("name", "id")
    multiplicadores = owned_queryset(MultiplicadorOrcamento.objects, request.user).order_by("name", "id")
    if busca:
        adicionais = adicionais.filter(name__icontains=busca)
        multiplicadores = multiplicadores.filter(name__icontains=busca)

    return {
        "busca": busca,
        "adicionais": adicionais,
        "multiplicadores": multiplicadores,
        "total_adicionais": adicionais.count(),
        "total_multiplicadores": multiplicadores.count(),
        "total_adicionais_ativos": adicionais.filter(ativo=True).count(),
        "total_multiplicadores_ativos": multiplicadores.filter(ativo=True).count(),
        "total_regras": adicionais.count() + multiplicadores.count(),
        "total_ativos": adicionais.filter(ativo=True).count() + multiplicadores.filter(ativo=True).count(),
    }


def _ajustes_orcamento_return_target(request: HttpRequest) -> str:
    return request.POST.get("return_url") or request.GET.get("next") or ""


def _ajustes_orcamento_return_url(request: HttpRequest) -> str:
    destino = _ajustes_orcamento_return_target(request)
    if destino == "configuracoes":
        return f"{reverse('configuracoes')}?tab=precos"
    return reverse("adicionais_orcamento")


def listar_adicionais_orcamento(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    context = _ajustes_orcamento_context(request, busca)
    return render(request, "service/adicionais_orcamento.html", context)


def novo_adicional_orcamento(request: HttpRequest) -> HttpResponse:
    return_url = _ajustes_orcamento_return_url(request)
    if request.method == "POST":
        form = AdicionalOrcamentoForm(request.POST)
        if form.is_valid():
            adicional = form.save(commit=False)
            adicional.owner = request.user
            adicional.save()
            messages.success(request, f"Adicional '{adicional.name}' cadastrado com sucesso.")
            return redirect(return_url)
    else:
        form = AdicionalOrcamentoForm(
            initial={
                "ativo": True,
                "tipo_valor": AdicionalOrcamento.TipoValor.FIXO,
                "valor": 0,
            }
        )

    context = {
        **_ajustes_orcamento_context(request),
        "form": form,
        "is_edit": False,
        "return_url": return_url,
        "return_target": _ajustes_orcamento_return_target(request),
    }
    return render(request, "service/adicional_orcamento_form.html", context)


def editar_adicional_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    return_url = _ajustes_orcamento_return_url(request)
    adicional = get_object_or_404(owned_queryset(AdicionalOrcamento.objects, request.user), pk=pk)
    if request.method == "POST":
        form = AdicionalOrcamentoForm(request.POST, instance=adicional)
        if form.is_valid():
            adicional = form.save()
            messages.success(request, f"Adicional '{adicional.name}' atualizado com sucesso.")
            return redirect(return_url)
    else:
        form = AdicionalOrcamentoForm(instance=adicional)

    context = {
        **_ajustes_orcamento_context(request),
        "form": form,
        "adicional": adicional,
        "is_edit": True,
        "return_url": return_url,
        "return_target": _ajustes_orcamento_return_target(request),
    }
    return render(request, "service/adicional_orcamento_form.html", context)


def deletar_adicional_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("adicionais_orcamento")

    return_url = _ajustes_orcamento_return_url(request)
    adicional = get_object_or_404(owned_queryset(AdicionalOrcamento.objects, request.user), pk=pk)
    nome = adicional.name
    adicional.delete()
    messages.success(request, f"Adicional '{nome}' excluído com sucesso.")
    return redirect(return_url)


def novo_multiplicador_orcamento(request: HttpRequest) -> HttpResponse:
    return_url = _ajustes_orcamento_return_url(request)
    if request.method == "POST":
        form = MultiplicadorOrcamentoForm(request.POST)
        if form.is_valid():
            multiplicador = form.save(commit=False)
            multiplicador.owner = request.user
            multiplicador.save()
            messages.success(request, f"Multiplicador '{multiplicador.name}' cadastrado com sucesso.")
            return redirect(return_url)
    else:
        form = MultiplicadorOrcamentoForm(initial={"ativo": True, "fator": 1.5})

    context = {
        **_ajustes_orcamento_context(request),
        "form": form,
        "is_edit": False,
        "return_url": return_url,
        "return_target": _ajustes_orcamento_return_target(request),
    }
    return render(request, "service/multiplicador_orcamento_form.html", context)


def editar_multiplicador_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    return_url = _ajustes_orcamento_return_url(request)
    multiplicador = get_object_or_404(owned_queryset(MultiplicadorOrcamento.objects, request.user), pk=pk)
    if request.method == "POST":
        form = MultiplicadorOrcamentoForm(request.POST, instance=multiplicador)
        if form.is_valid():
            multiplicador = form.save()
            messages.success(request, f"Multiplicador '{multiplicador.name}' atualizado com sucesso.")
            return redirect(return_url)
    else:
        form = MultiplicadorOrcamentoForm(instance=multiplicador)

    context = {
        **_ajustes_orcamento_context(request),
        "form": form,
        "multiplicador": multiplicador,
        "is_edit": True,
        "return_url": return_url,
        "return_target": _ajustes_orcamento_return_target(request),
    }
    return render(request, "service/multiplicador_orcamento_form.html", context)


def deletar_multiplicador_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("adicionais_orcamento")

    return_url = _ajustes_orcamento_return_url(request)
    multiplicador = get_object_or_404(owned_queryset(MultiplicadorOrcamento.objects, request.user), pk=pk)
    nome = multiplicador.name
    multiplicador.delete()
    messages.success(request, f"Multiplicador '{nome}' excluído com sucesso.")
    return redirect(return_url)


def _nome_servico_ordem(orcamento: Orcamento) -> str:
    itens = list(orcamento.itens.all())
    if itens:
        return " + ".join(item.name for item in itens[:2])
    return orcamento.descricao or "Serviço cadastrado"


def _criar_ordem_servico_automaticamente(orcamento: Orcamento) -> None:
    try:
        if orcamento.ordem_servico is not None:
            return
    except OrdemServico.DoesNotExist:
        pass

    OrdemServico.objects.create(
        owner=orcamento.owner,
        orcamento=orcamento,
        cliente=orcamento.cliente,
        titulo=_nome_servico_ordem(orcamento),
        descricao=orcamento.descricao,
        endereco=orcamento.endereco or _endereco_para_mapa(orcamento),
        data_agendada=timezone.localdate(),
        hora_inicio=time(8, 0),
        status=OrdemServico.Status.AGENDADA,
        valor=orcamento.valor or 0,
    )


def _deve_criar_ordem_servico(request: HttpRequest) -> bool:
    return request.POST.get("criar_ordem_servico", "1") != "0"


def _criar_ordem_servico_se_solicitado(orcamento: Orcamento, request: HttpRequest) -> None:
    if _deve_criar_ordem_servico(request):
        _criar_ordem_servico_automaticamente(orcamento)


def _dinheiro_ordem(valor: float) -> str:
    valor_formatado = f"{valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor_formatado}"


def _status_ordem(orcamento: Orcamento) -> str:
    if not orcamento.aprovado:
        return "agendada" if orcamento.cliente_id or orcamento.email else "aguardando"

    data_atualizacao = timezone.localtime(orcamento.updated_at).date()
    if data_atualizacao >= timezone.localdate():
        return "execucao"
    return "concluida"


def _agenda_ordem(orcamento: Orcamento, status: str) -> str:
    if status == "aguardando":
        return ""

    data_atualizacao = timezone.localtime(orcamento.updated_at)
    if status == "execucao" and data_atualizacao.date() == timezone.localdate():
        return f"Hoje {data_atualizacao:%H:%M}"
    if status == "concluida":
        return data_atualizacao.strftime("%d/%m/%Y")
    return data_atualizacao.strftime("%d/%m/%Y %H:%M")


def _colunas_ordens_base() -> list[dict]:
    return [
        {
            "key": "aguardando",
            "title": "Aguardando Agendamento",
            "cards": [],
        },
        {
            "key": "agendada",
            "title": "Agendada",
            "cards": [],
        },
        {
            "key": "execucao",
            "title": "Em Execução",
            "cards": [],
        },
        {
            "key": "concluida",
            "title": "Concluída",
            "cards": [],
        },
    ]


def _colunas_ordens_exemplo() -> list[dict]:
    colunas = _colunas_ordens_base()
    exemplos = {
        "aguardando": [
            ("#1250", "Aguardando", "Roberta Silva", "Limpeza de Sofá", "", "R$ 520"),
            ("#1248", "Aguardando", "Eduardo Costa", "Higienização de Tapete", "", "R$ 380"),
        ],
        "agendada": [
            ("#1247", "Agendada", "Mariana Alves", "Limpeza de Colchão", "30/04/2026 14:00", "R$ 290"),
            ("#1244", "Agendada", "Júlia Ferreira", "Higienização de Tapete", "01/05/2026 10:00", "R$ 320"),
        ],
        "execucao": [
            ("#1245", "Em", "Pedro Lima", "Limpeza de Sofá", "Hoje 09:00", "R$ 450"),
        ],
        "concluida": [
            ("#1243", "Concluída", "Roberto Alves", "Limpeza de Estofados", "28/04/2026", "R$ 680"),
            ("#1242", "Concluída", "Camila Santos", "Impermeabilização", "27/04/2026", "R$ 520"),
        ],
    }

    for coluna in colunas:
        coluna["cards"] = [
            {
                "numero": numero,
                "status_label": status_label,
                "cliente": cliente,
                "servico": servico,
                "agenda": agenda,
                "valor": valor,
                "status_key": coluna["key"],
                "obj": None,
            }
            for numero, status_label, cliente, servico, agenda, valor in exemplos[coluna["key"]]
        ]
    return colunas


def listar_ordens_servico(request: HttpRequest) -> HttpResponse:
    orcamentos = list(
        owned_queryset(Orcamento.objects.prefetch_related("itens", "cliente"), request.user)
        .order_by("-updated_at", "-id")[:12]
    )

    if not orcamentos:
        colunas = _colunas_ordens_exemplo()
    else:
        colunas = _colunas_ordens_base()
        colunas_por_status = {coluna["key"]: coluna for coluna in colunas}
        status_labels = {
            "aguardando": "Aguardando",
            "agendada": "Agendada",
            "execucao": "Em",
            "concluida": "Concluída",
        }

        for orcamento in orcamentos:
            status_key = _status_ordem(orcamento)
            colunas_por_status[status_key]["cards"].append(
                {
                    "numero": f"#{orcamento.pk}",
                    "status_label": status_labels[status_key],
                    "cliente": orcamento.name,
                    "servico": _nome_servico_ordem(orcamento),
                    "agenda": _agenda_ordem(orcamento, status_key),
                    "valor": _dinheiro_ordem(orcamento.valor),
                    "status_key": status_key,
                    "obj": orcamento,
                }
            )

    return render(request, "service/ordens_servico.html", {"colunas_ordens": colunas})


def _orcamento_initial_lead(lead: Lead, item_inicial: str | None = None) -> dict:
    initial = {
        "lead": lead.pk,
        "name": lead.name,
        "email": lead.email,
        "telefone": lead.telefone,
        "cep": lead.cep,
        "logradouro": lead.logradouro,
        "numero": lead.numero,
        "complemento": lead.complemento,
        "bairro": lead.bairro,
        "cidade": lead.cidade,
        "uf": lead.uf,
        "endereco": lead.endereco,
        "quantidade": 1,
    }
    if item_inicial:
        initial["itens"] = [item_inicial]
    return initial


def _adicionais_context(request: HttpRequest, form: OrcamentoForm) -> dict:
    if form.is_bound:
        selecionados = set(form.data.getlist("adicionais"))
        multiplicadores_selecionados = set(form.data.getlist("multiplicadores"))
    else:
        selecionados = {str(pk) for pk in (form.initial.get("adicionais") or [])}
        multiplicadores_selecionados = {str(pk) for pk in (form.initial.get("multiplicadores") or [])}

    return {
        "adicionais_disponiveis": owned_queryset(AdicionalOrcamento.objects, request.user).filter(ativo=True).order_by("name", "id"),
        "adicionais_selecionados": selecionados,
        "multiplicadores_disponiveis": owned_queryset(MultiplicadorOrcamento.objects, request.user).filter(ativo=True).order_by("name", "id"),
        "multiplicadores_selecionados": multiplicadores_selecionados,
    }


def novo_orcamento(request: HttpRequest) -> HttpResponse:
    lead_id = request.GET.get("lead")
    lead = owned_queryset(Lead.objects, request.user).filter(pk=lead_id).first() if lead_id else None

    if request.method == "POST":
        form = OrcamentoForm(request.POST, user=request.user)
        if form.is_valid():
            orcamento = Orcamento.objects.create(
                owner=request.user,
                name=form.cleaned_data["name"] or form.cleaned_data["cliente"].name,
                email=form.cleaned_data["email"] or None,
                quantidade=form.cleaned_data["quantidade"],
                valor=0,
                lead=lead or form.cleaned_data.get("lead"),
            )
            _salvar_dados_orcamento(orcamento, form)
            _aplicar_fluxo_cliente(orcamento, form)
            if orcamento.lead_id and orcamento.cliente_id:
                _marcar_lead_convertido(orcamento, orcamento.cliente)
            elif orcamento.lead_id:
                _marcar_lead_contatado_por_orcamento(orcamento)

            messages.success(request, "Orçamento criado com sucesso.")
            return redirect("orcamento_detalhe", pk=orcamento.pk)
    else:
        item_inicial = request.GET.get("item")
        initial = _orcamento_initial_lead(lead, item_inicial) if lead else {"itens": [item_inicial]} if item_inicial else None
        form = OrcamentoForm(initial=initial, user=request.user)

    context = {
        "form": form,
        "orcamentos_recentes": owned_queryset(Orcamento.objects.prefetch_related("itens"), request.user).order_by("-id")[:5],
        **_adicionais_context(request, form),
    }
    return render(request, "service/orcamento_form.html", context)


def buscar_cliente_dados(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Método não permitido."}, status=405)

    cliente = get_object_or_404(owned_queryset(Cliente.objects, request.user), pk=pk)
    return JsonResponse(
        {
            "ok": True,
            "cliente": {
                "id": cliente.pk,
                "name": cliente.name,
                "email": cliente.email,
                "telefone": cliente.telefone or "",
                "endereco": cliente.endereco or "",
                "cep": cliente.cep or "",
                "logradouro": cliente.logradouro or "",
                "numero": cliente.numero or "",
                "complemento": cliente.complemento or "",
                "bairro": cliente.bairro or "",
                "cidade": cliente.cidade or "",
                "uf": cliente.uf or "",
            },
        }
    )


def buscar_lead_dados(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Método não permitido."}, status=405)

    lead = get_object_or_404(owned_queryset(Lead.objects, request.user), pk=pk)
    return JsonResponse(
        {
            "ok": True,
            "lead": {
                "id": lead.pk,
                "name": lead.name,
                "email": lead.email or "",
                "telefone": lead.telefone or "",
                "endereco": lead.endereco or "",
                "cep": lead.cep or "",
                "logradouro": lead.logradouro or "",
                "numero": lead.numero or "",
                "complemento": lead.complemento or "",
                "bairro": lead.bairro or "",
                "cidade": lead.cidade or "",
                "uf": lead.uf or "",
            },
        }
    )


def _orcamento_initial(orcamento: Orcamento) -> dict:
    return {
        "lead": orcamento.lead_id,
        "cliente": orcamento.cliente_id,
        "name": orcamento.name,
        "email": orcamento.email,
        "telefone": orcamento.telefone,
        "cep": orcamento.cep,
        "logradouro": orcamento.logradouro,
        "numero": orcamento.numero,
        "complemento": orcamento.complemento,
        "bairro": orcamento.bairro,
        "cidade": orcamento.cidade,
        "uf": orcamento.uf,
        "endereco": orcamento.endereco,
        "descricao": orcamento.descricao,
        "quantidade": orcamento.quantidade,
        "itens": list(orcamento.itens.values_list("pk", flat=True)),
        "adicionais": list(orcamento.adicionais.values_list("pk", flat=True)),
        "multiplicadores": list(orcamento.multiplicadores.values_list("pk", flat=True)),
        "criar_cliente_automatico": False,
    }


def _salvar_dados_orcamento(orcamento: Orcamento, form: OrcamentoForm) -> Orcamento:
    itens = list(form.cleaned_data["itens"])
    adicionais = list(form.cleaned_data.get("adicionais") or [])
    multiplicadores = list(form.cleaned_data.get("multiplicadores") or [])
    quantidade = form.cleaned_data["quantidade"]
    valor_servicos = sum(item.valor for item in itens)
    valor_adicionais_fixos = sum(
        adicional.valor
        for adicional in adicionais
        if adicional.tipo_valor != AdicionalOrcamento.TipoValor.PERCENTUAL
    )
    percentual_adicionais = sum(
        adicional.valor
        for adicional in adicionais
        if adicional.tipo_valor == AdicionalOrcamento.TipoValor.PERCENTUAL
    )
    valor_adicionais = valor_adicionais_fixos + (valor_servicos * percentual_adicionais / 100)
    fator_servicos = 1
    fator_total = 1
    for multiplicador in multiplicadores:
        fator = float(multiplicador.fator or 1)
        if multiplicador.aplica_em == MultiplicadorOrcamento.Aplicacao.SERVICOS:
            fator_servicos *= fator
        else:
            fator_total *= fator

    orcamento.name = form.cleaned_data["name"]
    orcamento.email = form.cleaned_data["email"]
    orcamento.telefone = form.cleaned_data["telefone"] or None
    orcamento.endereco = form.cleaned_data["endereco"] or None
    orcamento.cep = form.cleaned_data["cep"] or None
    orcamento.logradouro = form.cleaned_data["logradouro"] or None
    orcamento.numero = form.cleaned_data["numero"] or None
    orcamento.complemento = form.cleaned_data["complemento"] or None
    orcamento.bairro = form.cleaned_data["bairro"] or None
    orcamento.cidade = form.cleaned_data["cidade"] or None
    orcamento.uf = form.cleaned_data["uf"] or None
    orcamento.descricao = form.cleaned_data["descricao"] or None
    orcamento.quantidade = quantidade
    orcamento.valor = ((valor_servicos * fator_servicos) + valor_adicionais) * quantidade * fator_total
    orcamento.cliente = form.cleaned_data.get("cliente") or orcamento.cliente
    orcamento.lead = form.cleaned_data.get("lead") or orcamento.lead
    orcamento.save()
    orcamento.itens.set(itens)
    orcamento.adicionais.set(adicionais)
    orcamento.multiplicadores.set(multiplicadores)
    return orcamento


def _marcar_lead_convertido(orcamento: Orcamento, cliente: Cliente | None = None) -> None:
    if not orcamento.lead_id:
        return

    lead = orcamento.lead
    lead.status = Lead.Status.CONVERTIDO
    update_fields = ["status", "updated_at"]
    if cliente and lead.cliente_id != cliente.pk:
        lead.cliente = cliente
        update_fields.append("cliente")
    lead.save(update_fields=update_fields)


def _marcar_lead_contatado_por_orcamento(orcamento: Orcamento) -> None:
    if not orcamento.lead_id or orcamento.cliente_id:
        return

    lead = orcamento.lead
    if lead.status != Lead.Status.NOVO:
        return

    lead.status = Lead.Status.CONTATADO
    lead.save(update_fields=["status", "updated_at"])


def _aplicar_fluxo_cliente(orcamento: Orcamento, form: OrcamentoForm) -> None:
    cliente = form.cleaned_data.get("cliente")
    if cliente:
        orcamento.cliente = cliente
        orcamento.save(update_fields=["cliente", "updated_at"])
        _marcar_lead_convertido(orcamento, cliente)
        return

    if form.cleaned_data.get("criar_cliente_automatico"):
        cliente = _criar_ou_atualizar_cliente_do_orcamento(orcamento)
        orcamento.cliente = cliente
        orcamento.save(update_fields=["cliente", "updated_at"])
        _marcar_lead_convertido(orcamento, cliente)


def editar_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    orcamento = get_object_or_404(
        owned_queryset(Orcamento.objects.prefetch_related("itens"), request.user),
        pk=pk,
    )

    if request.method == "POST":
        form = OrcamentoForm(request.POST, user=request.user)
        if form.is_valid():
            _salvar_dados_orcamento(orcamento, form)
            _aplicar_fluxo_cliente(orcamento, form)
            messages.success(request, "Orçamento atualizado com sucesso.")
            return redirect("orcamento_detalhe", pk=orcamento.pk)
    else:
        form = OrcamentoForm(initial=_orcamento_initial(orcamento), user=request.user)

    context = {
        "form": form,
        "orcamento": orcamento,
        "orcamentos_recentes": owned_queryset(Orcamento.objects.prefetch_related("itens"), request.user).exclude(pk=orcamento.pk).order_by("-id")[:5],
        "form_title": "Editar orçamento",
        "form_intro": "Atualize os dados do cliente, endereço, itens e quantidade deste orçamento.",
        "form_submit_label": "Salvar alterações",
        **_adicionais_context(request, form),
    }
    return render(request, "service/orcamento_form.html", context)


def buscar_endereco_cep(request: HttpRequest, cep: str) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Método não permitido."}, status=405)

    try:
        endereco = ViaCepService().buscar_por_cep(cep)
    except ViaCepTemporaryUnavailableError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    except ViaCepLookupError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "endereco": endereco.as_dict()})


def buscar_mapa_orcamento(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Método não permitido."}, status=405)

    orcamento = get_object_or_404(owned_queryset(Orcamento.objects, request.user), pk=pk)
    endereco = _endereco_para_mapa(orcamento)
    if not endereco:
        return JsonResponse(
            {"ok": False, "error": "Cadastre o endereço do serviço para visualizar o mapa."},
            status=400,
        )

    try:
        localizacao = NominatimService().geocodificar(
            endereco=endereco,
            cep=orcamento.cep or "",
            logradouro=orcamento.logradouro or orcamento.endereco or "",
            numero=orcamento.numero or "",
            bairro=orcamento.bairro or "",
            cidade=orcamento.cidade or "",
            uf=orcamento.uf or "",
        )
    except NominatimTemporaryUnavailableError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    except NominatimLookupError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "endereco": endereco,
            "localizacao": localizacao.as_dict(),
        }
    )


def detalhe_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    orcamento = get_object_or_404(
        owned_queryset(Orcamento.objects.prefetch_related("itens", "cliente"), request.user),
        pk=pk,
    )
    context = {
        "orcamento": orcamento,
        "itens": orcamento.itens.all(),
        "mapa": _links_mapa_orcamento(orcamento),
        "ordem_servico": getattr(orcamento, "ordem_servico", None),
        "vinculo_form": ClienteVinculoOrcamentoForm(
            initial={"cliente": orcamento.cliente_id} if orcamento.cliente_id else None,
            user=request.user,
        ),
        "total_clientes": owned_queryset(Cliente.objects, request.user).count(),
    }
    return render(request, "service/orcamento_detalhe.html", context)


def vincular_cliente_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(owned_queryset(Orcamento.objects, request.user), pk=pk)
    form = ClienteVinculoOrcamentoForm(request.POST, user=request.user)
    if form.is_valid():
        cliente = form.cleaned_data["cliente"]
        orcamento.cliente = cliente
        update_fields = ["cliente", "updated_at"]
        if request.POST.get("aprovar_orcamento") == "1":
            orcamento.aprovado = True
            update_fields.append("aprovado")
        orcamento.save(update_fields=update_fields)
        _marcar_lead_convertido(orcamento, cliente)
        if orcamento.aprovado:
            _criar_ordem_servico_se_solicitado(orcamento, request)
            messages.success(request, f"Orçamento aprovado e vinculado ao cliente '{cliente.name}'.")
        else:
            messages.success(request, f"Cliente '{cliente.name}' vinculado ao orçamento.")
            if request.POST.get("voltar_para_aprovacao") == "1":
                return redirect(f"{reverse('orcamento_detalhe', args=[pk])}?aprovar=1")
    else:
        messages.error(request, "Selecione um cliente válido para vincular ao orçamento.")

    return redirect("orcamento_detalhe", pk=pk)


def deletar_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(owned_queryset(Orcamento.objects, request.user), pk=pk)
    nome = orcamento.name
    orcamento.delete()

    messages.success(request, f"Orçamento de '{nome}' excluído com sucesso.")
    return redirect("orcamentos")


def concluir_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(owned_queryset(Orcamento.objects, request.user), pk=pk)
    if not orcamento.aprovado:
        if not orcamento.cliente_id:
            messages.error(
                request,
                "Vincule ou crie um cliente antes de aprovar o orçamento.",
            )
            return redirect(f"{reverse('orcamento_detalhe', args=[pk])}?aprovar=1")
        orcamento.aprovado = True
        orcamento.save(update_fields=["aprovado", "updated_at"])
        _marcar_lead_convertido(orcamento, orcamento.cliente)
        _criar_ordem_servico_se_solicitado(orcamento, request)
        messages.success(request, "Orçamento aprovado com sucesso.")
    else:
        messages.info(request, "Este orçamento já está aprovado.")

    return redirect("orcamento_detalhe", pk=pk)


def cadastrar_cliente_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(owned_queryset(Orcamento.objects, request.user), pk=pk)

    if not orcamento.email:
        messages.error(
            request,
            "Este orçamento precisa de um email para criar o cadastro do cliente.",
        )
        return redirect("orcamento_detalhe", pk=pk)

    cliente = _criar_ou_atualizar_cliente_do_orcamento(orcamento)
    orcamento.cliente = cliente
    update_fields = ["cliente", "updated_at"]
    if request.POST.get("aprovar_orcamento") == "1":
        orcamento.aprovado = True
        update_fields.append("aprovado")
    orcamento.save(update_fields=update_fields)
    _marcar_lead_convertido(orcamento, cliente)
    if orcamento.aprovado:
        _criar_ordem_servico_se_solicitado(orcamento, request)
        messages.success(request, "Orçamento aprovado e cliente vinculado com sucesso.")
    else:
        messages.success(
            request,
            "Cliente cadastrado e vinculado ao orçamento com sucesso.",
        )
        if request.POST.get("voltar_para_aprovacao") == "1":
            return redirect(f"{reverse('orcamento_detalhe', args=[pk])}?aprovar=1")
    return redirect("orcamento_detalhe", pk=pk)


def aprovar_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(owned_queryset(Orcamento.objects, request.user), pk=pk)

    if not orcamento.email:
        messages.error(
            request,
            "Este orçamento precisa de um email para criar o cadastro do cliente.",
        )
        return redirect("orcamento_detalhe", pk=pk)

    cliente = _criar_ou_atualizar_cliente_do_orcamento(orcamento)
    orcamento.cliente = cliente
    orcamento.aprovado = True
    orcamento.save(update_fields=["cliente", "aprovado", "updated_at"])
    _marcar_lead_convertido(orcamento, cliente)
    _criar_ordem_servico_se_solicitado(orcamento, request)

    messages.success(
        request,
        "Orçamento aprovado e cliente vinculado com sucesso.",
    )
    return redirect("orcamento_detalhe", pk=pk)


def gerar_orcamento_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    orcamento = get_object_or_404(
        owned_queryset(
            Orcamento.objects.select_related("cliente").prefetch_related("itens", "adicionais", "multiplicadores"),
            request.user,
        ),
        pk=pk,
    )
    itens = list(orcamento.itens.all())

    def clean_text(value: str, limit: int) -> str:
        return " ".join((value or "").split())[:limit]

    def clean_color(value: str) -> str:
        value = (value or "").strip()
        if len(value) == 7 and value.startswith("#"):
            hex_part = value[1:]
            if all(char in "0123456789abcdefABCDEF" for char in hex_part):
                return value
        return "#2664EB"

    def image_reader_from_bytes(logo_bytes: bytes):
        try:
            return ImageReader(BytesIO(logo_bytes))
        except Exception:
            return None

    def load_uploaded_logo_bytes():
        uploaded_logo = request.FILES.get("pdf_logo")
        if not uploaded_logo:
            return None

        allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
        if uploaded_logo.content_type not in allowed_types:
            return None

        logo_bytes = uploaded_logo.read(3 * 1024 * 1024 + 1)
        if len(logo_bytes) > 3 * 1024 * 1024:
            return None

        if image_reader_from_bytes(logo_bytes) is None:
            return None
        return logo_bytes

    def load_saved_logo():
        if not orcamento.pdf_logo:
            return None
        try:
            orcamento.pdf_logo.open("rb")
            return image_reader_from_bytes(orcamento.pdf_logo.read())
        except Exception:
            return None
        finally:
            try:
                orcamento.pdf_logo.close()
            except Exception:
                pass

    pdf_brand = clean_text(request.POST.get("pdf_brand", ""), 42) or "HigiFlow"
    pdf_phrase = clean_text(request.POST.get("pdf_phrase", orcamento.pdf_frase_cliente or ""), 180)
    accent_color = clean_color(request.POST.get("pdf_accent_color", ""))
    uploaded_logo_bytes = load_uploaded_logo_bytes()
    if request.method == "POST":
        orcamento.pdf_frase_cliente = pdf_phrase
        update_fields = ["pdf_frase_cliente", "updated_at"]
        if uploaded_logo_bytes:
            orcamento.pdf_logo.save(
                request.FILES["pdf_logo"].name,
                ContentFile(uploaded_logo_bytes),
                save=False,
            )
            update_fields.append("pdf_logo")
        orcamento.save(update_fields=update_fields)
    uploaded_logo = image_reader_from_bytes(uploaded_logo_bytes) if uploaded_logo_bytes else load_saved_logo()

    page_width, page_height = A4
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Proposta comercial {orcamento.pk}")

    ink = colors.HexColor("#0A0A0A")
    muted = colors.HexColor("#717182")
    soft_text = colors.HexColor("#8A95A6")
    line = colors.HexColor("#E5E7EB")
    panel = colors.white
    surface = colors.HexColor("#F8FAFF")
    accent = colors.HexColor(accent_color)
    accent_soft = colors.HexColor("#DBEAFE")

    card_x = 24
    card_y = 22
    card_w = page_width - (card_x * 2)
    card_h = page_height - (card_y * 2)
    body_pad = 32
    body_x = card_x + body_pad
    body_w = card_w - (body_pad * 2)
    footer_h = 52
    header_h = 72
    meta_h = 42
    emission = timezone.localdate()
    valid_until = emission + timedelta(days=15)
    emission_date = emission.strftime("%d/%m/%Y")
    valid_until_date = valid_until.strftime("%d/%m/%Y")
    doc_number = f"#{orcamento.pk:04d}"
    note_text = pdf_phrase

    company_defaults = {
        "razao_social": "HigiFlow Limpeza Profissional Ltda",
        "cnpj": "12.345.678/0001-90",
        "telefone": "(11) 3456-7890",
        "email": "contato@higiflow.com.br",
        "cep": "01234-567",
        "endereco": "Av. Paulista, 1000",
        "bairro": "Centro",
        "cidade": "São Paulo, SP",
    }
    company_config = {**company_defaults, **request.session.get("empresa_config", {})}
    if request.POST.get("pdf_brand"):
        company_config["razao_social"] = pdf_brand

    adicionais = list(orcamento.adicionais.all())
    multiplicadores = list(orcamento.multiplicadores.all())
    valor_servicos = sum(float(item.valor or 0) for item in itens)
    valor_adicionais_fixos = sum(
        float(adicional.valor or 0)
        for adicional in adicionais
        if adicional.tipo_valor != AdicionalOrcamento.TipoValor.PERCENTUAL
    )
    percentual_adicionais = sum(
        float(adicional.valor or 0)
        for adicional in adicionais
        if adicional.tipo_valor == AdicionalOrcamento.TipoValor.PERCENTUAL
    )
    valor_adicionais_unitario = valor_adicionais_fixos + (valor_servicos * percentual_adicionais / 100)
    fator_servicos = 1.0
    fator_total = 1.0
    for multiplicador in multiplicadores:
        fator = float(multiplicador.fator or 1)
        if multiplicador.aplica_em == MultiplicadorOrcamento.Aplicacao.SERVICOS:
            fator_servicos *= fator
        else:
            fator_total *= fator
    fator_multiplicadores = fator_servicos * fator_total
    subtotal_orcamento = ((valor_servicos * fator_servicos) + valor_adicionais_unitario) * orcamento.quantidade

    def pdf_text(value: object, fallback: str = "-") -> str:
        text = " ".join(str(value or fallback).split())
        return text.encode("latin-1", "replace").decode("latin-1")

    def money(value: float) -> str:
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def text_width(text: str, font_name: str, font_size: float) -> float:
        return pdf.stringWidth(text, font_name, font_size)

    def split_long_word(word: str, max_width: float, font_name: str, font_size: float) -> list[str]:
        pieces = []
        piece = ""
        for char in word:
            candidate = f"{piece}{char}"
            if piece and text_width(candidate, font_name, font_size) > max_width:
                pieces.append(piece)
                piece = char
            else:
                piece = candidate
        if piece:
            pieces.append(piece)
        return pieces

    def wrap_pdf_text(
        value: object,
        max_width: float,
        font_name: str,
        font_size: float,
        max_lines: int | None = None,
    ) -> list[str]:
        words = pdf_text(value).split()
        tokens = []
        for word in words:
            tokens.extend(split_long_word(word, max_width, font_name, font_size))

        lines = []
        current = ""
        for token in tokens:
            candidate = token if not current else f"{current} {token}"
            if text_width(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = token
        if current:
            lines.append(current)
        if not lines:
            lines = [pdf_text(None)]

        if max_lines and len(lines) > max_lines:
            visible = lines[:max_lines]
            last = visible[-1].rstrip()
            while last and text_width(f"{last}...", font_name, font_size) > max_width:
                last = last[:-1].rstrip()
            visible[-1] = f"{last}..." if last else "..."
            return visible
        return lines

    def draw_lines(
        lines: list[str],
        x: float,
        y: float,
        font_name: str,
        font_size: float,
        line_height: float,
        fill_color,
    ) -> float:
        pdf.setFillColor(fill_color)
        pdf.setFont(font_name, font_size)
        cursor_y = y
        for line_text in lines:
            pdf.drawString(x, cursor_y, line_text)
            cursor_y -= line_height
        return cursor_y

    def draw_right_fitted_text(
        text: object,
        right_x: float,
        y: float,
        max_width: float,
        font_name: str,
        font_size: int,
        fill_color,
        min_size: int = 8,
    ) -> None:
        value = pdf_text(text)
        size = font_size
        while size > min_size and text_width(value, font_name, size) > max_width:
            size -= 1
        pdf.setFillColor(fill_color)
        pdf.setFont(font_name, size)
        if text_width(value, font_name, size) <= max_width:
            pdf.drawRightString(right_x, y, value)
            return

        clipped = value
        while clipped and text_width(f"{clipped}...", font_name, size) > max_width:
            clipped = clipped[:-1]
        pdf.drawRightString(right_x, y, f"{clipped}..." if clipped else value[:10])

    def draw_fitted_text(
        text: object,
        x: float,
        y: float,
        max_width: float,
        font_name: str,
        font_size: int,
        fill_color,
        min_size: int = 10,
    ) -> None:
        value = pdf_text(text)
        size = font_size
        while size > min_size and text_width(value, font_name, size) > max_width:
            size -= 1
        pdf.setFillColor(fill_color)
        pdf.setFont(font_name, size)
        if text_width(value, font_name, size) <= max_width:
            pdf.drawString(x, y, value)
            return

        clipped = value
        while clipped and text_width(f"{clipped}...", font_name, size) > max_width:
            clipped = clipped[:-1]
        pdf.drawString(x, y, f"{clipped}..." if clipped else value[:10])

    def draw_panel(x: float, y: float, width: float, height: float, radius: float = 12, fill=panel, stroke_color=None) -> None:
        pdf.setFillColor(fill)
        pdf.setStrokeColor(stroke_color or line)
        pdf.setLineWidth(0.8)
        pdf.roundRect(x, y, width, height, radius, stroke=1, fill=1)

    def brand_initials() -> str:
        words = [word for word in pdf_text(pdf_brand, "HF").split() if word]
        initials = "".join(word[0] for word in words[:2]).upper()
        return initials[:2] or "HF"

    def image_reader_from_static(static_path: str):
        file_path = finders.find(static_path)
        if not file_path:
            return None
        try:
            return ImageReader(file_path)
        except Exception:
            return None

    official_logo = image_reader_from_static("service/img/pdf/pdf-logo-higiflow.png") or image_reader_from_static(
        "service/img/logo_oficial.png"
    )

    def draw_image_fit(image, x: float, y: float, width: float, height: float, preserve: bool = True) -> bool:
        if image is None:
            return False
        try:
            logo_w, logo_h = image.getSize()
            ratio = min(width / logo_w, height / logo_h) if preserve else max(width / logo_w, height / logo_h)
            draw_w = logo_w * ratio
            draw_h = logo_h * ratio
            pdf.drawImage(
                image,
                x + (width - draw_w) / 2,
                y + (height - draw_h) / 2,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            return True
        except Exception:
            return False

    # AJUSTA PROPRIEDADES DA LOGO
    def draw_header_logo(x: float, y: float, width: float, height: float) -> None:
        nonlocal uploaded_logo
        if uploaded_logo is not None:
            try:
                if draw_image_fit(uploaded_logo, x, y, width, height):
                    return
            except Exception:
                uploaded_logo = None

        if official_logo is not None and draw_image_fit(official_logo, x, y, width, height):
            return
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 19)
        pdf.drawString(x, y + 9, pdf_text(pdf_brand or brand_initials()))

    def draw_page_base() -> None:
        pdf.setFillColor(colors.white)
        pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        draw_panel(card_x, card_y, card_w, card_h, 14, colors.white)

    def draw_header(page_number: int, total_pages: int, first_page: bool) -> float:
        header_y = card_y + card_h - header_h
        pdf.setFillColor(accent)
        pdf.roundRect(card_x, header_y, card_w, header_h, 14, stroke=0, fill=1)
        pdf.rect(card_x, header_y, card_w, 18, stroke=0, fill=1)

        # CHAMA A FUNÇÃO DE AJUSTE DA LOGO E APLICA PARAMETROS
        draw_header_logo(card_x + 12, header_y + 22, 141, 18)

        pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.62))
        pdf.setFont("Helvetica-Bold", 7.8)
        pdf.drawRightString(card_x + card_w - 32, header_y + 47, "ORÇAMENTO")
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawRightString(card_x + card_w - 32, header_y + 22, doc_number)

        meta_y = header_y - meta_h
        pdf.setFillColor(surface)
        pdf.rect(card_x, meta_y, card_w, meta_h, stroke=0, fill=1)
        pdf.setStrokeColor(line)
        pdf.setLineWidth(0.8)
        pdf.line(card_x, meta_y, card_x + card_w, meta_y)
        pdf.line(card_x, meta_y + meta_h, card_x + card_w, meta_y + meta_h)

        def draw_meta_item(x: float, label: str, value: str) -> None:
            pdf.setFillColor(accent)
            pdf.circle(x, meta_y + 22, 2.2, stroke=0, fill=1)
            pdf.setFillColor(muted)
            pdf.setFont("Helvetica", 9)
            pdf.drawString(x + 9, meta_y + 18, label)
            pdf.setFillColor(ink)
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(x + 66, meta_y + 18, value)

        draw_meta_item(card_x + 32, "Emitido em", emission_date)
        draw_meta_item(card_x + 184, "Válido até", valid_until_date)
        if total_pages > 1:
            pdf.setFillColor(muted)
            pdf.setFont("Helvetica", 8)
            pdf.drawRightString(card_x + card_w - 32, meta_y + 18, f"Página {page_number} de {total_pages}")

        return meta_y - 28

    def address_text() -> str:
        structured = _endereco_para_mapa(orcamento)
        return structured or orcamento.endereco or "Endereço não informado"

    def company_address_text() -> str:
        parts = [company_config.get("endereco"), company_config.get("bairro"), company_config.get("cidade")]
        return " - ".join(str(part).strip() for part in parts if part)

    def draw_contact_line(label: str, value: object, x: float, y: float, width: float) -> None:
        pdf.setFillColor(soft_text)
        pdf.setFont("Helvetica-Bold", 7)
        pdf.drawString(x, y, label)
        draw_fitted_text(value, x + 40, y, width - 40, "Helvetica", 8.6, muted, 7)

    def draw_client_summary(top_y: float) -> float:
        section_h = 104
        y = top_y - section_h
        col_gap = 28
        col_w = (body_w - col_gap) / 2
        client_x = body_x
        company_x = body_x + col_w + col_gap

        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Bold", 7.8)
        pdf.drawString(client_x, y + section_h - 8, "CLIENTE")
        draw_lines(
            wrap_pdf_text(orcamento.name, col_w, "Helvetica-Bold", 10.8, 1),
            client_x,
            y + section_h - 28,
            "Helvetica-Bold",
            10.8,
            13,
            ink,
        )

        draw_contact_line("TEL.", orcamento.telefone, client_x, y + section_h - 50, col_w)
        draw_contact_line("E-MAIL", orcamento.email, client_x, y + section_h - 68, col_w)
        draw_contact_line("END.", address_text(), client_x, y + section_h - 86, col_w)

        divider_x = body_x + col_w + (col_gap / 2)
        pdf.setStrokeColor(line)
        pdf.line(divider_x, y + 12, divider_x, y + section_h - 8)

        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Bold", 7.8)
        pdf.drawString(company_x, y + section_h - 8, "EMPRESA")
        draw_lines(
            wrap_pdf_text(company_config.get("razao_social"), col_w, "Helvetica-Bold", 10.8, 1),
            company_x,
            y + section_h - 28,
            "Helvetica-Bold",
            10.8,
            13,
            ink,
        )
        draw_contact_line("TEL.", company_config.get("telefone"), company_x, y + section_h - 50, col_w)
        draw_contact_line("E-MAIL", company_config.get("email"), company_x, y + section_h - 68, col_w)
        draw_contact_line("END.", company_address_text(), company_x, y + section_h - 86, col_w)

        return y - 28

    def item_detail(item) -> str:
        pieces = []
        category = getattr(item, "categoria_nome", None) or item.tipo
        if category:
            pieces.append(f"Categoria: {category}")
        if item.tecido:
            pieces.append(f"Tecido: {item.tecido}")
        if item.tamanho:
            pieces.append(f"Tamanho: {item.tamanho}")
        if item.formato:
            pieces.append(f"Formato: {item.formato}")
        if item.descricao:
            pieces.append(item.descricao)
        return " | ".join(pieces) or "Higienização profissional com acabamento técnico."

    def format_factor(value: float) -> str:
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def adicional_value(adicional: AdicionalOrcamento) -> str:
        value = float(adicional.valor or 0)
        if adicional.tipo_valor == AdicionalOrcamento.TipoValor.PERCENTUAL:
            return f"+ {format_factor(value)}%"
        return f"+ {money(value)}"

    def build_blocks() -> list[dict]:
        service_w = body_w - 136
        blocks = []
        for item in itens:
            name_lines = wrap_pdf_text(item.name or "-", service_w, "Helvetica-Bold", 10.5, 2)
            detail_lines = wrap_pdf_text(item_detail(item), service_w, "Helvetica", 8.2, 2)
            row_h = max(56, 20 + len(name_lines) * 12 + len(detail_lines) * 10)
            blocks.append(
                {
                    "kind": "service",
                    "name_lines": name_lines,
                    "detail_lines": detail_lines,
                    "total_value": money(float(item.valor or 0) * orcamento.quantidade),
                    "height": min(row_h, 82),
                }
            )
        if not blocks:
            blocks.append(
                {
                    "kind": "empty",
                    "height": 52,
                    "text": "Nenhum serviço vinculado a este orçamento.",
                }
            )
        if adicionais:
            blocks.append(
                {
                    "kind": "rules",
                    "title": "ADICIONAIS",
                    "rows": [(adicional.name, adicional_value(adicional)) for adicional in adicionais],
                    "height": 28 + (len(adicionais) * 20),
                }
            )
        if multiplicadores:
            blocks.append(
                {
                    "kind": "rules",
                    "title": "MULTIPLICADORES",
                    "rows": [
                        (multiplicador.name, f"x {format_factor(float(multiplicador.fator or 1))}")
                        for multiplicador in multiplicadores
                    ],
                    "height": 28 + (len(multiplicadores) * 20),
                }
            )
        return blocks

    def block_total_height(blocks: list[dict]) -> float:
        return sum(block["height"] for block in blocks)

    summary_block_h = 108
    summary_conditions_gap = 14
    conditions_footer_gap = 12
    services_final_gap = 10

    def final_condition_lines() -> list[str]:
        lines = [
            "Orçamento válido por 15 dias a partir da data de emissão",
            "Pagamento: à vista com 5% de desconto ou parcelado em até 3x",
            "Garantia de 30 dias para os serviços realizados",
            "Agendamento sujeito à disponibilidade da equipe técnica",
        ]
        if note_text:
            lines.append(f"Observação: {note_text}")
        return lines

    def final_condition_items() -> list[list[str]]:
        return [wrap_pdf_text(line_text, body_w - 46, "Helvetica", 8.5, 2) for line_text in final_condition_lines()]

    def final_conditions_height() -> float:
        return 38 + sum(max(14, len(lines) * 10 + 4) for lines in final_condition_items())

    def final_reserved_height() -> float:
        return summary_block_h + summary_conditions_gap + final_conditions_height()

    def page_capacity(first_page: bool, last_page: bool) -> float:
        top = card_y + card_h - header_h - meta_h - 28
        if first_page:
            top -= 132
        if last_page:
            bottom = card_y + footer_h + conditions_footer_gap + final_reserved_height() + services_final_gap
            return max(80, top - 22 - bottom)
        bottom = card_y + footer_h + 28
        return max(80, top - bottom - 30)

    def paginate_blocks(blocks: list[dict]) -> list[dict]:
        if not blocks:
            return [{"blocks": [], "first": True, "last": True}]

        pages = []
        remaining = blocks[:]
        first_page = True
        while remaining:
            if block_total_height(remaining) <= page_capacity(first_page, True):
                page_blocks = remaining
                remaining = []
                pages.append({"blocks": page_blocks, "first": first_page, "last": True})
                break

            capacity = page_capacity(first_page, False)
            taken = []
            used = 0
            for block in remaining:
                if taken and used + block["height"] > capacity:
                    break
                taken.append(block)
                used += block["height"]

            if not taken:
                taken = [remaining[0]]
            next_remaining = remaining[len(taken) :]
            if not next_remaining:
                if len(taken) > 1 and block_total_height([taken[-1]]) <= page_capacity(False, True):
                    final_page_blocks = [taken.pop()]
                    pages.append({"blocks": taken, "first": first_page, "last": False})
                    pages.append({"blocks": final_page_blocks, "first": False, "last": True})
                else:
                    pages.append({"blocks": taken, "first": first_page, "last": False})
                    pages.append({"blocks": [], "first": False, "last": True})
                break
            pages.append({"blocks": taken, "first": first_page, "last": False})
            remaining = next_remaining
            first_page = False
        return pages

    def draw_section_label(text: str, x: float, y: float) -> None:
        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Bold", 7.8)
        pdf.drawString(x, y, text)

    def draw_services_table(page_blocks: list[dict], top_y: float, page_number: int, total_pages: int) -> float:
        x = body_x
        width = body_w
        body_h = max(52, block_total_height(page_blocks))
        y = top_y - 22 - body_h

        draw_section_label("SERVIÇOS", x, top_y)
        draw_panel(x, y, width, body_h, 14)

        cursor_y = y + body_h
        for index, block in enumerate(page_blocks):
            row_top = cursor_y
            row_bottom = cursor_y - block["height"]
            if index > 0:
                pdf.setStrokeColor(line)
                pdf.setLineWidth(0.7)
                pdf.line(x, row_top, x + width, row_top)

            if block["kind"] == "service":
                if index == 0:
                    pdf.setFillColor(surface)
                    pdf.rect(x + 1, row_bottom, width - 2, block["height"] - 1, stroke=0, fill=1)
                draw_lines(block["name_lines"], x + 18, row_top - 20, "Helvetica-Bold", 10.4, 12, ink)
                detail_y = row_top - 20 - (len(block["name_lines"]) * 12) - 4
                draw_lines(block["detail_lines"], x + 18, detail_y, "Helvetica", 8.2, 10, muted)
                draw_right_fitted_text(block["total_value"], x + width - 18, row_top - 23, 98, "Helvetica-Bold", 10.5, accent)
            elif block["kind"] == "rules":
                pdf.setFillColor(muted)
                pdf.setFont("Helvetica-Bold", 7.4)
                pdf.drawString(x + 18, row_top - 18, block["title"])
                rule_y = row_top - 36
                for label, value in block["rows"]:
                    pdf.setFillColor(accent)
                    pdf.circle(x + 22, rule_y + 3, 1.6, stroke=0, fill=1)
                    draw_fitted_text(label, x + 32, rule_y, width - 142, "Helvetica", 8.5, muted, 7)
                    draw_right_fitted_text(value, x + width - 18, rule_y, 96, "Helvetica", 8.5, accent)
                    rule_y -= 20
            else:
                pdf.setFillColor(muted)
                pdf.setFont("Helvetica", 9.2)
                pdf.drawString(x + 18, row_top - 30, block["text"])

            cursor_y = row_bottom

        return y - 26

    def draw_final_block(top_y: float | None = None) -> None:
        def draw_summary_block(top_y: float) -> float:
            h = summary_block_h
            x = body_x
            y = top_y - h
            width = body_w
            draw_panel(x, y, width, h, 14)

            total_h = 44
            row_font_size = 9
            subtotal_y = y + h - 25
            divider_y = y + h - 43
            multiplier_row_bottom = y + total_h
            multiplier_row_h = divider_y - multiplier_row_bottom
            multiplier_y = multiplier_row_bottom + ((multiplier_row_h - row_font_size) / 2) + 2

            pdf.setFillColor(muted)
            pdf.setFont("Helvetica", row_font_size)
            pdf.drawString(x + 20, subtotal_y, "Subtotal dos serviços")
            draw_right_fitted_text(money(subtotal_orcamento), x + width - 20, subtotal_y, 150, "Helvetica-Bold", row_font_size, ink)

            pdf.setStrokeColor(line)
            pdf.line(x, divider_y, x + width, divider_y)
            pdf.setFillColor(muted)
            pdf.setFont("Helvetica", row_font_size)
            pdf.drawString(x + 20, multiplier_y, "Multiplicador aplicado")
            draw_right_fitted_text(f"x {format_factor(fator_multiplicadores)}", x + width - 20, multiplier_y, 140, "Helvetica-Bold", row_font_size, ink)

            pdf.setFillColor(accent)
            pdf.roundRect(x, y, width, total_h, 14, stroke=0, fill=1)
            pdf.rect(x, y + total_h - 14, width, 14, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(x + 20, y + 17, "Valor Total")
            draw_right_fitted_text(money(orcamento.valor), x + width - 20, y + 13, 190, "Helvetica-Bold", 17, colors.white, 11)

            return y - summary_conditions_gap

        def draw_conditions(top_y: float) -> float:
            wrapped_items = final_condition_items()
            h = final_conditions_height()
            x = body_x
            y = top_y - h
            draw_panel(x, y, body_w, h, 14, surface, accent_soft)

            draw_section_label("CONDIÇÕES", x + 18, y + h - 24)
            cursor_y = y + h - 38
            for lines in wrapped_items:
                pdf.setFillColor(accent)
                pdf.circle(x + 20, cursor_y + 3, 1.7, stroke=0, fill=1)
                draw_lines(lines, x + 32, cursor_y, "Helvetica", 8.2, 10, muted)
                cursor_y -= max(14, len(lines) * 10 + 4)

            return y - 20

        minimum_top = card_y + footer_h + conditions_footer_gap + final_reserved_height()
        summary_top = max(top_y or minimum_top, minimum_top)
        next_y = draw_summary_block(summary_top)
        draw_conditions(next_y)

    def draw_continuation_note() -> None:
        y = card_y + footer_h + 18
        pdf.setFillColor(surface)
        pdf.roundRect(body_x, y, body_w, 28, 10, stroke=0, fill=1)
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(body_x + 14, y + 10, "Continua na próxima página com mais serviços e o resumo final.")

    def draw_footer(page_number: int, total_pages: int) -> None:
        pdf.setFillColor(surface)
        pdf.rect(card_x, card_y, card_w, footer_h, stroke=0, fill=1)
        pdf.setStrokeColor(line)
        pdf.line(card_x, card_y + footer_h, card_x + card_w, card_y + footer_h)
        pdf.setFillColor(colors.HexColor("#EAF1FF"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(card_x + 32, card_y + 21, "HigiFlow")
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 7.5)
        footer_text = "© 2024 HigiFlow. Todos os direitos reservados."
        if total_pages > 1:
            footer_text = f"{footer_text} Página {page_number} de {total_pages}."
        pdf.drawRightString(card_x + card_w - 32, card_y + 22, pdf_text(footer_text))

    blocks = build_blocks()
    pages = paginate_blocks(blocks)
    total_pages = len(pages)

    for index, page in enumerate(pages, start=1):
        if index > 1:
            pdf.showPage()
        draw_page_base()
        header_bottom = draw_header(index, total_pages, page["first"])
        table_top = draw_client_summary(header_bottom) if page["first"] else header_bottom
        final_top = table_top
        if page["blocks"] or not page["last"]:
            final_top = draw_services_table(page["blocks"], table_top, index, total_pages) - services_final_gap
        if page["last"]:
            draw_final_block(final_top)
        else:
            draw_continuation_note()
        draw_footer(index, total_pages)

    pdf.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="orcamento-{orcamento.pk}.pdf"'
    return response
