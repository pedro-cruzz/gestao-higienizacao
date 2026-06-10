from calendar import Calendar
import json
from datetime import date, timedelta
from urllib.parse import quote_plus

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from service.access import is_admin_user
from service.forms import OrdemServicoConclusaoForm, OrdemServicoForm, TecnicoForm
from service.models import Cliente, Orcamento, OrdemServico, Tecnico
from service.ownership import owned_queryset, set_owner
from service.services.nominatim import (
    NominatimLookupError,
    NominatimService,
    NominatimTemporaryUnavailableError,
)


ROUTE_ADDRESS_HINTS = (
    " rua ",
    " r. ",
    " avenida ",
    " av. ",
    " travessa ",
    " alameda ",
    " rodovia ",
    " estrada ",
    " praça ",
    " praca ",
    " largo ",
    " viela ",
)


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


def _endereco_para_mapa_ordem(ordem: OrdemServico) -> str:
    if ordem.endereco:
        return ordem.endereco.strip()

    origem = ordem.cliente or ordem.orcamento
    if not origem:
        return ""

    partes = [
        getattr(origem, "logradouro", None),
        getattr(origem, "numero", None),
        getattr(origem, "bairro", None),
        getattr(origem, "cidade", None),
        getattr(origem, "uf", None),
        getattr(origem, "cep", None),
    ]
    endereco_estruturado = ", ".join(str(parte).strip() for parte in partes if parte)
    return endereco_estruturado or (getattr(origem, "endereco", "") or "").strip()


def _parece_endereco_especifico(endereco: str) -> bool:
    texto = f" {endereco.strip().lower()} "
    return any(char.isdigit() for char in texto) or any(indicio in texto for indicio in ROUTE_ADDRESS_HINTS)


def _endereco_para_rota_do_dia(ordem: OrdemServico) -> str:
    if ordem.endereco:
        endereco = ordem.endereco.strip()
        return endereco if _parece_endereco_especifico(endereco) else ""

    origem = ordem.cliente or ordem.orcamento
    if not origem:
        return ""

    logradouro = (getattr(origem, "logradouro", "") or "").strip()
    if logradouro:
        partes = [
            logradouro,
            getattr(origem, "numero", None),
            getattr(origem, "bairro", None),
            getattr(origem, "cidade", None),
            getattr(origem, "uf", None),
            getattr(origem, "cep", None),
        ]
        return ", ".join(str(parte).strip() for parte in partes if parte)

    endereco = (getattr(origem, "endereco", "") or "").strip()
    return endereco if _parece_endereco_especifico(endereco) else ""


def _links_mapa_ordem(ordem: OrdemServico) -> dict[str, str]:
    endereco = _endereco_para_mapa_ordem(ordem)
    if not endereco:
        return {}

    query = quote_plus(endereco)
    return {
        "endereco": endereco,
        "maps_url": f"https://www.google.com/maps/search/?api=1&query={query}",
        "rota_url": f"https://www.google.com/maps/dir/?api=1&destination={query}&travelmode=driving",
    }


def _rota_do_dia_paradas(ordens: list[OrdemServico]) -> list[str]:
    enderecos = [_endereco_para_rota_do_dia(ordem) for ordem in ordens]
    return [endereco for endereco in enderecos if endereco]


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


def _ordens_visiveis_queryset(user):
    ordens = OrdemServico.objects.all()
    if is_admin_user(user):
        return owned_queryset(ordens, user)
    return ordens.filter(tecnico__user=user)


def _agenda_data_base(request: HttpRequest, ordens) -> date:
    data_param = request.GET.get("data")
    if data_param:
        return _parse_date(data_param)

    hoje = timezone.localdate()
    proxima_ordem = ordens.filter(data_agendada__gte=hoje).order_by("data_agendada").first()
    if proxima_ordem:
        return proxima_ordem.data_agendada

    ultima_ordem = ordens.order_by("-data_agendada").first()
    return ultima_ordem.data_agendada if ultima_ordem else hoje


def _shift_month(base: date, offset: int) -> date:
    month_index = (base.month - 1) + offset
    year = base.year + (month_index // 12)
    month = (month_index % 12) + 1
    return date(year, month, 1)


def _agenda_evento_ordem(ordem: OrdemServico, equipe: str = "a") -> dict:
    mapa = _links_mapa_ordem(ordem)
    return {
        "pk": ordem.pk,
        "dia": ordem.data_agendada.isoformat(),
        "horario": ordem.hora_inicio.strftime("%H:%M"),
        "equipe": equipe,
        "cliente": _cliente_ordem(ordem),
        "servico": ordem.titulo,
        "endereco": mapa.get("endereco") or "Endereco nao informado",
        "responsavel": ordem.responsavel_nome,
        "status_label": ordem.get_status_display(),
        "status_css": _status_class(ordem.status),
        "valor": _dinheiro(ordem.valor),
        "agenda": _agenda_label_ordem(ordem),
        "maps_url": mapa.get("maps_url", ""),
        "rota_url": mapa.get("rota_url", ""),
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
    todas_ordens = _ordens_visiveis_queryset(request.user)
    ordens = todas_ordens.select_related("cliente", "tecnico", "orcamento").order_by(
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
        ordem.mapa = _links_mapa_ordem(ordem)

    context = {
        "busca": busca,
        "ordens": ordens,
        "clientes": owned_queryset(Cliente.objects, request.user).order_by("name", "id"),
        "tecnicos": owned_queryset(Tecnico.objects, request.user).filter(ativo=True).order_by("name", "id"),
        "can_manage_os_links": is_admin_user(request.user),
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
    ordens_visiveis = _ordens_visiveis_queryset(request.user)
    data_base = _agenda_data_base(request, ordens_visiveis)
    inicio_semana = data_base - timedelta(days=data_base.weekday())
    dias_datas = [inicio_semana + timedelta(days=index) for index in range(7)]
    inicio_mes = data_base.replace(day=1)
    mes_anterior = _shift_month(inicio_mes, -1)
    proximo_mes = _shift_month(inicio_mes, 1)
    semanas_mes = Calendar(firstweekday=0).monthdatescalendar(inicio_mes.year, inicio_mes.month)
    inicio_grade_mes = semanas_mes[0][0]
    fim_grade_mes = semanas_mes[-1][-1]
    ordens_mes = list(
        ordens_visiveis.select_related("cliente", "tecnico", "orcamento")
        .filter(data_agendada__range=(inicio_grade_mes, fim_grade_mes))
        .order_by("data_agendada", "hora_inicio", "id")
    )
    ordens = (
        ordens_visiveis.select_related("cliente", "tecnico", "orcamento")
        .filter(data_agendada__range=(dias_datas[0], dias_datas[-1]))
        .order_by("data_agendada", "hora_inicio", "id")
    )
    ordens = list(ordens)
    for ordem in ordens:
        ordem.status_css = _status_class(ordem.status)
        ordem.cliente_nome = _cliente_ordem(ordem)
        ordem.mapa = _links_mapa_ordem(ordem)

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
        rota_stops = _rota_do_dia_paradas(ordens_do_dia)
        ordens_por_dia.append(
            {
                "data": dia,
                "ordens": ordens_do_dia,
                "rota_stops": rota_stops,
                "rota_stops_json": json.dumps(rota_stops, ensure_ascii=False),
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
        form = OrdemServicoForm(request.POST, user=request.user)
        if form.is_valid():
            ordem = form.save(commit=False)
            set_owner(ordem, request.user)
            ordem.save()
            form.save_m2m()
            messages.success(request, f"OS #{ordem.pk} criada e agendada com sucesso.")
            return redirect("os_detalhe", pk=ordem.pk)
    else:
        orcamento_id = request.GET.get("orcamento")
        orcamento = (
            owned_queryset(Orcamento.objects.prefetch_related("itens"), request.user)
            .filter(pk=orcamento_id, aprovado=True, ordem_servico__isnull=True)
            .first()
            if orcamento_id
            else None
        )
        form = OrdemServicoForm(initial=_ordem_initial_orcamento(orcamento) if orcamento else None, user=request.user)

    context = {
        "form": form,
        "is_edit": False,
        "tecnicos_recentes": owned_queryset(Tecnico.objects, request.user).order_by("-created_at", "-id")[:5],
    }
    return render(request, "service/os_form.html", context)


def editar_ordem_servico(request: HttpRequest, pk: int) -> HttpResponse:
    ordem = get_object_or_404(
        owned_queryset(OrdemServico.objects.select_related("cliente", "tecnico", "orcamento"), request.user),
        pk=pk,
    )

    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem, user=request.user)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, f"OS #{ordem.pk} atualizada com sucesso.")
            return redirect("os_detalhe", pk=ordem.pk)
    else:
        form = OrdemServicoForm(instance=ordem, user=request.user)

    context = {
        "form": form,
        "ordem": ordem,
        "is_edit": True,
        "tecnicos_recentes": owned_queryset(Tecnico.objects, request.user).order_by("-created_at", "-id")[:5],
    }
    return render(request, "service/os_form.html", context)


def detalhe_ordem_servico(request: HttpRequest, pk: int) -> HttpResponse:
    ordem = get_object_or_404(
        _ordens_visiveis_queryset(request.user)
        .select_related("cliente", "tecnico", "orcamento")
        .prefetch_related("orcamento__itens"),
        pk=pk,
    )
    conclusao_form = OrdemServicoConclusaoForm(instance=ordem)
    context = {
        "ordem": ordem,
        "conclusao_form": conclusao_form,
        "status_class": _status_class(ordem.status),
        "mapa": _links_mapa_ordem(ordem),
    }
    return render(request, "service/os_detalhe.html", context)


def buscar_mapa_ordem_servico(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    ordem = get_object_or_404(
        _ordens_visiveis_queryset(request.user).select_related("cliente", "orcamento"),
        pk=pk,
    )
    endereco = _endereco_para_mapa_ordem(ordem)
    if not endereco:
        return JsonResponse(
            {"ok": False, "error": "Cadastre o endereco do servico para visualizar o mapa."},
            status=400,
        )

    origem = ordem.cliente or ordem.orcamento
    try:
        localizacao = NominatimService().geocodificar(
            endereco=endereco,
            cep=(getattr(origem, "cep", "") or "") if origem else "",
            logradouro=(getattr(origem, "logradouro", "") or ordem.endereco or "") if origem else ordem.endereco or "",
            numero=(getattr(origem, "numero", "") or "") if origem else "",
            bairro=(getattr(origem, "bairro", "") or "") if origem else "",
            cidade=(getattr(origem, "cidade", "") or "") if origem else "",
            uf=(getattr(origem, "uf", "") or "") if origem else "",
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


def atualizar_status_ordem_servico(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    novo_status = request.POST.get("status")
    status_validos = set(OrdemServico.Status.values)
    if novo_status not in status_validos:
        return JsonResponse({"ok": False, "error": "Status invalido."}, status=400)

    ordem = get_object_or_404(_ordens_visiveis_queryset(request.user), pk=pk)
    ordem.status = novo_status
    if novo_status == OrdemServico.Status.CONCLUIDA and not ordem.data_conclusao:
        ordem.data_conclusao = timezone.now()
    elif novo_status != OrdemServico.Status.CONCLUIDA:
        ordem.data_conclusao = None
    ordem.save(update_fields=["status", "data_conclusao", "updated_at"])

    totais = _ordens_visiveis_queryset(request.user).values_list("status").order_by()
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


def atualizar_vinculos_ordem_servico(request: HttpRequest, pk: int) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Metodo nao permitido."}, status=405)

    ordem = get_object_or_404(
        owned_queryset(OrdemServico.objects.select_related("cliente", "tecnico", "orcamento"), request.user),
        pk=pk,
    )
    campo = request.POST.get("campo")
    valor = request.POST.get("valor", "").strip()

    if campo == "cliente":
        ordem.cliente = owned_queryset(Cliente.objects, request.user).filter(pk=valor).first() if valor else None
        ordem.save(update_fields=["cliente", "updated_at"])
    elif campo == "responsavel":
        if valor and valor != "admin":
            tecnico = owned_queryset(Tecnico.objects, request.user).filter(pk=valor, ativo=True).first()
            if not tecnico:
                return JsonResponse({"ok": False, "error": "Equipe tecnica invalida."}, status=400)
            ordem.tecnico = tecnico
            ordem.administrador_executa = False
        else:
            ordem.tecnico = None
            ordem.administrador_executa = True
        ordem.save(update_fields=["tecnico", "administrador_executa", "updated_at"])
    else:
        return JsonResponse({"ok": False, "error": "Campo invalido."}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "cliente": _cliente_ordem(ordem),
            "responsavel": ordem.responsavel_nome,
        }
    )


def concluir_ordem_servico(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("os_detalhe", pk=pk)

    ordem = get_object_or_404(_ordens_visiveis_queryset(request.user), pk=pk)
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


def deletar_ordem_servico(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("os_detalhe", pk=pk)

    ordem = get_object_or_404(owned_queryset(OrdemServico.objects, request.user), pk=pk)
    numero = ordem.pk
    ordem.delete()

    messages.success(request, f"OS #{numero} excluida com sucesso.")
    return redirect("ordens_servico")


def listar_tecnicos(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    tecnicos = owned_queryset(Tecnico.objects, request.user).order_by("name")
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
        form = TecnicoForm(request.POST, user=request.user)
        if form.is_valid():
            tecnico = form.save()
            messages.success(request, f"Equipe '{tecnico.name}' cadastrada com sucesso.")
            return redirect("tecnicos")
    else:
        form = TecnicoForm(initial={"ativo": True}, user=request.user)

    return render(request, "service/tecnico_form.html", {"form": form, "is_edit": False})


def editar_tecnico(request: HttpRequest, pk: int) -> HttpResponse:
    tecnico = get_object_or_404(owned_queryset(Tecnico.objects, request.user), pk=pk)
    if request.method == "POST":
        form = TecnicoForm(request.POST, instance=tecnico, user=request.user)
        if form.is_valid():
            tecnico = form.save()
            messages.success(request, f"Equipe '{tecnico.name}' atualizada com sucesso.")
            return redirect("tecnicos")
    else:
        form = TecnicoForm(instance=tecnico, user=request.user)

    return render(request, "service/tecnico_form.html", {"form": form, "tecnico": tecnico, "is_edit": True})
