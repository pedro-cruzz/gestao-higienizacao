from collections.abc import Callable
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse


ADMIN_GROUP = "Administradores"
TEAM_GROUP = "Equipe"


def is_admin_user(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.is_staff or user.groups.filter(name=ADMIN_GROUP).exists()


def is_team_user(user) -> bool:
    if not user.is_authenticated:
        return False
    return is_admin_user(user) or user.groups.filter(name=TEAM_GROUP).exists()


def has_service_access(user) -> bool:
    return is_admin_user(user) or is_team_user(user)


def _role_required(test_func: Callable) -> Callable:
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        @login_required
        def wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            if test_func(request.user):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("Seu usuario nao tem permissao para acessar esta area.")

        return wrapped

    return decorator


admin_required = _role_required(is_admin_user)
team_required = _role_required(is_team_user)
