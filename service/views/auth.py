from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from service.access import has_service_access, is_admin_user, is_dev_user, is_team_user
from service.forms import PerfilUsuarioForm, SegurancaUsuarioForm
from service.views.comum import inicio as dashboard_view


class ServiceLoginView(LoginView):
    template_name = "service/login.html"
    redirect_authenticated_user = False

    def get_success_url(self):
        user = self.request.user
        if is_team_user(user) and not is_admin_user(user):
            return reverse_lazy("agenda")
        return reverse_lazy("inicio")

    def form_valid(self, form):
        user = form.get_user()
        if not has_service_access(user):
            form.add_error(None, "Seu usuário ainda não tem perfil de acesso no HigiFlow.")
            return self.form_invalid(form)
        return super().form_valid(form)


@login_required
def painel_inicial(request: HttpRequest) -> HttpResponse:
    if is_admin_user(request.user):
        return dashboard_view(request)
    if is_team_user(request.user):
        return redirect("agenda")
    raise PermissionDenied("Seu usuário não tem permissão para acessar esta área.")


@login_required
def sair(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.success(request, "Você saiu do HigiFlow com segurança.")
    return redirect("login")


@login_required
def perfil_usuario(request: HttpRequest) -> HttpResponse:
    if not is_admin_user(request.user):
        raise PermissionDenied("Seu usuário não tem permissão para acessar esta área.")

    active_tab = request.GET.get("tab")
    if active_tab not in {"perfil", "seguranca"}:
        active_tab = "perfil"

    if request.method == "POST":
        form_kind = request.POST.get("form_kind")
        if form_kind == "security":
            active_tab = "seguranca"
            profile_form = PerfilUsuarioForm(instance=request.user)
            security_form = SegurancaUsuarioForm(request.POST, user=request.user)
            if security_form.is_valid():
                user = security_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Senha atualizada com sucesso.")
                return redirect(f"{reverse('perfil')}?tab=seguranca")
        else:
            active_tab = "perfil"
            profile_form = PerfilUsuarioForm(request.POST, request.FILES, instance=request.user)
            security_form = SegurancaUsuarioForm(user=request.user)
            if profile_form.is_valid():
                user = profile_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Perfil atualizado com sucesso.")
                return redirect("perfil")
    else:
        profile_form = PerfilUsuarioForm(instance=request.user)
        security_form = SegurancaUsuarioForm(user=request.user)

    tecnico = getattr(request.user, "tecnico_profile", None)
    full_name = request.user.get_full_name().strip()
    display_name = full_name or request.user.username
    initials_source = full_name.split() or [request.user.username]
    initials = "".join(part[0] for part in initials_source[:2] if part).upper() or "HF"
    role_label = "Desenvolvedor" if is_dev_user(request.user) else "Administrador"
    access_text = "Acesso de desenvolvedor" if is_dev_user(request.user) else "Acesso administrativo"

    return render(
        request,
        "service/perfil.html",
        {
            "form": profile_form,
            "profile_form": profile_form,
            "security_form": security_form,
            "active_profile_tab": active_tab,
            "profile_display_name": display_name,
            "profile_initials": initials,
            "profile_role_label": role_label,
            "profile_phone": getattr(tecnico, "telefone", None) or "Não informado",
            "profile_access_text": access_text,
        },
    )
