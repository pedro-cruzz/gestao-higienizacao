from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from service.forms import ProdutoCatalogoForm
from service.models import CategoriaCatalogo, Service_catalog
from service.ownership import owned_queryset, set_owner


def _deletar_imagem_catalogo(imagem) -> None:
    if not imagem:
        return

    nome = imagem.name
    if nome:
        imagem.storage.delete(nome)


def novo_produto(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ProdutoCatalogoForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            produto = form.save(commit=False)
            set_owner(produto, request.user)
            produto.save()
            form.save_m2m()
            messages.success(request, f"Item '{produto.name}' cadastrado no catálogo com sucesso.")
            return redirect("catalogo")
    else:
        form = ProdutoCatalogoForm(user=request.user)

    if request.method == "GET" and not owned_queryset(CategoriaCatalogo.objects, request.user).exists():
        messages.info(request, "Cadastre uma categoria antes de adicionar itens ao catálogo.")

    context = {
        "form": form,
        "ultimos_produtos": owned_queryset(Service_catalog.objects, request.user).order_by("-created_at", "-id")[:5],
        "total_categorias": owned_queryset(CategoriaCatalogo.objects, request.user).count(),
        "is_edit": False,
    }
    return render(request, "service/produto_form.html", context)


def editar_produto(request: HttpRequest, pk: int) -> HttpResponse:
    produto = get_object_or_404(owned_queryset(Service_catalog.objects, request.user), pk=pk)
    imagem_anterior = produto.imagem.name if produto.imagem else ""

    if request.method == "POST":
        form = ProdutoCatalogoForm(request.POST, request.FILES, instance=produto, user=request.user)
        if form.is_valid():
            produto = form.save()
            if imagem_anterior and produto.imagem.name != imagem_anterior:
                produto.imagem.storage.delete(imagem_anterior)
            messages.success(request, f"Item '{produto.name}' atualizado com sucesso.")
            return redirect("catalogo")
    else:
        form = ProdutoCatalogoForm(instance=produto, user=request.user)

    context = {
        "form": form,
        "produto": produto,
        "ultimos_produtos": owned_queryset(Service_catalog.objects, request.user).exclude(pk=pk).order_by("-created_at", "-id")[:5],
        "total_categorias": owned_queryset(CategoriaCatalogo.objects, request.user).count(),
        "is_edit": True,
    }
    return render(request, "service/produto_form.html", context)


def deletar_produto(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("catalogo")

    produto = get_object_or_404(owned_queryset(Service_catalog.objects, request.user), pk=pk)
    nome = produto.name
    imagem = produto.imagem
    produto.delete()
    _deletar_imagem_catalogo(imagem)

    messages.success(request, f"Item '{nome}' excluído do catálogo com sucesso.")
    return redirect("catalogo")
