from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from service.forms import CategoriaCatalogoForm, ClienteForm
from service.models import CategoriaCatalogo, Cliente, Orcamento, Service_catalog


def _lead_status_class(status: str) -> str:
    return {
        Cliente.Status.NOVO: "status-blue",
        Cliente.Status.CONTATADO: "status-yellow",
        Cliente.Status.AGUARDANDO: "status-gray",
        Cliente.Status.CONVERTIDO: "status-soft-blue",
    }.get(status, "status-gray")


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
    todos_clientes = Cliente.objects.prefetch_related("orcamentos").order_by("name")
    clientes = todos_clientes

    if busca:
        clientes = clientes.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(telefone__icontains=busca)
            | Q(endereco__icontains=busca)
            | Q(bairro__icontains=busca)
            | Q(cidade__icontains=busca)
            | Q(uf__icontains=busca)
            | Q(status__icontains=busca)
        )

    clientes = clientes.annotate(
        total_servicos=Count("orcamentos", distinct=True),
        total_gasto=Sum("orcamentos__valor"),
        ticket_medio=Avg("orcamentos__valor"),
    )

    def tipo_cliente(cliente: Cliente) -> str:
        texto = f"{cliente.name} {cliente.email}".lower()
        termos_empresariais = ("empresa", "ltda", "tech", "hotel", "plaza", "clean", "corp", "comercial")
        if any(termo in texto for termo in termos_empresariais):
            return "Empresarial"
        return "Residencial"

    def mes_cliente(cliente: Cliente) -> str:
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        return f"{meses[cliente.created_at.month - 1]}/{cliente.created_at.year}"

    def contato_cliente(cliente: Cliente) -> str:
        return cliente.telefone or cliente.email or "-"

    def localizacao_cliente(cliente: Cliente) -> str:
        if cliente.bairro and cliente.cidade and cliente.uf:
            return f"{cliente.bairro}, {cliente.cidade} - {cliente.uf}"
        if cliente.cidade and cliente.uf:
            return f"{cliente.cidade} - {cliente.uf}"
        return cliente.endereco or "-"

    linhas_clientes = [
        {
            "obj": cliente,
            "name": cliente.name,
            "desde": mes_cliente(cliente),
            "contato": contato_cliente(cliente),
            "localizacao": localizacao_cliente(cliente),
            "tipo": tipo_cliente(cliente),
            "tipo_class": "client-type-business" if tipo_cliente(cliente) == "Empresarial" else "client-type-residential",
            "servicos": cliente.total_servicos or 0,
            "total_gasto": cliente.total_gasto or 0,
            "ticket_medio": cliente.ticket_medio or 0,
        }
        for cliente in clientes
    ]

    if not linhas_clientes and not busca:
        linhas_clientes = _clientes_exemplo()

    total_residenciais = sum(1 for cliente in linhas_clientes if cliente["tipo"] == "Residencial")
    total_empresariais = sum(1 for cliente in linhas_clientes if cliente["tipo"] == "Empresarial")
    faturamento_total = sum(cliente["total_gasto"] for cliente in linhas_clientes)

    context = {
        "busca": busca,
        "clientes": linhas_clientes,
        "total_clientes": len(linhas_clientes),
        "total_residenciais": total_residenciais,
        "total_empresariais": total_empresariais,
        "faturamento_total": faturamento_total,
    }
    return render(request, "service/clientes.html", context)


def _clientes_exemplo() -> list[dict]:
    nomes = [
        ("Roberto Alves", "Mar/2026", "(11) 98765-4321", "Jardim Paulista, São Paulo - SP", "Residencial", 3, 1450, 483),
        ("Empresa Clean Tech Ltda", "Jan/2026", "(11) 3456-7890", "Centro, São Paulo - SP", "Empresarial", 8, 6240, 780),
        ("Maria Santos", "Abr/2026", "(11) 97654-3210", "Vila Mariana, São Paulo - SP", "Residencial", 2, 890, 445),
        ("Carlos Oliveira", "Fev/2026", "(11) 96543-2109", "Pinheiros, São Paulo - SP", "Residencial", 5, 2180, 436),
        ("Hotel Confort Plaza", "Jan/2026", "(11) 3789-0123", "Brooklin, São Paulo - SP", "Empresarial", 12, 9600, 800),
        ("Ana Costa", "Abr/2026", "(11) 95432-1098", "Moema, São Paulo - SP", "Residencial", 1, 320, 320),
        ("Paulo Mendes", "Mar/2026", "(11) 94321-0987", "Itaim Bibi, São Paulo - SP", "Residencial", 4, 1680, 420),
    ]
    return [
        {
            "obj": None,
            "name": nome,
            "desde": desde,
            "contato": contato,
            "localizacao": localizacao,
            "tipo": tipo,
            "tipo_class": "client-type-business" if tipo == "Empresarial" else "client-type-residential",
            "servicos": servicos,
            "total_gasto": total_gasto,
            "ticket_medio": ticket_medio,
        }
        for nome, desde, contato, localizacao, tipo, servicos, total_gasto, ticket_medio in nomes
    ]


def listar_leads(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    clientes = Cliente.objects.order_by("-created_at", "-id")

    if busca:
        clientes = clientes.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(telefone__icontains=busca)
            | Q(status__icontains=busca)
        )

    origem_cycle = ["WhatsApp", "Instagram", "Indicação"]
    leads = []
    for index, cliente in enumerate(clientes[:5]):
        leads.append(
            {
                "name": cliente.name,
                "telefone": cliente.telefone or cliente.email or "-",
                "status": cliente.get_status_display(),
                "status_class": _lead_status_class(cliente.status),
                "origem": origem_cycle[index % len(origem_cycle)],
                "data": cliente.created_at.strftime("%d/%m/%Y"),
            }
        )

    if not leads and not busca:
        leads = [
            {
                "name": "Maria Santos",
                "telefone": "(11) 98765-4321",
                "status": "Novo",
                "status_class": "status-blue",
                "origem": "WhatsApp",
                "data": "29/04/2026",
            },
            {
                "name": "Carlos Oliveira",
                "telefone": "(11) 97654-3210",
                "status": "Contatado",
                "status_class": "status-yellow",
                "origem": "Instagram",
                "data": "28/04/2026",
            },
            {
                "name": "Ana Costa",
                "telefone": "(11) 96543-2109",
                "status": "Aguardando",
                "status_class": "status-gray",
                "origem": "Indicação",
                "data": "28/04/2026",
            },
            {
                "name": "Paulo Mendes",
                "telefone": "(11) 95432-1098",
                "status": "Novo",
                "status_class": "status-blue",
                "origem": "WhatsApp",
                "data": "27/04/2026",
            },
            {
                "name": "Fernanda Rocha",
                "telefone": "(11) 94321-0987",
                "status": "Contatado",
                "status_class": "status-yellow",
                "origem": "Instagram",
                "data": "27/04/2026",
            },
        ]

    context = {
        "busca": busca,
        "leads": leads,
        "total_leads": clientes.count() if busca or Cliente.objects.exists() else len(leads),
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
    if request.method == "POST":
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save()
            orcamento = form.cleaned_data.get("orcamento_origem")
            if orcamento:
                orcamento.cliente = cliente
                orcamento.save(update_fields=["cliente", "updated_at"])
            messages.success(request, f"Cliente '{cliente.name}' cadastrado com sucesso.")
            return redirect("clientes")
    else:
        orcamento_id = request.GET.get("orcamento") or request.GET.get("orcamento_origem")
        orcamento = Orcamento.objects.filter(pk=orcamento_id, cliente__isnull=True).first() if orcamento_id else None
        form = ClienteForm(initial=_cliente_initial_orcamento(orcamento) if orcamento else None)

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
        form = ClienteForm(request.POST)
        if form.is_valid():
            lead = form.save()
            messages.success(request, f"Lead '{lead.name}' cadastrado com sucesso.")
            return redirect("leads")
    else:
        form = ClienteForm()

    context = {
        "form": form,
        "leads_recentes": Cliente.objects.order_by("-created_at", "-id")[:5],
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
