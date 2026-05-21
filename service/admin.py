from django.contrib import admin

from service.models import CategoriaCatalogo, Cliente, Lead, Orcamento, OrdemServico, Service_catalog, Tecnico


@admin.register(CategoriaCatalogo)
class CategoriaCatalogoAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name", "descricao")


@admin.register(Service_catalog)
class ServiceCatalogAdmin(admin.ModelAdmin):
    list_display = ("name", "categoria", "tipo", "valor", "imagem")
    list_filter = ("categoria",)
    search_fields = ("name", "tipo", "categoria__name")


@admin.register(Orcamento)
class OrcamentoAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "valor", "quantidade", "aprovado", "cliente")
    list_filter = ("aprovado",)
    search_fields = ("name", "email")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "telefone")
    search_fields = ("name", "email")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "telefone", "status", "origem", "cliente")
    list_filter = ("status", "origem")
    search_fields = ("name", "email", "telefone")


@admin.register(Tecnico)
class TecnicoAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "telefone", "especialidade", "ativo")
    list_filter = ("ativo",)
    search_fields = ("name", "email", "telefone", "especialidade")


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ("id", "titulo", "cliente", "tecnico", "data_agendada", "hora_inicio", "status")
    list_filter = ("status", "data_agendada", "administrador_executa")
    search_fields = ("titulo", "cliente__name", "tecnico__name", "orcamento__name")
