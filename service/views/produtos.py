from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from service.forms import ProdutoCatalogoForm
from service.models import CategoriaCatalogo, Service_catalog


def novo_produto(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProdutoCatalogoForm(request.POST, request.FILES)
        if form.is_valid():
            produto = form.save()
            messages.success(request, f"Item '{produto.name}' cadastrado no catalogo com sucesso.")
            return redirect("catalogo")
    else:
        form = ProdutoCatalogoForm()

    if request.method == "GET" and not CategoriaCatalogo.objects.exists():
        messages.info(request, "Cadastre uma categoria antes de adicionar itens ao catalogo.")

    context = {
        "form": form,
        "ultimos_produtos": Service_catalog.objects.order_by("-created_at", "-id")[:5],
        "total_categorias": CategoriaCatalogo.objects.count(),
        "is_edit": False,
    }
    return render(request, "service/produto_form.html", context)


def editar_produto(request: HttpRequest, pk: int) -> HttpResponse:
    produto = get_object_or_404(Service_catalog, pk=pk)

    if request.method == "POST":
        form = ProdutoCatalogoForm(request.POST, request.FILES, instance=produto)
        if form.is_valid():
            produto = form.save()
            messages.success(request, f"Item '{produto.name}' atualizado com sucesso.")
            return redirect("catalogo")
    else:
        form = ProdutoCatalogoForm(instance=produto)

    context = {
        "form": form,
        "produto": produto,
        "ultimos_produtos": Service_catalog.objects.exclude(pk=pk).order_by("-created_at", "-id")[:5],
        "total_categorias": CategoriaCatalogo.objects.count(),
        "is_edit": True,
    }
    return render(request, "service/produto_form.html", context)


def deletar_produto(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("catalogo")

    produto = get_object_or_404(Service_catalog, pk=pk)
    nome = produto.name
    produto.delete()

    messages.success(request, f"Item '{nome}' excluido do catalogo com sucesso.")
    return redirect("catalogo")
