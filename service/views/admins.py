from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from service.access import ADMIN_GROUP, DEV_GROUP, is_dev_user
from service.forms import AdminUserForm


def _usuarios_de_acesso():
    return get_user_model().objects.filter(Q(groups__name__in=[DEV_GROUP, ADMIN_GROUP]) | Q(is_superuser=True))


def _usuario_e_dev(user) -> bool:
    return user.is_superuser or user.groups.filter(name=DEV_GROUP).exists()


def _perfil_label(user) -> str:
    if _usuario_e_dev(user):
        return "Dev"
    return "Admin"


def listar_admins(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    admins = _usuarios_de_acesso().order_by("first_name", "username").distinct()
    if busca:
        admins = admins.filter(
            Q(first_name__icontains=busca)
            | Q(last_name__icontains=busca)
            | Q(username__icontains=busca)
            | Q(email__icontains=busca)
        )

    admins = list(admins)
    for admin in admins:
        admin.perfil_label = _perfil_label(admin)

    context = {
        "admins": admins,
        "busca": busca,
        "total_admins": len(admins),
    }
    return render(request, "service/admins.html", context)


def novo_admin(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AdminUserForm(request.POST, actor=request.user)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Usuário '{user.get_full_name() or user.username}' cadastrado com sucesso.")
            return redirect("admins")
    else:
        form = AdminUserForm(initial={"is_active": True, "perfil": ADMIN_GROUP}, actor=request.user)

    return render(request, "service/admin_form.html", {"form": form, "is_edit": False})


def editar_admin(request: HttpRequest, pk: int) -> HttpResponse:
    user = get_object_or_404(_usuarios_de_acesso().distinct(), pk=pk)
    if request.method == "POST":
        form = AdminUserForm(request.POST, instance=user, actor=request.user)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Usuário '{user.get_full_name() or user.username}' atualizado com sucesso.")
            return redirect("admins")
    else:
        form = AdminUserForm(instance=user, actor=request.user)

    return render(request, "service/admin_form.html", {"form": form, "admin_user": user, "is_edit": True})


def deletar_admin(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("admins")

    user = get_object_or_404(_usuarios_de_acesso().distinct(), pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, "Você não pode excluir o próprio usuário.")
        return redirect("admins")

    if _usuario_e_dev(user) and not is_dev_user(request.user):
        raise PermissionDenied("Somente um perfil dev pode excluir outro dev.")

    nome = user.get_full_name() or user.username
    user.delete()
    messages.success(request, f"Usuário '{nome}' excluído com sucesso.")
    return redirect("admins")
