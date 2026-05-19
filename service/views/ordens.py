from calendar import Calendar
from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
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


def _dinheiro(valor: float) -> str:
    valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {valor_formatado}"


def _cliente_ordem(ordem: OrdemServico) -> str:
    if ordem.cliente_id:
        return ordem.cliente.name
    if ordem.orcamento_id:
        return ordem.orcamento.name
    return "Cliente nao informado"


def _agenda_label_ordem(ordem: OrdemServico) -> str:
    return f"{ordem.data_agendada:%d/%m/%Y} {ordem.hora_inicio:%H:%M}"


def _colunas_ordens(ordens: list[OrdemServico]) -> list[dict]:
    colunas = [
        {"key": OrdemServico.Status.AGENDADA, "title": "Agendadas", "cards": []},
        {"key": OrdemServico.Status.EM_ANDAMENTO, "title": "Em andamento", "cards": []},
        {"key": OrdemServico.Status.CONCLUIDA, "title": "Concluidas", "cards": []},
        {"key": OrdemServico.Status.CANCELADA, "title": "Canceladas", "cards": []},
    ]
    colunas_por_status = {coluna["key"]: coluna for coluna in colunas}

    for ordem in ordens:
        coluna = colunas_por_status.get(ordem.status, colunas_por_status[OrdemServico.Status.AGENDADA])
        coluna["cards"].append(
            {
                "numero": f"#{ordem.pk}",
                "status_label": ordem.get_status_display(),
                "cliente": _cliente_ordem(ordem),
                "servico": ordem.titulo,
                "agenda": _agenda_label_ordem(ordem),
                "valor": _dinheiro(ordem.valor),
                "status_key": ordem.status,
                "obj": ordem,
            }
        )

    return colunas


def _parse_date(value: str | None) -> date:
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return timezone.localdate()


def _agenda_data_base(request: HttpRequest) -> date:
    data_param = request.GET.get("data")
    if data_param:
        return _parse_date(data_param)

    hoje = timezone.localdate()
    if OrdemServico.objects.filter(data_agendada__gte=hoje).exists():
        return OrdemServico.objects.filter(data_agendada__gte=hoje).earliest("data_agendada").data_agendada

    ultima_ordem = OrdemServico.objects.order_by("-data_agendada").first()
    return ultima_ordem.data_agendada if ultima_ordem else hoje


def _shift_month(base: date, offset: int) -> date:
    month_index = (base.month - 1) + offset
    year = base.year + (month_index // 12)
    month = (month_index % 12) + 1
    return date(year, month, 1)


def _agenda_evento_ordem(ordem: OrdemServico, equipe: str = "a") -> dict:
    return {
        "pk": ordem.pk,
        "dia": ordem.data_agendada.isoformat(),
        "horario": ordem.hora_inicio.strftime("%H:%M"),
        "equipe": equipe,
        "cliente": _cliente_ordem(ordem),
        "servico": ordem.titulo,
        "endereco": ordem.endereco or "Endereco nao informado",
        "responsavel": ordem.responsavel_nome,
        "status_label": ordem.get_status_display(),
        "status_css": _status_class(ordem.status),
        "valor": _dinheiro(ordem.valor),
        "agenda": _agenda_label_ordem(ordem),
        "tamanho": "grande" if ordem.hora_fim and ordem.hora_fim.hour > ordem.hora_inicio.hour else "",
    }


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
        ordem.cliente_nome = _cliente_ordem(ordem)

    todas_ordens = OrdemServico.objects.all()
    context = {
        "busca": busca,
        "ordens": ordens,
        "colunas_ordens": _colunas_ordens(ordens),
        "total_ordens": todas_ordens.count(),
        "total_filtrado": len(ordens),
        "total_agendadas": todas_ordens.filter(status=OrdemServico.Status.AGENDADA).count(),
        "total_em_andamento": todas_ordens.filter(status=OrdemServico.Status.EM_ANDAMENTO).count(),
        "total_concluidas": todas_ordens.filter(status=OrdemServico.Status.CONCLUIDA).count(),
        "total_canceladas": todas_ordens.filter(status=OrdemServico.Status.CANCELADA).count(),
    }
    return render(request, "service/ordens_servico.html", context)


def agenda(request: HttpRequest) -> HttpResponse:
    data_base = _agenda_data_base(request)
    inicio_semana = data_base - timedelta(days=data_base.weekday())
    dias_datas = [inicio_semana + timedelta(days=index) for index in range(7)]
    inicio_mes = data_base.replace(day=1)
    mes_anterior = _shift_month(inicio_mes, -1)
    proximo_mes = _shift_month(inicio_mes, 1)
    semanas_mes = Calendar(firstweekday=0).monthdatescalendar(inicio_mes.year, inicio_mes.month)
    inicio_grade_mes = semanas_mes[0][0]
    fim_grade_mes = semanas_mes[-1][-1]
    ordens_mes = list(
        OrdemServico.objects.select_related("cliente", "tecnico", "orcamento")
        .filter(data_agendada__range=(inicio_grade_mes, fim_grade_mes))
        .order_by("data_agendada", "hora_inicio", "id")
    )
    ordens = (
        OrdemServico.objects.select_related("cliente", "tecnico", "orcamento")
        .filter(data_agendada__range=(dias_datas[0], dias_datas[-1]))
        .order_by("data_agendada", "hora_inicio", "id")
    )
    ordens = list(ordens)
    for ordem in ordens:
        ordem.status_css = _status_class(ordem.status)
        ordem.cliente_nome = _cliente_ordem(ordem)

    eventos_por_dia_mes = {}
    for ordem in ordens_mes:
        eventos_por_dia_mes.setdefault(ordem.data_agendada, []).append(_agenda_evento_ordem(ordem))

    dias_mes = []
    for semana in semanas_mes:
        dias_mes.append(
            [
                {
                    "data": dia,
                    "numero": dia.strftime("%d"),
                    "is_today": dia == timezone.localdate(),
                    "is_current_month": dia.month == inicio_mes.month,
                    "eventos": eventos_por_dia_mes.get(dia, []),
                }
                for dia in semana
            ]
        )

    ordens_por_dia = []
    for dia in dias_datas:
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
        "dias_mes": dias_mes,
        "dias": ordens_por_dia,
        "periodo_mes": inicio_mes.strftime("%m/%Y"),
        "periodo_agenda": f"{dias_datas[0]:%d/%m} - {dias_datas[-1]:%d/%m/%Y}",
        "mes_anterior": mes_anterior.isoformat(),
        "proximo_mes": proximo_mes.isoformat(),
        "semana_anterior": (inicio_semana - timedelta(days=7)).isoformat(),
        "proxima_semana": (inicio_semana + timedelta(days=7)).isoformat(),
        "hoje": timezone.localdate().isoformat(),
        "total_mes": sum(1 for ordem in ordens_mes if ordem.data_agendada.month == inicio_mes.month),
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


def atualizar_status_ordem_servico(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    novo_status = request.POST.get("status")
    status_validos = set(OrdemServico.Status.values)
    if novo_status not in status_validos:
        return JsonResponse({"ok": False, "error": "Status invalido."}, status=400)

    ordem = get_object_or_404(OrdemServico, pk=pk)
    ordem.status = novo_status
    if novo_status == OrdemServico.Status.CONCLUIDA and not ordem.data_conclusao:
        ordem.data_conclusao = timezone.now()
    elif novo_status != OrdemServico.Status.CONCLUIDA:
        ordem.data_conclusao = None
    ordem.save(update_fields=["status", "data_conclusao", "updated_at"])

    totais = OrdemServico.objects.values_list("status").order_by()
    totais_por_status = {status: 0 for status in status_validos}
    for status, in totais:
        totais_por_status[status] = totais_por_status.get(status, 0) + 1

    return JsonResponse(
        {
            "ok": True,
            "status": ordem.status,
            "status_label": ordem.get_status_display(),
            "status_css": _status_class(ordem.status),
            "totais": totais_por_status,
        }
    )


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
