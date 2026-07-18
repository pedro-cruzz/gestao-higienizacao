from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hf_profile",
    )
    foto = models.ImageField(upload_to="perfis/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Perfil de {self.user.get_username()}"


class CategoriaCatalogo(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="categorias_catalogo",
    )
    name = models.CharField(max_length=100)
    descricao = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_categoria_por_owner"),
        ]

    def __str__(self):
        return self.name


class Service_catalog(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="produtos_catalogo",
    )
    name = models.CharField(max_length=100, null=False)
    tempo = models.CharField(max_length=100, null=True)
    tipo = models.CharField(max_length=100, null=True)
    categoria = models.ForeignKey(
        CategoriaCatalogo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens",
    )
    id = models.AutoField(primary_key=True)
    valor = models.FloatField(null=False)
    imagem = models.ImageField(upload_to="catalogo/", null=True, blank=True)
    descricao = models.TextField(null=True)
    formato = models.CharField(max_length=100, null=True)
    tamanho = models.CharField(max_length=100, null=True)
    largura = models.CharField(max_length=100, null=True)
    comprimento = models.CharField(max_length=100, null=True)
    tecido = models.CharField(max_length=100, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_catalogo_por_owner"),
        ]

    def __str__(self):
        return self.name

    @property
    def categoria_nome(self):
        return self.categoria.name if self.categoria else self.tipo


class Lead(models.Model):
    class Status(models.TextChoices):
        NOVO = "novo", "Novo"
        CONTATADO = "contatado", "Contatado"
        AGUARDANDO = "aguardando", "Aguardando"
        CONVERTIDO = "convertido", "Convertido"

    class Origem(models.TextChoices):
        MANUAL = "manual", "Manual"
        WHATSAPP = "whatsapp", "WhatsApp"
        INSTAGRAM = "instagram", "Instagram"
        INDICACAO = "indicacao", "Indicação"
        SITE = "site", "Site"
        OUTRO = "outro", "Outro"

    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    name = models.CharField(max_length=100, null=False)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    cep = models.CharField(max_length=9, null=True, blank=True)
    logradouro = models.CharField(max_length=120, null=True, blank=True)
    numero = models.CharField(max_length=20, null=True, blank=True)
    complemento = models.CharField(max_length=120, null=True, blank=True)
    bairro = models.CharField(max_length=120, null=True, blank=True)
    cidade = models.CharField(max_length=120, null=True, blank=True)
    uf = models.CharField(max_length=2, null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOVO,
    )
    origem = models.CharField(
        max_length=20,
        choices=Origem.choices,
        default=Origem.MANUAL,
    )
    cliente = models.ForeignKey(
        "Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_origem",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name


class Orcamento(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orcamentos",
    )
    name = models.CharField(max_length=100, null=False)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    cep = models.CharField(max_length=9, null=True, blank=True)
    logradouro = models.CharField(max_length=120, null=True, blank=True)
    numero = models.CharField(max_length=20, null=True, blank=True)
    complemento = models.CharField(max_length=120, null=True, blank=True)
    bairro = models.CharField(max_length=120, null=True, blank=True)
    cidade = models.CharField(max_length=120, null=True, blank=True)
    uf = models.CharField(max_length=2, null=True, blank=True)
    valor = models.FloatField(null=False)
    descricao = models.TextField(null=True)
    pdf_frase_cliente = models.TextField(null=True, blank=True)
    pdf_logo = models.ImageField(upload_to="orcamentos/logos/", null=True, blank=True)
    quantidade = models.IntegerField(null=False)
    itens = models.ManyToManyField(Service_catalog, related_name="orcamento_items")
    adicionais = models.ManyToManyField("AdicionalOrcamento", blank=True, related_name="orcamentos")
    multiplicadores = models.ManyToManyField("MultiplicadorOrcamento", blank=True, related_name="orcamentos")
    aprovado = models.BooleanField(default=False)
    cliente = models.ForeignKey(
        "Cliente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orcamentos",
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orcamentos",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_orcamento"

    def __str__(self):
        return self.name


class AdicionalOrcamento(models.Model):
    class TipoValor(models.TextChoices):
        FIXO = "fixo", "Valor fixo"
        PERCENTUAL = "percentual", "Percentual"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adicionais_orcamento",
    )
    name = models.CharField(max_length=100)
    descricao = models.CharField(max_length=160, blank=True, default="")
    categoria = models.CharField(max_length=80, blank=True, default="")
    tipo_valor = models.CharField(max_length=20, choices=TipoValor.choices, default=TipoValor.FIXO, blank=True)
    valor = models.FloatField(default=0)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_adicional_orcamento_por_owner"),
        ]

    def __str__(self):
        return self.name


class MultiplicadorOrcamento(models.Model):
    class Aplicacao(models.TextChoices):
        TOTAL = "total", "Total"
        SERVICOS = "servicos", "Serviços"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="multiplicadores_orcamento",
    )
    name = models.CharField(max_length=100)
    descricao = models.CharField(max_length=160, blank=True, default="")
    aplica_em = models.CharField(max_length=20, choices=Aplicacao.choices, default=Aplicacao.TOTAL, blank=True)
    fator = models.FloatField(default=1)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_multiplicador_orcamento_por_owner"),
        ]

    def __str__(self):
        return self.name


class Cliente(models.Model):
    class TipoCliente(models.TextChoices):
        RESIDENCIAL = "residencial", "Residencial"
        EMPRESARIAL = "empresarial", "Empresarial"

    class Status(models.TextChoices):
        NOVO = "novo", "Novo"
        CONTATADO = "contatado", "Contatado"
        AGUARDANDO = "aguardando", "Aguardando"
        CONVERTIDO = "convertido", "Convertido"

    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clientes",
    )
    tipo_cliente = models.CharField(
        max_length=20,
        choices=TipoCliente.choices,
        default=TipoCliente.RESIDENCIAL,
    )
    name = models.CharField(max_length=100, null=False)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    cnpj = models.CharField(max_length=18, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    cep = models.CharField(max_length=9, null=True, blank=True)
    logradouro = models.CharField(max_length=120, null=True, blank=True)
    numero = models.CharField(max_length=20, null=True, blank=True)
    complemento = models.CharField(max_length=120, null=True, blank=True)
    bairro = models.CharField(max_length=120, null=True, blank=True)
    cidade = models.CharField(max_length=120, null=True, blank=True)
    uf = models.CharField(max_length=2, null=True, blank=True)
    observacoes = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOVO,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Tecnico(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tecnicos",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tecnico_profile",
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    especialidade = models.CharField(max_length=120, null=True, blank=True)
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrdemServico(models.Model):
    class Status(models.TextChoices):
        AGENDADA = "agendada", "Agendada"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        CONCLUIDA = "concluida", "Concluída"
        CANCELADA = "cancelada", "Cancelada"

    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordens_servico",
    )
    orcamento = models.OneToOneField(
        Orcamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordem_servico",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordens_servico",
    )
    tecnico = models.ForeignKey(
        Tecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordens_servico",
    )
    administrador_executa = models.BooleanField(
        default=False,
        help_text="Marque quando o administrador ou dono executar o serviço.",
    )
    titulo = models.CharField(max_length=140)
    descricao = models.TextField(null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    data_agendada = models.DateField()
    hora_inicio = models.TimeField()
    hora_fim = models.TimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AGENDADA,
    )
    valor = models.FloatField(default=0)
    instrucoes = models.TextField(null=True, blank=True)
    checklist = models.TextField(null=True, blank=True)
    observacoes_execucao = models.TextField(null=True, blank=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data_agendada", "hora_inicio", "id"]

    def __str__(self):
        return f"OS #{self.pk} - {self.titulo}"

    @property
    def responsavel_nome(self):
        if self.administrador_executa:
            return "Administrador / dono"
        return self.tecnico.name if self.tecnico else "Sem responsável"
