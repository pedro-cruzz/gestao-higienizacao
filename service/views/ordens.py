from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from service.forms import OrdemServicoConclusaoForm, OrdemServicoForm, TecnicoForm
from service.models import Orcamento, OrdemServico, Tecnico


def _status_class(status: str) -> str:
    return {
        OrdemServico.Status.AGENDADA: "status-blue",
        OrdemServico.Status.EM_ANDAMENTO: "status-purple",
        OrdemServico.Status.CONCLUIDA: "status-soft-blue",
        OrdemServico.Status.CANCELADA: "status-red",
    }.get(status, "status-gray")


def _parse_date(value: str | None) -> date:
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return timezone.localdate()


def _ordem_initial_orcamento(orcamento: Orcamento) -> dict:
    itens = ", ".join(item.name for item in orcamento.itens.all())
    return {
        "orcamento": orcamento.pk,
        "cliente": orcamento.cliente_id,
        "titulo": f"Servico para {orcamento.name}",
        "descricao": itens or orcamento.descricao or "",
        "endereco": orcamento.endereco or "",
        "valor": orcamento.valor,
        "status": OrdemServico.Status.AGENDADA,
    }


def listar_ordens_servico(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    ordens = OrdemServico.objects.select_related("cliente", "tecnico", "orcamento").order_by(
        "-data_agendada",
        "-hora_inicio",
        "-id",
    )

    if busca:
        ordens = ordens.filter(
            Q(titulo__icontains=busca)
            | Q(cliente__name__icontains=busca)
            | Q(orcamento__name__icontains=busca)
            | Q(tecnico__name__icontains=busca)
            | Q(endereco__icontains=busca)
        )

    ordens = list(ordens)
    for ordem in ordens:
        ordem.status_css = _status_class(ordem.status)

    todas_ordens = OrdemServico.objects.all()
    context = {
        "busca": busca,
        "ordens": ordens,
        "total_ordens": todas_ordens.count(),
        "total_filtrado": len(ordens),
        "total_agendadas": todas_ordens.filter(status=OrdemServico.Status.AGENDADA).count(),
        "total_em_andamento": todas_ordens.filter(status=OrdemServico.Status.EM_ANDAMENTO).count(),
        "total_concluidas": todas_ordens.filter(status=OrdemServico.Status.CONCLUIDA).count(),
        "total_canceladas": todas_ordens.filter(status=OrdemServico.Status.CANCELADA).count(),
    }
    return render(request, "service/ordens_servico.html", context)


def agenda(request: HttpRequest) -> HttpResponse:
    data_base = _parse_date(request.GET.get("data"))
    inicio_semana = data_base - timedelta(days=data_base.weekday())
    dias = [inicio_semana + timedelta(days=index) for index in range(7)]
    ordens = (
        OrdemServico.objects.select_related("cliente", "tecnico", "orcamento")
        .filter(data_agendada__range=(dias[0], dias[-1]))
        .order_by("data_agendada", "hora_inicio", "id")
    )
    ordens = list(ordens)
    for ordem in ordens:
        ordem.status_css = _status_class(ordem.status)

    ordens_por_dia = []
    for dia in dias:
        ordens_do_dia = [ordem for ordem in ordens if ordem.data_agendada == dia]
        ordens_por_dia.append(
            {
                "data": dia,
                "ordens": ordens_do_dia,
                "is_today": dia == timezone.localdate(),
            }
        )

    context = {
        "data_base": data_base,
        "dias": ordens_por_dia,
        "semana_anterior": (inicio_semana - timedelta(days=7)).isoformat(),
        "proxima_semana": (inicio_semana + timedelta(days=7)).isoformat(),
        "hoje": timezone.localdate().isoformat(),
        "total_semana": len(ordens),
    }
    return render(request, "service/agenda.html", context)


def nova_ordem_servico(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = OrdemServicoForm(request.POST)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, f"OS #{ordem.pk} criada e agendada com sucesso.")
            return redirect("os_detalhe", pk=ordem.pk)
    else:
        orcamento_id = request.GET.get("orcamento")
        orcamento = (
            Orcamento.objects.prefetch_related("itens")
            .filter(pk=orcamento_id, aprovado=True, ordem_servico__isnull=True)
            .first()
            if orcamento_id
            else None
        )
        form = OrdemServicoForm(initial=_ordem_initial_orcamento(orcamento) if orcamento else None)

    context = {
        "form": form,
        "is_edit": False,
        "tecnicos_recentes": Tecnico.objects.order_by("-created_at", "-id")[:5],
    }
    return render(request, "service/os_form.html", context)


def editar_ordem_servico(request: HttpRequest, pk: int) -> HttpResponse:
    ordem = get_object_or_404(OrdemServico.objects.select_related("cliente", "tecnico", "orcamento"), pk=pk)

    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, f"OS #{ordem.pk} atualizada com sucesso.")
            return redirect("os_detalhe", pk=ordem.pk)
    else:
        form = OrdemServicoForm(instance=ordem)

    context = {
        "form": form,
        "ordem": ordem,
        "is_edit": True,
        "tecnicos_recentes": Tecnico.objects.order_by("-created_at", "-id")[:5],
    }
    return render(request, "service/os_form.html", context)


def detalhe_ordem_servico(request: HttpRequest, pk: int) -> HttpResponse:
    ordem = get_object_or_404(
        OrdemServico.objects.select_related("cliente", "tecnico", "orcamento").prefetch_related("orcamento__itens"),
        pk=pk,
    )
    conclusao_form = OrdemServicoConclusaoForm(instance=ordem)
    context = {
        "ordem": ordem,
        "conclusao_form": conclusao_form,
        "status_class": _status_class(ordem.status),
    }
    return render(request, "service/os_detalhe.html", context)


def concluir_ordem_servico(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("os_detalhe", pk=pk)

    ordem = get_object_or_404(OrdemServico, pk=pk)
    form = OrdemServicoConclusaoForm(request.POST, instance=ordem)
    if form.is_valid():
        ordem = form.save(commit=False)
        if ordem.status == OrdemServico.Status.CONCLUIDA and not ordem.data_conclusao:
            ordem.data_conclusao = timezone.now()
        elif ordem.status != OrdemServico.Status.CONCLUIDA:
            ordem.data_conclusao = None
        ordem.save()
        messages.success(request, f"OS #{ordem.pk} atualizada com sucesso.")
    else:
        messages.error(request, "Revise os dados de conclusao da OS.")

    return redirect("os_detalhe", pk=pk)


def listar_tecnicos(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    tecnicos = Tecnico.objects.order_by("name")
    if busca:
        tecnicos = tecnicos.filter(
            Q(name__icontains=busca)
            | Q(email__icontains=busca)
            | Q(telefone__icontains=busca)
            | Q(especialidade__icontains=busca)
        )

    context = {
        "busca": busca,
        "tecnicos": tecnicos,
        "total_tecnicos": tecnicos.count(),
    }
    return render(request, "service/tecnicos.html", context)


def novo_tecnico(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = TecnicoForm(request.POST)
        if form.is_valid():
            tecnico = form.save()
            messages.success(request, f"Equipe '{tecnico.name}' cadastrada com sucesso.")
            return redirect("tecnicos")
    else:
        form = TecnicoForm(initial={"ativo": True})

    return render(request, "service/tecnico_form.html", {"form": form, "is_edit": False})


def editar_tecnico(request: HttpRequest, pk: int) -> HttpResponse:
    tecnico = get_object_or_404(Tecnico, pk=pk)
    if request.method == "POST":
        form = TecnicoForm(request.POST, instance=tecnico)
        if form.is_valid():
            tecnico = form.save()
            messages.success(request, f"Equipe '{tecnico.name}' atualizada com sucesso.")
            return redirect("tecnicos")
    else:
        form = TecnicoForm(instance=tecnico)

    return render(request, "service/tecnico_form.html", {"form": form, "tecnico": tecnico, "is_edit": True})
