from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from service.models import Cliente, Lead, Orcamento, OrdemServico, Service_catalog, Tecnico


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
        Lead.Status.NOVO: "status-blue",
        Lead.Status.CONTATADO: "status-yellow",
        Lead.Status.AGUARDANDO: "status-gray",
        Lead.Status.CONVERTIDO: "status-soft-blue",
    }.get(status, "status-gray")


def _dashboard_leads():
    leads = Lead.objects.order_by("-created_at", "-id")[:3]
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

    leads = Lead.objects.all()
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


def agenda(request: HttpRequest) -> HttpResponse:
    equipes = [
        {"key": "a", "nome": "Equipe A"},
        {"key": "b", "nome": "Equipe B"},
        {"key": "c", "nome": "Equipe C"},
    ]
    dias = [
        {"key": "segunda", "nome": "Segunda", "numero": "28"},
        {"key": "terca", "nome": "Terça", "numero": "29"},
        {"key": "quarta", "nome": "Quarta", "numero": "30"},
        {"key": "quinta", "nome": "Quinta", "numero": "01"},
        {"key": "sexta", "nome": "Sexta", "numero": "02"},
        {"key": "sabado", "nome": "Sábado", "numero": "03"},
        {"key": "domingo", "nome": "Domingo", "numero": "04"},
    ]
    horarios = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
    eventos = [
        {
            "dia": "quinta",
            "horario": "08:00",
            "equipe": "c",
            "cliente": "Ana Costa",
            "servico": "Impermeabilização",
            "endereco": "Av. D, 321",
        },
        {
            "dia": "terca",
            "horario": "09:00",
            "equipe": "a",
            "cliente": "Pedro Lima",
            "servico": "Limpeza de Sofá",
            "endereco": "Rua A, 123",
        },
        {
            "dia": "quarta",
            "horario": "10:00",
            "equipe": "b",
            "cliente": "João Santos",
            "servico": "Limpeza Colchão",
            "endereco": "Rua C, 789",
        },
        {
            "dia": "terca",
            "horario": "14:00",
            "equipe": "a",
            "cliente": "Maria Silva",
            "servico": "Higienização Tapete",
            "endereco": "Av. B, 456",
            "tamanho": "grande",
        },
    ]

    linhas = []
    for horario in horarios:
        celulas = []
        for dia in dias:
            celulas.append(
                {
                    "dia": dia["key"],
                    "eventos": [
                        evento
                        for evento in eventos
                        if evento["dia"] == dia["key"] and evento["horario"] == horario
                    ],
                }
            )
        linhas.append({"horario": horario, "celulas": celulas})

    context = {
        "equipes": equipes,
        "dias": dias,
        "linhas_agenda": linhas,
        "periodo_agenda": "28 Abr - 04 Mai, 2026",
    }
    return render(request, "service/agenda.html", context)


def configuracoes(request: HttpRequest) -> HttpResponse:
    servicos = Service_catalog.objects.select_related("categoria").order_by("name")
    usuarios = get_user_model().objects.order_by("first_name", "username")[:6]
    tecnicos = Tecnico.objects.select_related("user").order_by("name")[:6]

    context = {
        "servicos_config": servicos,
        "usuarios_config": usuarios,
        "tecnicos_config": tecnicos,
        "adicionais_config": [
            {"nome": "Manchas dificeis", "valor": 80},
            {"nome": "Urina de animais", "valor": 120},
            {"nome": "Mofo ou bolor", "valor": 100},
        ],
        "tecidos_config": [
            {"nome": "Padrao", "multiplicador": "1.0"},
            {"nome": "Nobuck/Camurca", "multiplicador": "1.2"},
            {"nome": "Seda/Delicado", "multiplicador": "1.5"},
        ],
        "tamanhos_config": [
            {"nome": "Pequeno", "multiplicador": "1.0"},
            {"nome": "Medio", "multiplicador": "1.3"},
            {"nome": "Grande", "multiplicador": "1.6"},
            {"nome": "Extra Grande", "multiplicador": "2.0"},
        ],
    }
    return render(request, "service/configuracoes.html", context)


def login(request: HttpRequest) -> HttpResponse:
    return render(request, "service/login.html")


def teste(request: HttpRequest) -> HttpResponse:
    return render(request, "teste.html")
