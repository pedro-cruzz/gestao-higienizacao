from datetime import datetime, time, timedelta

from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from service.models import Cliente, Orcamento, OrdemServico, Service_catalog


def _month_boundaries() -> tuple[datetime, datetime]:
    current_month = timezone.localdate().replace(day=1)
    previous_month = (current_month - timedelta(days=1)).replace(day=1)
    active_timezone = timezone.get_current_timezone()

    previous_start = timezone.make_aware(
        datetime.combine(previous_month, time.min),
        active_timezone,
    )
    current_start = timezone.make_aware(
        datetime.combine(current_month, time.min),
        active_timezone,
    )
    return previous_start, current_start


def _sum_orcamentos(queryset) -> float:
    return queryset.aggregate(total=Sum("valor"))["total"] or 0


def _conversion_rate(queryset) -> int:
    total = queryset.count()
    if not total:
        return 0

    aprovados = queryset.filter(aprovado=True).count()
    return round((aprovados / total) * 100)


def _percent_delta(current: float, previous: float) -> int:
    if not previous:
        return 100 if current else 0

    return round(((current - previous) / previous) * 100)


def _signed_percent(current: float, previous: float) -> str:
    delta = _percent_delta(current, previous)
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta}%"


def _signed_count(current: int, previous: int) -> str:
    delta = current - previous
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta}"


def _lead_status_class(status: str) -> str:
    return {
        Cliente.Status.NOVO: "status-blue",
        Cliente.Status.CONTATADO: "status-yellow",
        Cliente.Status.AGUARDANDO: "status-gray",
        Cliente.Status.CONVERTIDO: "status-soft-blue",
    }.get(status, "status-gray")


def _dashboard_leads():
    leads = Cliente.objects.order_by("-created_at", "-id")[:3]
    return [
        {
            "name": lead.name,
            "contato": lead.telefone or lead.email,
            "status_label": lead.get_status_display(),
            "status_class": _lead_status_class(lead.status),
            "created_at": lead.created_at,
        }
        for lead in leads
    ]


def _dashboard_ordens():
    ordens = OrdemServico.objects.select_related("tecnico").order_by("-created_at", "-id")[:3]
    dashboard_ordens = []

    for ordem in ordens:
        dashboard_ordens.append(
            {
                "name": ordem.titulo,
                "servico": ordem.responsavel_nome,
                "status_label": ordem.get_status_display(),
                "status_class": {
                    OrdemServico.Status.AGENDADA: "status-blue",
                    OrdemServico.Status.EM_ANDAMENTO: "status-purple",
                    OrdemServico.Status.CONCLUIDA: "status-soft-blue",
                    OrdemServico.Status.CANCELADA: "status-red",
                }.get(ordem.status, "status-gray"),
                "valor": ordem.valor,
            }
        )

    if not dashboard_ordens:
        orcamentos = Orcamento.objects.prefetch_related("itens").order_by("-created_at", "-id")[:3]
        for orcamento in orcamentos:
            primeiro_item = next(iter(orcamento.itens.all()), None)
            dashboard_ordens.append(
                {
                    "name": orcamento.name,
                    "servico": primeiro_item.name if primeiro_item else "Servico cadastrado",
                    "status_label": "Concluida" if orcamento.aprovado else "Em execucao",
                    "status_class": "status-soft-blue" if orcamento.aprovado else "status-purple",
                    "valor": orcamento.valor,
                }
            )

    return dashboard_ordens


def inicio(request: HttpRequest) -> HttpResponse:
    previous_start, current_start = _month_boundaries()

    leads = Cliente.objects.all()
    orcamentos = Orcamento.objects.all()
    orcamentos_aprovados = orcamentos.filter(aprovado=True)
    servicos_catalogo = Service_catalog.objects.all()

    leads_mes_atual = leads.filter(created_at__gte=current_start).count()
    leads_mes_anterior = leads.filter(
        created_at__gte=previous_start,
        created_at__lt=current_start,
    ).count()
    aprovados_mes_atual = orcamentos_aprovados.filter(created_at__gte=current_start).count()
    aprovados_mes_anterior = orcamentos_aprovados.filter(
        created_at__gte=previous_start,
        created_at__lt=current_start,
    ).count()
    faturamento_mes_atual = _sum_orcamentos(orcamentos_aprovados.filter(created_at__gte=current_start))
    faturamento_mes_anterior = _sum_orcamentos(
        orcamentos_aprovados.filter(
            created_at__gte=previous_start,
            created_at__lt=current_start,
        )
    )

    context = {
        "total_leads": leads.count(),
        "total_leads_delta": _signed_percent(leads_mes_atual, leads_mes_anterior),
        "taxa_conversao": _conversion_rate(orcamentos),
        "taxa_conversao_delta": _signed_percent(
            _conversion_rate(orcamentos.filter(created_at__gte=current_start)),
            _conversion_rate(
                orcamentos.filter(
                    created_at__gte=previous_start,
                    created_at__lt=current_start,
                )
            ),
        ),
        "servicos_ativos": orcamentos_aprovados.count(),
        "servicos_ativos_delta": _signed_count(aprovados_mes_atual, aprovados_mes_anterior),
        "servicos_catalogo": servicos_catalogo.count(),
        "faturamento": _sum_orcamentos(orcamentos_aprovados),
        "faturamento_delta": _signed_percent(faturamento_mes_atual, faturamento_mes_anterior),
        "leads_recentes": _dashboard_leads(),
        "ordens_recentes": _dashboard_ordens(),
    }
    return render(request, "service/inicio.html", context)


def teste(request: HttpRequest) -> HttpResponse:
    return render(request, "teste.html")
