from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from service.forms import CategoriaCatalogoForm, ClienteForm, LeadForm
from service.models import CategoriaCatalogo, Cliente, Lead, Orcamento, Service_catalog


def _lead_status_class(status: str) -> str:
    return {
        Lead.Status.NOVO: "lead-status-new",
        Lead.Status.CONTATADO: "lead-status-contacted",
        Lead.Status.AGUARDANDO: "lead-status-waiting",
        Lead.Status.CONVERTIDO: "lead-status-converted",
    }.get(status, "lead-status-waiting")


def _lead_status_icon(status: str) -> str:
    return {
        Lead.Status.NOVO: "bi-stars",
        Lead.Status.CONTATADO: "bi-chat-dots",
        Lead.Status.AGUARDANDO: "bi-hourglass-split",
        Lead.Status.CONVERTIDO: "bi-check2-circle",
    }.get(status, "bi-circle")


def _lead_origin_class(origem: str) -> str:
    return {
        Lead.Origem.WHATSAPP: "lead-origin-whatsapp",
        Lead.Origem.INSTAGRAM: "lead-origin-instagram",
        Lead.Origem.INDICACAO: "lead-origin-referral",
        Lead.Origem.SITE: "lead-origin-site",
        Lead.Origem.MANUAL: "lead-origin-manual",
        Lead.Origem.OUTRO: "lead-origin-other",
    }.get(origem, "lead-origin-other")


def _lead_origin_icon(origem: str) -> str:
    return {
        Lead.Origem.WHATSAPP: "bi-whatsapp",
        Lead.Origem.INSTAGRAM: "bi-instagram",
        Lead.Origem.INDICACAO: "bi-people",
        Lead.Origem.SITE: "bi-globe2",
        Lead.Origem.MANUAL: "bi-pencil-square",
        Lead.Origem.OUTRO: "bi-three-dots",
    }.get(origem, "bi-three-dots")


def catalogo(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    itens = Service_catalog.objects.select_related("categoria").order_by("categoria__name", "tipo", "name")

    if busca:
        itens = itens.filter(
            Q(name__icontains=busca)
            | Q(tipo__icontains=busca)
            | Q(categoria__name__icontains=busca)
            | Q(descricao__icontains=busca)
        )

    categorias = CategoriaCatalogo.objects.annotate(total=Count("itens")).order_by("name")

    context = {
        "busca": busca,
        "itens": itens,
        "total_itens": itens.count(),
        "total_categorias": categorias.count(),
        "valor_medio": itens.aggregate(media=Avg("valor"))["media"] or 0,
        "categorias": categorias,
    }
    return render(request, "service/catalogo.html", context)


def nova_categoria(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = CategoriaCatalogoForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            messages.success(request, f"Categoria '{categoria.name}' cadastrada com sucesso.")
            return redirect("catalogo")
    else:
        form = CategoriaCatalogoForm()

    context = {
        "form": form,
        "categorias": CategoriaCatalogo.objects.annotate(total=Count("itens")).order_by("name"),
    }
    return render(request, "service/categoria_form.html", context)


def listar_clientes(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    clientes = Cliente.objects.order_by("name")

    if busca:
        clientes = clientes.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(telefone__icontains=busca)
            | Q(status__icontains=busca)
        )

    context = {
        "busca": busca,
        "clientes": clientes,
        "total_clientes": clientes.count(),
    }
    return render(request, "service/clientes.html", context)


def listar_leads(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    origem = request.GET.get("origem", "").strip()
    data_inicio = request.GET.get("data_inicio", "").strip()
    data_fim = request.GET.get("data_fim", "").strip()
    leads_query = Lead.objects.select_related("cliente").order_by("-created_at", "-id")

    if busca:
        leads_query = leads_query.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(telefone__icontains=busca)
            | Q(origem__icontains=busca)
            | Q(status__icontains=busca)
        )
    if status:
        leads_query = leads_query.filter(status=status)
    if origem:
        leads_query = leads_query.filter(origem=origem)

    data_inicio_parseada = parse_date(data_inicio) if data_inicio else None
    data_fim_parseada = parse_date(data_fim) if data_fim else None
    if data_inicio_parseada:
        leads_query = leads_query.filter(created_at__date__gte=data_inicio_parseada)
    if data_fim_parseada:
        leads_query = leads_query.filter(created_at__date__lte=data_fim_parseada)

    leads = []
    for lead in leads_query:
        leads.append(
            {
                "obj": lead,
                "name": lead.name,
                "telefone": lead.telefone or lead.email or "-",
                "status": lead.get_status_display(),
                "status_class": _lead_status_class(lead.status),
                "status_icon": _lead_status_icon(lead.status),
                "origem": lead.get_origem_display(),
                "origem_class": _lead_origin_class(lead.origem),
                "origem_icon": _lead_origin_icon(lead.origem),
                "data": lead.created_at.strftime("%d/%m/%Y"),
                "cliente": lead.cliente,
                "convertido": lead.status == Lead.Status.CONVERTIDO or lead.cliente_id is not None,
            }
        )

    context = {
        "busca": busca,
        "status_filtro": status,
        "origem_filtro": origem,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "status_choices": Lead.Status.choices,
        "origem_choices": Lead.Origem.choices,
        "leads": leads,
        "total_leads": leads_query.count(),
    }
    return render(request, "service/leads.html", context)


def _cliente_initial_orcamento(orcamento: Orcamento) -> dict:
    return {
        "orcamento_origem": orcamento.pk,
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
        "status": Cliente.Status.CONVERTIDO,
    }


def _cliente_initial_lead(lead: Lead) -> dict:
    return {
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
        "status": Cliente.Status.CONVERTIDO,
    }


def _orcamentos_origem_cliente():
    orcamentos = Orcamento.objects.filter(cliente__isnull=True).order_by("-created_at", "-id")[:50]
    return [
        {
            "id": orcamento.pk,
            "name": orcamento.name,
            "email": orcamento.email or "",
            "telefone": orcamento.telefone or "",
            "cep": orcamento.cep or "",
            "logradouro": orcamento.logradouro or "",
            "numero": orcamento.numero or "",
            "complemento": orcamento.complemento or "",
            "bairro": orcamento.bairro or "",
            "cidade": orcamento.cidade or "",
            "uf": orcamento.uf or "",
            "endereco": orcamento.endereco or "",
            "status": Cliente.Status.CONVERTIDO,
        }
        for orcamento in orcamentos
    ]


def novo_cliente(request: HttpRequest) -> HttpResponse:
    lead_id = request.GET.get("lead")
    lead = Lead.objects.filter(pk=lead_id, cliente__isnull=True).first() if lead_id else None

    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            orcamento = form.cleaned_data.get("orcamento_origem")
            if orcamento:
                orcamento.cliente = cliente
                orcamento.save(update_fields=["cliente", "updated_at"])
            if lead:
                lead.cliente = cliente
                lead.status = Lead.Status.CONVERTIDO
                lead.save(update_fields=["cliente", "status", "updated_at"])
            messages.success(request, f"Cliente '{cliente.name}' cadastrado com sucesso.")
            return redirect("clientes")
    else:
        orcamento_id = request.GET.get("orcamento") or request.GET.get("orcamento_origem")
        orcamento = Orcamento.objects.filter(pk=orcamento_id, cliente__isnull=True).first() if orcamento_id else None
        initial = _cliente_initial_lead(lead) if lead else _cliente_initial_orcamento(orcamento) if orcamento else None
        form = ClienteForm(initial=initial)

    context = {
        "form": form,
        "clientes_recentes": Cliente.objects.order_by("-created_at", "-id")[:5],
        "orcamentos_origem": _orcamentos_origem_cliente(),
        "is_edit": False,
    }
    return render(request, "service/cliente_form.html", context)


def editar_cliente(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente = form.save()
            messages.success(request, f"Cliente '{cliente.name}' atualizado com sucesso.")
            return redirect("clientes")
    else:
        form = ClienteForm(instance=cliente)

    context = {
        "form": form,
        "cliente": cliente,
        "clientes_recentes": Cliente.objects.exclude(pk=pk).order_by("-created_at", "-id")[:5],
        "orcamentos_origem": [],
        "is_edit": True,
    }
    return render(request, "service/cliente_form.html", context)


def novo_lead(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save()
            messages.success(request, f"Lead '{lead.name}' cadastrado com sucesso.")
            return redirect("leads")
    else:
        form = LeadForm()

    context = {
        "form": form,
        "leads_recentes": Lead.objects.order_by("-created_at", "-id")[:5],
    }
    return render(request, "service/lead_form.html", context)


def deletar_cliente(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("clientes")

    cliente = get_object_or_404(Cliente, pk=pk)
    nome = cliente.name
    cliente.delete()

    messages.success(request, f"Cliente '{nome}' excluido com sucesso.")
    return redirect("clientes")
