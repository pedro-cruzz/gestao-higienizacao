from django.urls import reverse
from django.utils import timezone

from service.access import is_admin_user, is_dev_user, is_team_user
from service.models import OrdemServico
from service.ownership import owned_queryset


def _cliente_ordem(ordem: OrdemServico) -> str:
    if ordem.cliente_id:
        return ordem.cliente.name
    if ordem.orcamento_id:
        return ordem.orcamento.name
    return "Cliente nao informado"


def _ordens_notificaveis(user):
    ordens = OrdemServico.objects.select_related("cliente", "orcamento", "tecnico")
    if is_admin_user(user):
        return owned_queryset(ordens, user)
    if is_team_user(user):
        return ordens.filter(tecnico__user=user)
    return ordens.none()


def _notification_item(ordem: OrdemServico, title: str, tone: str) -> dict:
    horario = ordem.hora_inicio.strftime("%H:%M")
    return {
        "title": title,
        "text": f"OS #{ordem.pk} - {ordem.titulo}",
        "meta": f"{horario} - {_cliente_ordem(ordem)}",
        "url": reverse("os_detalhe", args=[ordem.pk]),
        "tone": tone,
    }


def _service_notifications(request, user) -> dict:
    if not user or not user.is_authenticated:
        return {
            "hf_notifications": [],
            "hf_notification_count": 0,
            "hf_today_services_count": 0,
        }

    hoje = timezone.localdate()
    status_ativos = [OrdemServico.Status.AGENDADA, OrdemServico.Status.EM_ANDAMENTO]
    ordens = _ordens_notificaveis(user).filter(status__in=status_ativos)
    ordens_hoje = list(ordens.filter(data_agendada=hoje).order_by("hora_inicio", "id")[:5])
    notificacoes = [
        _notification_item(ordem, "Servico de hoje", "today")
        for ordem in ordens_hoje
    ]

    if is_team_user(user) and not is_admin_user(user):
        ordens_designadas = list(
            ordens.filter(data_agendada__gt=hoje).order_by("data_agendada", "hora_inicio", "id")[:5]
        )
        for ordem in ordens_designadas:
            data = ordem.data_agendada.strftime("%d/%m")
            notificacoes.append(_notification_item(ordem, f"OS designada para {data}", "assigned"))

    return {
        "hf_notifications": notificacoes[:8],
        "hf_notification_count": ordens.count(),
        "hf_today_services_count": len(ordens_hoje),
    }


def auth_roles(request):
    user = getattr(request, "user", None)
    context = {
        "hf_is_dev": is_dev_user(user) if user else False,
        "hf_is_admin": is_admin_user(user) if user else False,
        "hf_is_team": is_team_user(user) if user else False,
    }
    context.update(_service_notifications(request, user))
    return context
