import textwrap
from datetime import timedelta
from io import BytesIO
from urllib.parse import quote_plus

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from service.forms import ClienteVinculoOrcamentoForm, OrcamentoForm
from service.models import Cliente, Lead, Orcamento
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
    cliente = Cliente.objects.filter(email=orcamento.email).first()
    if cliente is None:
        return Cliente.objects.create(
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
    todos_orcamentos = Orcamento.objects.prefetch_related("itens", "cliente").order_by("-created_at", "-id")
    orcamentos = todos_orcamentos

    if busca:
        orcamentos = orcamentos.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(telefone__icontains=busca)
            | Q(descricao__icontains=busca)
        )

    total_orcamentos = todos_orcamentos.count()
    total_pendentes = todos_orcamentos.filter(aprovado=False).count()
    total_aprovados = todos_orcamentos.filter(aprovado=True).count()

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
            status_label = "Pendente"
            status_class = "status-yellow"

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
        "total_pendentes": total_pendentes,
        "total_aprovados": total_aprovados,
        "total_recusados": 0,
    }
    return render(request, "service/orcamentos.html", context)


def _nome_servico_ordem(orcamento: Orcamento) -> str:
    itens = list(orcamento.itens.all())
    if itens:
        return " + ".join(item.name for item in itens[:2])
    return orcamento.descricao or "Servico cadastrado"


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
    orcamentos = list(Orcamento.objects.prefetch_related("itens", "cliente").order_by("-updated_at", "-id")[:12])

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


def novo_orcamento(request: HttpRequest) -> HttpResponse:
    lead_id = request.GET.get("lead")
    lead = Lead.objects.filter(pk=lead_id).first() if lead_id else None

    if request.method == "POST":
        form = OrcamentoForm(request.POST)
        if form.is_valid():
            orcamento = Orcamento.objects.create(
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

            messages.success(request, "Orcamento criado com sucesso.")
            return redirect("orcamento_detalhe", pk=orcamento.pk)
    else:
        item_inicial = request.GET.get("item")
        initial = _orcamento_initial_lead(lead, item_inicial) if lead else {"itens": [item_inicial]} if item_inicial else None
        form = OrcamentoForm(initial=initial)

    context = {
        "form": form,
        "orcamentos_recentes": Orcamento.objects.prefetch_related("itens").order_by("-id")[:5],
    }
    return render(request, "service/orcamento_form.html", context)


def buscar_cliente_dados(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    cliente = get_object_or_404(Cliente, pk=pk)
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
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    lead = get_object_or_404(Lead, pk=pk)
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
        "criar_cliente_automatico": False,
    }


def _salvar_dados_orcamento(orcamento: Orcamento, form: OrcamentoForm) -> Orcamento:
    itens = list(form.cleaned_data["itens"])
    quantidade = form.cleaned_data["quantidade"]

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
    orcamento.valor = sum(item.valor for item in itens) * quantidade
    orcamento.cliente = form.cleaned_data.get("cliente") or orcamento.cliente
    orcamento.lead = form.cleaned_data.get("lead") or orcamento.lead
    orcamento.save()
    orcamento.itens.set(itens)
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
    orcamento = get_object_or_404(Orcamento.objects.prefetch_related("itens"), pk=pk)

    if request.method == "POST":
        form = OrcamentoForm(request.POST)
        if form.is_valid():
            _salvar_dados_orcamento(orcamento, form)
            _aplicar_fluxo_cliente(orcamento, form)
            messages.success(request, "Orcamento atualizado com sucesso.")
            return redirect("orcamento_detalhe", pk=orcamento.pk)
    else:
        form = OrcamentoForm(initial=_orcamento_initial(orcamento))

    context = {
        "form": form,
        "orcamento": orcamento,
        "orcamentos_recentes": Orcamento.objects.prefetch_related("itens").exclude(pk=orcamento.pk).order_by("-id")[:5],
        "form_title": "Editar orcamento",
        "form_intro": "Atualize os dados do cliente, endereco, itens e quantidade deste orcamento.",
        "form_submit_label": "Salvar alteracoes",
    }
    return render(request, "service/orcamento_form.html", context)


def buscar_endereco_cep(request: HttpRequest, cep: str) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    try:
        endereco = ViaCepService().buscar_por_cep(cep)
    except ViaCepTemporaryUnavailableError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    except ViaCepLookupError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "endereco": endereco.as_dict()})


def buscar_mapa_orcamento(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    orcamento = get_object_or_404(Orcamento, pk=pk)
    endereco = _endereco_para_mapa(orcamento)
    if not endereco:
        return JsonResponse(
            {"ok": False, "error": "Cadastre o endereco do servico para visualizar o mapa."},
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
        Orcamento.objects.prefetch_related("itens", "cliente"),
        pk=pk,
    )
    context = {
        "orcamento": orcamento,
        "itens": orcamento.itens.all(),
        "mapa": _links_mapa_orcamento(orcamento),
        "ordem_servico": getattr(orcamento, "ordem_servico", None),
        "vinculo_form": ClienteVinculoOrcamentoForm(
            initial={"cliente": orcamento.cliente_id} if orcamento.cliente_id else None
        ),
        "total_clientes": Cliente.objects.count(),
    }
    return render(request, "service/orcamento_detalhe.html", context)


def vincular_cliente_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(Orcamento, pk=pk)
    form = ClienteVinculoOrcamentoForm(request.POST)
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
            messages.success(request, f"Orcamento aprovado e vinculado ao cliente '{cliente.name}'.")
        else:
            messages.success(request, f"Cliente '{cliente.name}' vinculado ao orcamento.")
            if request.POST.get("voltar_para_aprovacao") == "1":
                return redirect(f"{reverse('orcamento_detalhe', args=[pk])}?aprovar=1")
    else:
        messages.error(request, "Selecione um cliente valido para vincular ao orcamento.")

    return redirect("orcamento_detalhe", pk=pk)


def deletar_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(Orcamento, pk=pk)
    nome = orcamento.name
    orcamento.delete()

    messages.success(request, f"Orcamento de '{nome}' excluido com sucesso.")
    return redirect("orcamentos")


def concluir_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(Orcamento, pk=pk)
    if not orcamento.aprovado:
        if not orcamento.cliente_id:
            messages.error(
                request,
                "Vincule ou crie um cliente antes de aprovar o orcamento.",
            )
            return redirect(f"{reverse('orcamento_detalhe', args=[pk])}?aprovar=1")
        orcamento.aprovado = True
        orcamento.save(update_fields=["aprovado", "updated_at"])
        _marcar_lead_convertido(orcamento, orcamento.cliente)
        messages.success(request, "Orcamento aprovado com sucesso.")
    else:
        messages.info(request, "Este orcamento ja esta aprovado.")

    return redirect("orcamento_detalhe", pk=pk)


def cadastrar_cliente_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(Orcamento, pk=pk)

    if not orcamento.email:
        messages.error(
            request,
            "Este orcamento precisa de um email para criar o cadastro do cliente.",
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
        messages.success(request, "Orcamento aprovado e cliente vinculado com sucesso.")
    else:
        messages.success(
            request,
            "Cliente cadastrado e vinculado ao orcamento com sucesso.",
        )
        if request.POST.get("voltar_para_aprovacao") == "1":
            return redirect(f"{reverse('orcamento_detalhe', args=[pk])}?aprovar=1")
    return redirect("orcamento_detalhe", pk=pk)


def aprovar_orcamento(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("orcamento_detalhe", pk=pk)

    orcamento = get_object_or_404(Orcamento, pk=pk)

    if not orcamento.email:
        messages.error(
            request,
            "Este orcamento precisa de um email para criar o cadastro do cliente.",
        )
        return redirect("orcamento_detalhe", pk=pk)

    cliente = _criar_ou_atualizar_cliente_do_orcamento(orcamento)
    orcamento.cliente = cliente
    orcamento.aprovado = True
    orcamento.save(update_fields=["cliente", "aprovado", "updated_at"])
    _marcar_lead_convertido(orcamento, cliente)

    messages.success(
        request,
        "Orcamento aprovado e cliente vinculado com sucesso.",
    )
    return redirect("orcamento_detalhe", pk=pk)


def gerar_orcamento_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    orcamento = get_object_or_404(
        Orcamento.objects.prefetch_related("itens", "cliente"),
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
        return "#2577B5"

    def load_logo():
        uploaded_logo = request.FILES.get("pdf_logo")
        if not uploaded_logo:
            return None

        allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
        if uploaded_logo.content_type not in allowed_types:
            return None

        logo_bytes = uploaded_logo.read(3 * 1024 * 1024 + 1)
        if len(logo_bytes) > 3 * 1024 * 1024:
            return None

        try:
            return ImageReader(BytesIO(logo_bytes))
        except Exception:
            return None

    pdf_brand = clean_text(request.POST.get("pdf_brand", ""), 42) or "ERP Higienizacao"
    pdf_phrase = clean_text(request.POST.get("pdf_phrase", ""), 180)
    accent_color = clean_color(request.POST.get("pdf_accent_color", ""))
    uploaded_logo = load_logo()

    page_width, page_height = A4
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Proposta comercial {orcamento.pk}")

    navy = colors.HexColor("#111827")
    ink = colors.HexColor("#172033")
    muted = colors.HexColor("#667085")
    soft_text = colors.HexColor("#8A95A6")
    line = colors.HexColor("#E4E7EC")
    panel = colors.white
    surface = colors.HexColor("#F8FAFC")
    accent = colors.HexColor(accent_color)
    accent_soft = colors.HexColor("#EEF6FF")

    margin = 40
    content_w = page_width - (margin * 2)
    emission_date = timezone.localdate().strftime("%d/%m/%Y")
    doc_number = f"PF-{timezone.localdate().year}-{orcamento.pk:04d}"
    note_text = (
        pdf_phrase
        or orcamento.descricao
        or "Valido mediante confirmacao da agenda, avaliacao tecnica e disponibilidade da equipe."
    )

    table_title_h = 42
    table_head_h = 30
    table_bottom_pad = 12
    first_table_top = 514
    next_table_top = 718
    last_table_bottom = 224
    continue_table_bottom = 112

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

    def draw_panel(x: float, y: float, width: float, height: float, radius: float = 12, fill=panel) -> None:
        pdf.setFillColor(fill)
        pdf.setStrokeColor(line)
        pdf.setLineWidth(0.8)
        pdf.roundRect(x, y, width, height, radius, stroke=1, fill=1)

    def brand_initials() -> str:
        words = [word for word in pdf_text(pdf_brand, "HF").split() if word]
        initials = "".join(word[0] for word in words[:2]).upper()
        return initials[:2] or "HF"

    def draw_logo_box(x: float, y: float, size: float) -> None:
        nonlocal uploaded_logo
        if uploaded_logo is not None:
            try:
                logo_w, logo_h = uploaded_logo.getSize()
                ratio = min((size - 12) / logo_w, (size - 12) / logo_h)
                draw_w = logo_w * ratio
                draw_h = logo_h * ratio
                pdf.setFillColor(colors.white)
                pdf.roundRect(x, y, size, size, 12, stroke=0, fill=1)
                pdf.drawImage(
                    uploaded_logo,
                    x + (size - draw_w) / 2,
                    y + (size - draw_h) / 2,
                    width=draw_w,
                    height=draw_h,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                return
            except Exception:
                uploaded_logo = None

        pdf.setFillColor(accent)
        pdf.roundRect(x, y, size, size, 12, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawCentredString(x + size / 2, y + size / 2 - 5, brand_initials())

    def draw_page_base() -> None:
        pdf.setFillColor(colors.white)
        pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
        pdf.setFillColor(surface)
        pdf.rect(0, 0, page_width, 92, stroke=0, fill=1)
        pdf.setFillColor(accent)
        pdf.rect(0, 0, 5, page_height, stroke=0, fill=1)

    def draw_header(page_number: int, total_pages: int, first_page: bool) -> float:
        header_h = 106 if first_page else 68
        header_y = page_height - margin - header_h
        header_radius = 18 if first_page else 14
        pdf.setFillColor(navy)
        pdf.roundRect(margin, header_y, content_w, header_h, header_radius, stroke=0, fill=1)
        pdf.setFillColor(accent)
        pdf.roundRect(margin, header_y + header_h - 8, content_w, 8, header_radius, stroke=0, fill=1)

        logo_size = 54 if first_page else 40
        logo_x = margin + 20
        logo_y = header_y + (header_h - logo_size) / 2
        draw_logo_box(logo_x, logo_y, logo_size)

        brand_x = logo_x + logo_size + 18
        meta_w = 154 if first_page else 142
        meta_h = 64 if first_page else 46
        meta_x = margin + content_w - meta_w - 18
        meta_y = header_y + (header_h - meta_h) / 2
        brand_max_w = meta_x - brand_x - 20

        title_y = header_y + (68 if first_page else 38)
        draw_fitted_text(pdf_brand, brand_x, title_y, brand_max_w, "Helvetica-Bold", 22 if first_page else 15, colors.white)
        pdf.setFillColor(colors.HexColor("#D5E0EA"))
        pdf.setFont("Helvetica", 10 if first_page else 8.5)
        pdf.drawString(brand_x, title_y - (20 if first_page else 15), "Proposta comercial de servicos")
        if first_page:
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(brand_x, header_y + 22, "Higienizacao profissional | atendimento tecnico | proposta personalizada")

        pdf.setFillColor(colors.white)
        pdf.roundRect(meta_x, meta_y, meta_w, meta_h, 12, stroke=0, fill=1)
        pdf.setFillColor(soft_text)
        pdf.setFont("Helvetica-Bold", 7.5)
        pdf.drawString(meta_x + 14, meta_y + meta_h - 18, "DOCUMENTO")
        pdf.drawString(meta_x + 14, meta_y + (22 if first_page else 8), "EMISSAO")
        pdf.setFillColor(ink)
        pdf.setFont("Helvetica-Bold", 11 if first_page else 9)
        pdf.drawString(meta_x + 14, meta_y + meta_h - 31, doc_number)
        pdf.drawString(meta_x + 78, meta_y + (22 if first_page else 8), emission_date)
        if not first_page:
            pdf.setFillColor(soft_text)
            pdf.setFont("Helvetica", 7.5)
            pdf.drawRightString(meta_x + meta_w - 14, meta_y + 8, f"Pag. {page_number}/{total_pages}")

        return header_y - (22 if first_page else 20)

    def address_text() -> str:
        structured = _endereco_para_mapa(orcamento)
        return structured or orcamento.endereco or "Endereco nao informado"

    def draw_metric(label: str, value: str, x: float, y: float, width: float) -> None:
        pdf.setFillColor(soft_text)
        pdf.setFont("Helvetica-Bold", 7.8)
        pdf.drawString(x, y, label.upper())
        draw_fitted_text(value, x, y - 17, width, "Helvetica-Bold", 13, ink, 9)

    def draw_client_summary(top_y: float) -> float:
        card_h = 126
        gap = 16
        client_w = 322
        summary_w = content_w - client_w - gap
        y = top_y - card_h
        client_x = margin
        summary_x = client_x + client_w + gap

        draw_panel(client_x, y, client_w, card_h)
        draw_panel(summary_x, y, summary_w, card_h)

        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(client_x + 18, y + card_h - 24, "CLIENTE")
        draw_lines(
            wrap_pdf_text(orcamento.name, client_w - 36, "Helvetica-Bold", 16, 1),
            client_x + 18,
            y + card_h - 48,
            "Helvetica-Bold",
            16,
            18,
            ink,
        )

        contact_y = y + card_h - 72
        contact_lines = [
            f"Email: {pdf_text(orcamento.email)}",
            f"Telefone: {pdf_text(orcamento.telefone)}",
        ]
        for contact in contact_lines:
            draw_lines(
                wrap_pdf_text(contact, client_w - 36, "Helvetica", 9.5, 1),
                client_x + 18,
                contact_y,
                "Helvetica",
                9.5,
                12,
                muted,
            )
            contact_y -= 15

        draw_lines(
            wrap_pdf_text(address_text(), client_w - 36, "Helvetica", 9.3, 2),
            client_x + 18,
            y + 24,
            "Helvetica",
            9.3,
            11,
            muted,
        )

        pdf.setFillColor(accent_soft)
        pdf.roundRect(summary_x + 14, y + card_h - 49, summary_w - 28, 35, 10, stroke=0, fill=1)
        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(summary_x + 26, y + card_h - 28, "TOTAL")
        draw_fitted_text(money(orcamento.valor), summary_x + 26, y + card_h - 45, summary_w - 52, "Helvetica-Bold", 17, accent, 10)

        metric_y = y + 50
        draw_metric("Quantidade", str(orcamento.quantidade), summary_x + 18, metric_y, 62)
        draw_metric("Itens", str(len(itens)), summary_x + 92, metric_y, 48)
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(summary_x + 18, y + 22, f"Status: {'Concluido' if orcamento.aprovado else 'Pendente'}")

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
        return " | ".join(pieces) or "Higienizacao profissional com acabamento tecnico."

    def build_rows() -> list[dict]:
        service_w = content_w - 210
        rows = []
        for item in itens:
            name_lines = wrap_pdf_text(item.name or "-", service_w, "Helvetica-Bold", 10.5, 2)
            detail_lines = wrap_pdf_text(item_detail(item), service_w, "Helvetica", 8.5, 2)
            row_h = max(58, 21 + len(name_lines) * 12 + len(detail_lines) * 10)
            rows.append(
                {
                    "name_lines": name_lines,
                    "detail_lines": detail_lines,
                    "quantity": str(orcamento.quantidade),
                    "unit_value": money(item.valor),
                    "total_value": money(item.valor * orcamento.quantidade),
                    "height": min(row_h, 82),
                }
            )
        return rows

    def row_total_height(rows: list[dict]) -> float:
        return sum(row["height"] for row in rows)

    def page_capacity(first_page: bool, last_page: bool) -> float:
        table_top = first_table_top if first_page else next_table_top
        table_bottom = last_table_bottom if last_page else continue_table_bottom
        return table_top - table_bottom - table_title_h - table_head_h - table_bottom_pad

    def paginate_rows(rows: list[dict]) -> list[dict]:
        if not rows:
            return [{"rows": [], "first": True, "last": True}]

        pages = []
        remaining = rows[:]
        first_page = True
        while remaining:
            if row_total_height(remaining) <= page_capacity(first_page, True):
                page_rows = remaining
                remaining = []
                pages.append({"rows": page_rows, "first": first_page, "last": True})
                break

            capacity = page_capacity(first_page, False)
            taken = []
            used = 0
            for row in remaining:
                if taken and used + row["height"] > capacity:
                    break
                taken.append(row)
                used += row["height"]

            if not taken:
                taken = [remaining[0]]
            pages.append({"rows": taken, "first": first_page, "last": False})
            remaining = remaining[len(taken) :]
            first_page = False
        return pages

    def draw_table_header(x: float, y: float, width: float) -> None:
        pdf.setFillColor(surface)
        pdf.roundRect(x + 14, y - table_head_h + 2, width - 28, table_head_h - 2, 8, stroke=0, fill=1)
        pdf.setFillColor(soft_text)
        pdf.setFont("Helvetica-Bold", 7.8)
        pdf.drawString(x + 24, y - 18, "SERVICO")
        pdf.drawCentredString(x + width - 188, y - 18, "QTD")
        pdf.drawRightString(x + width - 92, y - 18, "UNITARIO")
        pdf.drawRightString(x + width - 24, y - 18, "TOTAL")

    def draw_services_table(page_rows: list[dict], top_y: float, page_number: int, total_pages: int) -> float:
        x = margin
        width = content_w
        body_h = row_total_height(page_rows) if page_rows else 56
        table_h = table_title_h + table_head_h + body_h + table_bottom_pad
        y = top_y - table_h
        draw_panel(x, y, width, table_h, 14)

        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(x + 18, top_y - 24, "SERVICOS SOLICITADOS")
        pdf.setFillColor(soft_text)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawRightString(x + width - 18, top_y - 24, f"Pagina {page_number} de {total_pages}")
        draw_table_header(x, top_y - table_title_h, width)

        cursor_y = top_y - table_title_h - table_head_h
        if not page_rows:
            pdf.setFillColor(muted)
            pdf.setFont("Helvetica", 10)
            pdf.drawString(x + 24, cursor_y - 34, "Nenhum servico vinculado a este orcamento.")
            return y

        for row in page_rows:
            row_top = cursor_y
            row_bottom = cursor_y - row["height"]
            pdf.setStrokeColor(line)
            pdf.setLineWidth(0.7)
            pdf.line(x + 14, row_bottom, x + width - 14, row_bottom)

            text_y = row_top - 18
            draw_lines(row["name_lines"], x + 24, text_y, "Helvetica-Bold", 10.5, 12, ink)
            detail_y = text_y - (len(row["name_lines"]) * 12) - 4
            draw_lines(row["detail_lines"], x + 24, detail_y, "Helvetica", 8.5, 10, muted)

            value_y = row_top - 32
            pdf.setFillColor(ink)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawCentredString(x + width - 188, value_y, row["quantity"])
            pdf.setFont("Helvetica", 9.5)
            pdf.drawRightString(x + width - 92, value_y, row["unit_value"])
            pdf.setFillColor(accent)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawRightString(x + width - 24, value_y, row["total_value"])
            cursor_y = row_bottom

        return y

    def draw_final_block() -> None:
        y = 92
        h = 104
        note_w = 318
        total_w = content_w - note_w - 16
        total_x = margin + note_w + 16

        draw_panel(margin, y, note_w, h, 14)
        pdf.setFillColor(accent)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(margin + 18, y + h - 24, "MENSAGEM PARA O CLIENTE")
        draw_lines(
            wrap_pdf_text(note_text, note_w - 36, "Helvetica", 9.2, 4),
            margin + 18,
            y + h - 45,
            "Helvetica",
            9.2,
            11,
            muted,
        )
        pdf.setStrokeColor(line)
        pdf.line(margin + 18, y + 20, margin + note_w - 18, y + 20)
        pdf.setFillColor(soft_text)
        pdf.setFont("Helvetica", 7.8)
        pdf.drawString(margin + 18, y + 8, "Valores sujeitos a confirmacao de agenda e avaliacao tecnica.")

        pdf.setFillColor(accent)
        pdf.roundRect(total_x, y, total_w, h, 14, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(total_x + 18, y + h - 25, "VALOR TOTAL")
        draw_fitted_text(money(orcamento.valor), total_x + 18, y + h - 58, total_w - 36, "Helvetica-Bold", 24, colors.white, 12)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(total_x + 18, y + 20, f"{len(itens)} item(ns) x {orcamento.quantidade}")

    def draw_continuation_note() -> None:
        pdf.setFillColor(surface)
        pdf.roundRect(margin, 72, content_w, 28, 10, stroke=0, fill=1)
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 8.5)
        pdf.drawString(margin + 14, 82, "Continua na proxima pagina com mais servicos e o resumo final.")

    def draw_footer(page_number: int, total_pages: int) -> None:
        pdf.setStrokeColor(line)
        pdf.setLineWidth(0.8)
        pdf.line(margin, 60, margin + content_w, 60)
        pdf.setFillColor(soft_text)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(margin, 40, f"{pdf_text(pdf_brand)} | Documento gerado em {emission_date}")
        pdf.drawRightString(margin + content_w, 40, f"Pagina {page_number} de {total_pages}")

    rows = build_rows()
    pages = paginate_rows(rows)
    total_pages = len(pages)

    for index, page in enumerate(pages, start=1):
        if index > 1:
            pdf.showPage()
        draw_page_base()
        header_bottom = draw_header(index, total_pages, page["first"])
        table_top = first_table_top if page["first"] else next_table_top
        if page["first"]:
            table_top = draw_client_summary(header_bottom)
        draw_services_table(page["rows"], table_top, index, total_pages)
        if page["last"]:
            draw_final_block()
        else:
            draw_continuation_note()
        draw_footer(index, total_pages)

    pdf.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="orcamento-{orcamento.pk}.pdf"'
    return response
