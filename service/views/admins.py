from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from service.access import ADMIN_GROUP
from service.forms import AdminUserForm


def listar_admins(request: HttpRequest) -> HttpResponse:
    busca = request.GET.get("q", "").strip()
    admins = (
        get_user_model()
        .objects.filter(groups__name=ADMIN_GROUP)
        .order_by("first_name", "username")
        .distinct()
    )
    if busca:
        admins = admins.filter(
            Q(first_name__icontains=busca)
            | Q(last_name__icontains=busca)
            | Q(username__icontains=busca)
            | Q(email__icontains=busca)
        )

    context = {
        "admins": admins,
        "busca": busca,
        "total_admins": admins.count(),
    }
    return render(request, "service/admins.html", context)


def novo_admin(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = AdminUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Admin '{user.get_full_name() or user.username}' cadastrado com sucesso.")
            return redirect("admins")
    else:
        form = AdminUserForm(initial={"is_active": True})

    return render(request, "service/admin_form.html", {"form": form, "is_edit": False})


def editar_admin(request: HttpRequest, pk: int) -> HttpResponse:
    user = get_object_or_404(get_user_model(), pk=pk, groups__name=ADMIN_GROUP)
    if request.method == "POST":
        form = AdminUserForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Admin '{user.get_full_name() or user.username}' atualizado com sucesso.")
            return redirect("admins")
    else:
        form = AdminUserForm(instance=user)

    return render(request, "service/admin_form.html", {"form": form, "admin_user": user, "is_edit": True})
