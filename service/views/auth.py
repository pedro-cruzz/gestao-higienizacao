from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy

from service.access import has_service_access, is_admin_user, is_team_user
from service.views.comum import inicio as dashboard_view


class ServiceLoginView(LoginView):
    template_name = "service/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if is_team_user(user) and not is_admin_user(user):
            return reverse_lazy("agenda")
        return reverse_lazy("inicio")

    def form_valid(self, form):
        user = form.get_user()
        if not has_service_access(user):
            form.add_error(None, "Seu usuario ainda nao tem perfil de acesso no HigiFlow.")
            return self.form_invalid(form)
        return super().form_valid(form)


@login_required
def painel_inicial(request: HttpRequest) -> HttpResponse:
    if is_admin_user(request.user):
        return dashboard_view(request)
    if is_team_user(request.user):
        return redirect("agenda")
    raise PermissionDenied("Seu usuario nao tem permissao para acessar esta area.")


@login_required
def sair(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.success(request, "Voce saiu do HigiFlow com seguranca.")
    return redirect("login")
