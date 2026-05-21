from django.conf import settings
from django.db import models


class CategoriaCatalogo(models.Model):
    name = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Service_catalog(models.Model):
    name = models.CharField(max_length=100, unique=True, null=False)
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
        INDICACAO = "indicacao", "Indicacao"
        SITE = "site", "Site"
        OUTRO = "outro", "Outro"

    id = models.AutoField(primary_key=True)
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
    cliente = models.OneToOneField(
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
    quantidade = models.IntegerField(null=False)
    itens = models.ManyToManyField(Service_catalog, related_name="orcamento_items")
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


class Cliente(models.Model):
    class Status(models.TextChoices):
        NOVO = "novo", "Novo"
        CONTATADO = "contatado", "Contatado"
        AGUARDANDO = "aguardando", "Aguardando"
        CONVERTIDO = "convertido", "Convertido"

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, null=False)
    email = models.EmailField(null=False)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    endereco = models.CharField(max_length=255, null=True, blank=True)
    cep = models.CharField(max_length=9, null=True, blank=True)
    logradouro = models.CharField(max_length=120, null=True, blank=True)
    numero = models.CharField(max_length=20, null=True, blank=True)
    complemento = models.CharField(max_length=120, null=True, blank=True)
    bairro = models.CharField(max_length=120, null=True, blank=True)
    cidade = models.CharField(max_length=120, null=True, blank=True)
    uf = models.CharField(max_length=2, null=True, blank=True)
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
        CONCLUIDA = "concluida", "Concluida"
        CANCELADA = "cancelada", "Cancelada"

    id = models.AutoField(primary_key=True)
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
        help_text="Marque quando o administrador ou dono executar o servico.",
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
        return self.tecnico.name if self.tecnico else "Sem responsavel"
