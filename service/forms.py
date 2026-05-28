from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q

from service.access import ADMIN_GROUP, TEAM_GROUP
from service.models import CategoriaCatalogo, Cliente, Lead, Orcamento, OrdemServico, Service_catalog, Tecnico


def normalizar_email(value: str | None) -> str:
    return (value or "").strip().lower()


def normalizar_telefone(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value:
        return ""

    digits = "".join(char for char in raw_value if char.isdigit())
    if digits.startswith("55") and len(digits) in [12, 13]:
        digits = digits[2:]

    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"

    raise forms.ValidationError("Informe um telefone com DDD no formato (11) 99999-9999.")


class CategoriaCatalogoForm(forms.ModelForm):
    class Meta:
        model = CategoriaCatalogo
        fields = ["name", "descricao"]
        labels = {
            "name": "Nome da categoria",
            "descricao": "Descricao",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Sofas"}),
            "descricao": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Ex.: Itens de higienizacao para sofas, poltronas e chaises."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["descricao"].required = False
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class ProdutoCatalogoForm(forms.ModelForm):
    class Meta:
        model = Service_catalog
        fields = [
            "name",
            "categoria",
            "valor",
            "imagem",
            "descricao",
            "tempo",
            "formato",
            "tamanho",
            "largura",
            "comprimento",
            "tecido",
        ]
        labels = {
            "name": "Nome do servico ou item",
            "categoria": "Categoria",
            "valor": "Valor base",
            "imagem": "Imagem do item",
            "descricao": "Descricao",
            "tempo": "Tempo medio",
            "formato": "Formato",
            "tamanho": "Tamanho",
            "largura": "Largura",
            "comprimento": "Comprimento",
            "tecido": "Material ou tecido",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Sofa retratil 3 lugares"}),
            "categoria": forms.Select(),
            "valor": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "imagem": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "descricao": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Ex.: Higienizacao profunda com extratora e acabamento antiodor."}
            ),
            "tempo": forms.TextInput(attrs={"placeholder": "Ex.: 2 horas"}),
            "formato": forms.TextInput(attrs={"placeholder": "Ex.: Retratil, chaise, canto"}),
            "tamanho": forms.TextInput(attrs={"placeholder": "Ex.: 2 lugares, queen, 2x3 m"}),
            "largura": forms.TextInput(attrs={"placeholder": "Ex.: 180 cm"}),
            "comprimento": forms.TextInput(attrs={"placeholder": "Ex.: 220 cm"}),
            "tecido": forms.TextInput(attrs={"placeholder": "Ex.: Suede, linho, veludo"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in [
            "categoria",
            "imagem",
            "descricao",
            "tempo",
            "formato",
            "tamanho",
            "largura",
            "comprimento",
            "tecido",
        ]:
            self.fields[field_name].required = False

        for name, field in self.fields.items():
            widget = field.widget
            current_class = widget.attrs.get("class", "")
            base_class = "form-control"
            if name == "categoria":
                base_class = "form-select"
            widget.attrs["class"] = f"{current_class} {base_class}".strip()

    def save(self, commit=True):
        item = super().save(commit=False)
        item.tipo = item.categoria.name if item.categoria else None
        if commit:
            item.save()
            self.save_m2m()
        return item


class ClienteForm(forms.ModelForm):
    orcamento_origem = forms.ModelChoiceField(
        label="Puxar dados de um orcamento",
        queryset=Orcamento.objects.none(),
        required=False,
        empty_label="Preencher manualmente ou selecionar orcamento",
        widget=forms.Select(),
    )

    class Meta:
        model = Cliente
        fields = [
            "name",
            "email",
            "telefone",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "endereco",
            "status",
        ]
        labels = {
            "name": "Nome do cliente",
            "email": "Email",
            "telefone": "Telefone",
            "cep": "CEP",
            "logradouro": "Logradouro",
            "numero": "Numero",
            "complemento": "Complemento",
            "bairro": "Bairro",
            "cidade": "Cidade",
            "uf": "UF",
            "status": "Status",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Maria Souza"}),
            "email": forms.EmailInput(attrs={"placeholder": "cliente@empresa.com"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(11) 99999-9999"}),
            "cep": forms.TextInput(attrs={"placeholder": "00000-000", "autocomplete": "postal-code"}),
            "logradouro": forms.TextInput(attrs={"placeholder": "Rua, avenida ou travessa"}),
            "numero": forms.TextInput(attrs={"placeholder": "Numero"}),
            "complemento": forms.TextInput(attrs={"placeholder": "Apartamento, bloco, referencia"}),
            "bairro": forms.TextInput(attrs={"placeholder": "Bairro"}),
            "cidade": forms.TextInput(attrs={"placeholder": "Cidade"}),
            "uf": forms.TextInput(attrs={"placeholder": "SP"}),
            "endereco": forms.HiddenInput(),
            "status": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        if args and args[0] is not None:
            args = (self._data_com_orcamento(args[0]), *args[1:])
        elif kwargs.get("data") is not None:
            kwargs["data"] = self._data_com_orcamento(kwargs["data"])

        super().__init__(*args, **kwargs)
        self.fields["orcamento_origem"].queryset = Orcamento.objects.filter(cliente__isnull=True).order_by(
            "-created_at", "-id"
        )
        self.fields["orcamento_origem"].label_from_instance = self._orcamento_label
        self.fields["orcamento_origem"].widget.attrs["class"] = "form-select"
        for field_name in [
            "telefone",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "endereco",
        ]:
            self.fields[field_name].required = False

        for name, field in self.fields.items():
            if name == "status":
                field.widget.attrs["class"] = "form-select"
            elif name != "endereco":
                field.widget.attrs["class"] = "form-control text-uppercase" if name == "uf" else "form-control"

    @staticmethod
    def _orcamento_label(orcamento: Orcamento) -> str:
        contato = orcamento.email or orcamento.telefone or "sem contato"
        return f"#{orcamento.pk} - {orcamento.name} ({contato})"

    @staticmethod
    def _data_com_orcamento(data):
        mutable_data = data.copy()
        orcamento_id = mutable_data.get("orcamento_origem")
        if not orcamento_id:
            return mutable_data

        orcamento = Orcamento.objects.filter(pk=orcamento_id, cliente__isnull=True).first()
        if not orcamento:
            return mutable_data

        for field_name in [
            "name",
            "email",
            "telefone",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "endereco",
        ]:
            if not mutable_data.get(field_name):
                mutable_data[field_name] = getattr(orcamento, field_name, None) or ""

        if not mutable_data.get("status"):
            mutable_data["status"] = Cliente.Status.CONVERTIDO

        return mutable_data

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["email"] = normalizar_email(cleaned_data.get("email"))
        cleaned_data["telefone"] = normalizar_telefone(cleaned_data.get("telefone"))
        endereco = montar_endereco_limpo(cleaned_data)
        cleaned_data["uf"] = (cleaned_data.get("uf") or "").strip().upper()
        cleaned_data["endereco"] = endereco or (cleaned_data.get("endereco") or "").strip()
        return cleaned_data


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "name",
            "email",
            "telefone",
            "status",
            "origem",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "endereco",
        ]
        labels = {
            "name": "Nome do lead",
            "email": "Email",
            "telefone": "Telefone",
            "status": "Status",
            "origem": "Origem",
            "cep": "CEP",
            "logradouro": "Logradouro",
            "numero": "Numero",
            "complemento": "Complemento",
            "bairro": "Bairro",
            "cidade": "Cidade",
            "uf": "UF",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Maria Souza"}),
            "email": forms.EmailInput(attrs={"placeholder": "lead@empresa.com"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(11) 99999-9999"}),
            "status": forms.Select(),
            "origem": forms.Select(),
            "cep": forms.TextInput(attrs={"placeholder": "00000-000", "autocomplete": "postal-code"}),
            "logradouro": forms.TextInput(attrs={"placeholder": "Rua, avenida ou travessa"}),
            "numero": forms.TextInput(attrs={"placeholder": "Numero"}),
            "complemento": forms.TextInput(attrs={"placeholder": "Apartamento, bloco, referencia"}),
            "bairro": forms.TextInput(attrs={"placeholder": "Bairro"}),
            "cidade": forms.TextInput(attrs={"placeholder": "Cidade"}),
            "uf": forms.TextInput(attrs={"placeholder": "SP"}),
            "endereco": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in [
            "email",
            "telefone",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "endereco",
        ]:
            self.fields[field_name].required = False

        for name, field in self.fields.items():
            if name in ["status", "origem"]:
                field.widget.attrs["class"] = "form-select"
            elif name != "endereco":
                field.widget.attrs["class"] = "form-control text-uppercase" if name == "uf" else "form-control"

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["email"] = normalizar_email(cleaned_data.get("email"))
        cleaned_data["telefone"] = normalizar_telefone(cleaned_data.get("telefone"))
        cleaned_data["uf"] = (cleaned_data.get("uf") or "").strip().upper()
        cleaned_data["endereco"] = montar_endereco_limpo(cleaned_data) or (cleaned_data.get("endereco") or "").strip()
        return cleaned_data


class OrcamentoForm(forms.Form):
    lead = forms.ModelChoiceField(
        label="Lead de origem",
        queryset=Lead.objects.none(),
        required=False,
        empty_label="Preencher manualmente ou selecionar lead",
        widget=forms.Select(),
    )
    cliente = forms.ModelChoiceField(
        label="Cliente ja cadastrado",
        queryset=Cliente.objects.none(),
        required=False,
        empty_label="Preencher manualmente ou selecionar cliente",
        widget=forms.Select(),
    )
    criar_cliente_automatico = forms.BooleanField(
        label="Criar cliente automaticamente ao salvar",
        required=False,
    )
    name = forms.CharField(
        label="Nome do cliente",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Maria Souza"}),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={"placeholder": "cliente@empresa.com"}),
    )
    telefone = forms.CharField(
        label="Telefone",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "(11) 99999-9999"}),
    )
    cep = forms.CharField(
        label="CEP",
        required=False,
        max_length=9,
        widget=forms.TextInput(attrs={"placeholder": "00000-000", "autocomplete": "postal-code"}),
    )
    logradouro = forms.CharField(
        label="Logradouro",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Rua, avenida ou travessa"}),
    )
    numero = forms.CharField(
        label="Numero",
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "Numero"}),
    )
    complemento = forms.CharField(
        label="Complemento",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Apartamento, bloco, referencia"}),
    )
    bairro = forms.CharField(
        label="Bairro",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Bairro"}),
    )
    cidade = forms.CharField(
        label="Cidade",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "Cidade"}),
    )
    uf = forms.CharField(
        label="UF",
        required=False,
        max_length=2,
        widget=forms.TextInput(attrs={"placeholder": "SP"}),
    )
    endereco = forms.CharField(required=False, widget=forms.HiddenInput())
    descricao = forms.CharField(
        label="Observacoes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Detalhes do pedido, prazo ou acabamento.",
            }
        ),
    )
    quantidade = forms.IntegerField(
        label="Quantidade",
        min_value=1,
        initial=1,
    )
    itens = forms.ModelMultipleChoiceField(
        label="Itens do catalogo",
        queryset=Service_catalog.objects.none(),
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )

    def __init__(self, *args, **kwargs):
        if args and args[0] is not None:
            args = (self._data_com_origem(args[0]), *args[1:])
        elif kwargs.get("data") is not None:
            kwargs["data"] = self._data_com_origem(kwargs["data"])

        super().__init__(*args, **kwargs)
        self.fields["lead"].queryset = Lead.objects.filter(cliente__isnull=True).exclude(
            status=Lead.Status.CONVERTIDO
        ).order_by("-created_at", "-id")
        self.fields["lead"].label_from_instance = self._lead_label
        self.fields["cliente"].queryset = Cliente.objects.order_by("name", "email")
        self.fields["itens"].queryset = Service_catalog.objects.select_related("categoria").order_by("categoria__name", "tipo", "name")
        self.fields["itens"].label_from_instance = self._catalogo_item_label
        self.fields["lead"].widget.attrs["class"] = "form-select"
        self.fields["cliente"].widget.attrs["class"] = "form-select"
        self.fields["criar_cliente_automatico"].widget.attrs["class"] = "form-check-input"
        self.fields["name"].widget.attrs["class"] = "form-control"
        self.fields["email"].widget.attrs["class"] = "form-control"
        self.fields["telefone"].widget.attrs["class"] = "form-control"
        self.fields["cep"].widget.attrs["class"] = "form-control"
        self.fields["logradouro"].widget.attrs["class"] = "form-control"
        self.fields["numero"].widget.attrs["class"] = "form-control"
        self.fields["complemento"].widget.attrs["class"] = "form-control"
        self.fields["bairro"].widget.attrs["class"] = "form-control"
        self.fields["cidade"].widget.attrs["class"] = "form-control"
        self.fields["uf"].widget.attrs["class"] = "form-control text-uppercase"
        self.fields["descricao"].widget.attrs["class"] = "form-control"
        self.fields["quantidade"].widget.attrs["class"] = "form-control"
        self.fields["itens"].widget.attrs["class"] = "form-select"

    @staticmethod
    def _catalogo_item_label(item: Service_catalog) -> str:
        categoria_nome = item.categoria_nome
        categoria = f"{categoria_nome} - " if categoria_nome else ""
        return f"{categoria}{item.name} | R$ {item.valor:.2f}"

    @staticmethod
    def _lead_label(lead: Lead) -> str:
        contato = lead.telefone or lead.email or "sem contato"
        return f"#{lead.pk} - {lead.name} ({contato})"

    @staticmethod
    def _data_com_origem(data):
        mutable_data = data.copy()
        lead_id = mutable_data.get("lead")
        cliente_id = mutable_data.get("cliente")

        if cliente_id:
            return mutable_data

        if lead_id:
            lead = Lead.objects.filter(pk=lead_id).first()
            if lead:
                for field_name in [
                    "name",
                    "email",
                    "telefone",
                    "cep",
                    "logradouro",
                    "numero",
                    "complemento",
                    "bairro",
                    "cidade",
                    "uf",
                    "endereco",
                ]:
                    if not mutable_data.get(field_name):
                        mutable_data[field_name] = getattr(lead, field_name, None) or ""

        return mutable_data

    def clean(self):
        cleaned_data = super().clean()
        lead = cleaned_data.get("lead")
        cliente = cleaned_data.get("cliente")
        if cliente:
            for field_name in [
                "name",
                "email",
                "telefone",
                "cep",
                "logradouro",
                "numero",
                "complemento",
                "bairro",
                "cidade",
                "uf",
                "endereco",
            ]:
                if not cleaned_data.get(field_name):
                    cleaned_data[field_name] = getattr(cliente, field_name, None) or ""
            cleaned_data["lead"] = None
            cleaned_data["criar_cliente_automatico"] = False
        elif lead:
            for field_name in [
                "name",
                "email",
                "telefone",
                "cep",
                "logradouro",
                "numero",
                "complemento",
                "bairro",
                "cidade",
                "uf",
                "endereco",
            ]:
                if not cleaned_data.get(field_name):
                    cleaned_data[field_name] = getattr(lead, field_name, None) or ""

        cleaned_data["email"] = normalizar_email(cleaned_data.get("email"))
        cleaned_data["telefone"] = normalizar_telefone(cleaned_data.get("telefone"))
        cleaned_data["uf"] = (cleaned_data.get("uf") or "").strip().upper()
        cleaned_data["endereco"] = montar_endereco_limpo(cleaned_data) or (cleaned_data.get("endereco") or "").strip()
        if not cleaned_data.get("cliente") and not cleaned_data.get("name"):
            self.add_error("name", "Informe o nome do cliente ou selecione um cliente cadastrado.")
        if cleaned_data.get("criar_cliente_automatico") and not cleaned_data.get("email"):
            self.add_error("email", "Informe um email para criar o cliente automaticamente.")
        return cleaned_data


class ClienteVinculoOrcamentoForm(forms.Form):
    cliente = forms.ModelChoiceField(
        label="Cliente cadastrado",
        queryset=Cliente.objects.none(),
        empty_label="Selecione um cliente",
        widget=forms.Select(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cliente"].queryset = Cliente.objects.order_by("name", "email")
        self.fields["cliente"].widget.attrs["class"] = "form-select"


class TecnicoForm(forms.ModelForm):
    username = forms.CharField(
        label="Usuario de acesso",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: equipe-a"}),
    )
    senha = forms.CharField(
        label="Senha inicial",
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Defina a senha de acesso"}),
    )

    class Meta:
        model = Tecnico
        fields = ["name", "email", "telefone", "especialidade", "ativo", "observacoes"]
        labels = {
            "name": "Nome da equipe ou tecnico",
            "email": "Email",
            "telefone": "Telefone",
            "especialidade": "Especialidade",
            "ativo": "Ativo",
            "observacoes": "Observacoes",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Equipe A"}),
            "email": forms.EmailInput(attrs={"placeholder": "equipe@empresa.com"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(11) 99999-9999"}),
            "especialidade": forms.TextInput(attrs={"placeholder": "Ex.: Sofas, tapetes, colchao"}),
            "observacoes": forms.Textarea(attrs={"rows": 4, "placeholder": "Disponibilidade, area de atendimento ou detalhes internos."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields["username"].initial = self.instance.user.username
            self.fields["senha"].label = "Nova senha"
            self.fields["senha"].widget.attrs["placeholder"] = "Preencha apenas para trocar a senha"
        else:
            self.fields["senha"].required = True

        self.fields["username"].widget.attrs["class"] = "form-control"
        self.fields["senha"].widget.attrs["class"] = "form-control"
        for name, field in self.fields.items():
            if name not in ["username", "senha"]:
                field.required = name == "name"
                field.widget.attrs["class"] = "form-check-input" if name == "ativo" else "form-control"

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["email"] = normalizar_email(cleaned_data.get("email"))
        cleaned_data["telefone"] = normalizar_telefone(cleaned_data.get("telefone"))
        return cleaned_data

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        user_model = get_user_model()
        existing_user = user_model.objects.filter(username__iexact=username).first()
        current_user_id = self.instance.user_id if self.instance and self.instance.pk else None
        if existing_user and existing_user.pk != current_user_id:
            raise forms.ValidationError("Ja existe um usuario com este login.")
        return username

    def save(self, commit=True):
        tecnico = super().save(commit=False)
        if not commit:
            return tecnico

        tecnico.save()
        user = self._save_user(tecnico)
        if tecnico.user_id != user.pk:
            tecnico.user = user
            tecnico.save(update_fields=["user", "updated_at"])
        self.save_m2m()
        return tecnico

    def _save_user(self, tecnico: Tecnico):
        user_model = get_user_model()
        user = tecnico.user or user_model()
        user.username = self.cleaned_data["username"]
        user.email = tecnico.email or ""
        user.first_name = tecnico.name
        user.is_active = tecnico.ativo
        user.is_staff = False
        user.is_superuser = False
        senha = self.cleaned_data.get("senha")
        if senha:
            user.set_password(senha)
        user.save()

        group, _ = Group.objects.get_or_create(name=TEAM_GROUP)
        user.groups.add(group)
        return user


class AdminUserForm(forms.ModelForm):
    senha = forms.CharField(
        label="Senha inicial",
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Defina a senha de acesso"}),
    )

    class Meta:
        model = get_user_model()
        fields = ["first_name", "username", "email", "is_active"]
        labels = {
            "first_name": "Nome do admin/dono",
            "username": "Usuario de acesso",
            "email": "Email",
            "is_active": "Ativo",
        }
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "Ex.: Joao Silva"}),
            "username": forms.TextInput(attrs={"placeholder": "Ex.: joao-admin"}),
            "email": forms.EmailInput(attrs={"placeholder": "admin@empresa.com"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["senha"].label = "Nova senha"
            self.fields["senha"].widget.attrs["placeholder"] = "Preencha apenas para trocar a senha"
        else:
            self.fields["senha"].required = True
            self.initial.setdefault("is_active", True)

        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-check-input" if name == "is_active" else "form-control"

    def clean_email(self):
        return normalizar_email(self.cleaned_data.get("email"))

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        user_model = get_user_model()
        existing_user = user_model.objects.filter(username__iexact=username).first()
        current_user_id = self.instance.pk if self.instance and self.instance.pk else None
        if existing_user and existing_user.pk != current_user_id:
            raise forms.ValidationError("Ja existe um usuario com este login.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email") or ""
        user.is_staff = False
        user.is_superuser = False
        senha = self.cleaned_data.get("senha")
        if senha:
            user.set_password(senha)
        if commit:
            user.save()
            admin_group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
            team_group, _ = Group.objects.get_or_create(name=TEAM_GROUP)
            user.groups.add(admin_group)
            user.groups.remove(team_group)
            self.save_m2m()
        return user


class OrdemServicoForm(forms.ModelForm):
    class Meta:
        model = OrdemServico
        fields = [
            "orcamento",
            "cliente",
            "titulo",
            "descricao",
            "endereco",
            "data_agendada",
            "hora_inicio",
            "hora_fim",
            "tecnico",
            "administrador_executa",
            "status",
            "valor",
            "instrucoes",
            "checklist",
        ]
        labels = {
            "orcamento": "Orcamento de origem",
            "cliente": "Cliente",
            "titulo": "Titulo da OS",
            "descricao": "Servico a realizar",
            "endereco": "Endereco do servico",
            "data_agendada": "Data agendada",
            "hora_inicio": "Hora inicial",
            "hora_fim": "Hora final prevista",
            "tecnico": "Equipe tecnica",
            "administrador_executa": "Administrador/dono executa o servico",
            "status": "Status",
            "valor": "Valor",
            "instrucoes": "Instrucoes internas",
            "checklist": "Checklist do servico",
        }
        widgets = {
            "orcamento": forms.Select(),
            "cliente": forms.Select(),
            "titulo": forms.TextInput(attrs={"placeholder": "Ex.: Higienizacao sofa - Cliente Maria"}),
            "descricao": forms.Textarea(attrs={"rows": 4, "placeholder": "Detalhes do servico, itens, produtos e cuidados."}),
            "endereco": forms.TextInput(attrs={"placeholder": "Endereco completo do atendimento"}),
            "data_agendada": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
            "tecnico": forms.Select(),
            "administrador_executa": forms.CheckboxInput(),
            "status": forms.Select(),
            "valor": forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
            "instrucoes": forms.Textarea(attrs={"rows": 3, "placeholder": "Orientacoes para quem vai executar."}),
            "checklist": forms.Textarea(attrs={"rows": 4, "placeholder": "Ex.: Fotografar antes/depois; aspirar; extrair; finalizar."}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        if args and args[0] is not None:
            args = (self._data_com_orcamento(args[0]), *args[1:])
        elif kwargs.get("data") is not None:
            kwargs["data"] = self._data_com_orcamento(kwargs["data"])

        super().__init__(*args, **kwargs)

        orcamentos = Orcamento.objects.filter(aprovado=True).filter(Q(ordem_servico__isnull=True))
        if instance and instance.orcamento_id:
            orcamentos = Orcamento.objects.filter(Q(pk=instance.orcamento_id) | Q(aprovado=True, ordem_servico__isnull=True))
        self.fields["orcamento"].queryset = orcamentos.order_by("-created_at", "-id")
        self.fields["orcamento"].label_from_instance = self._orcamento_label
        self.fields["orcamento"].required = False
        self.fields["cliente"].queryset = Cliente.objects.order_by("name", "email")
        self.fields["cliente"].required = False
        self.fields["tecnico"].queryset = Tecnico.objects.filter(ativo=True).order_by("name")
        self.fields["tecnico"].required = False
        self.fields["descricao"].required = False
        self.fields["endereco"].required = False
        self.fields["hora_fim"].required = False
        self.fields["instrucoes"].required = False
        self.fields["checklist"].required = False

        for name, field in self.fields.items():
            if name == "administrador_executa":
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    @staticmethod
    def _orcamento_label(orcamento: Orcamento) -> str:
        return f"#{orcamento.pk} - {orcamento.name} | R$ {orcamento.valor:.2f}"

    @staticmethod
    def _data_com_orcamento(data):
        mutable_data = data.copy()
        orcamento_id = mutable_data.get("orcamento")
        if not orcamento_id:
            return mutable_data

        orcamento = Orcamento.objects.filter(pk=orcamento_id).first()
        if not orcamento:
            return mutable_data

        if not mutable_data.get("cliente") and orcamento.cliente_id:
            mutable_data["cliente"] = str(orcamento.cliente_id)
        if not mutable_data.get("titulo"):
            mutable_data["titulo"] = f"Servico para {orcamento.name}"
        if not mutable_data.get("descricao"):
            itens = ", ".join(item.name for item in orcamento.itens.all())
            mutable_data["descricao"] = itens or orcamento.descricao or ""
        if not mutable_data.get("endereco"):
            mutable_data["endereco"] = orcamento.endereco or ""
        if not mutable_data.get("valor"):
            mutable_data["valor"] = str(orcamento.valor or 0)
        return mutable_data

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("tecnico") and not cleaned_data.get("administrador_executa"):
            self.add_error(
                "administrador_executa",
                "Selecione uma equipe tecnica ou marque que o administrador/dono executa o servico.",
            )

        hora_inicio = cleaned_data.get("hora_inicio")
        hora_fim = cleaned_data.get("hora_fim")
        if hora_inicio and hora_fim and hora_fim <= hora_inicio:
            self.add_error("hora_fim", "A hora final deve ser posterior a hora inicial.")
        return cleaned_data


class OrdemServicoConclusaoForm(forms.ModelForm):
    class Meta:
        model = OrdemServico
        fields = ["status", "observacoes_execucao", "checklist"]
        labels = {
            "status": "Status final",
            "observacoes_execucao": "Observacoes da execucao",
            "checklist": "Checklist executado",
        }
        widgets = {
            "status": forms.Select(),
            "observacoes_execucao": forms.Textarea(attrs={"rows": 4, "placeholder": "Relate o que foi feito, intercorrencias e orientacoes ao cliente."}),
            "checklist": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (OrdemServico.Status.CONCLUIDA, "Concluida"),
            (OrdemServico.Status.EM_ANDAMENTO, "Em andamento"),
            (OrdemServico.Status.CANCELADA, "Cancelada"),
        ]
        self.fields["status"].widget.attrs["class"] = "form-select"
        self.fields["observacoes_execucao"].required = False
        self.fields["checklist"].required = False
        self.fields["observacoes_execucao"].widget.attrs["class"] = "form-control"
        self.fields["checklist"].widget.attrs["class"] = "form-control"


def montar_endereco_limpo(cleaned_data: dict) -> str:
    logradouro = (cleaned_data.get("logradouro") or "").strip()
    numero = (cleaned_data.get("numero") or "").strip()
    complemento = (cleaned_data.get("complemento") or "").strip()
    bairro = (cleaned_data.get("bairro") or "").strip()
    cidade = (cleaned_data.get("cidade") or "").strip()
    uf = (cleaned_data.get("uf") or "").strip().upper()

    partes = []
    if logradouro:
        partes.append(f"{logradouro}, {numero}" if numero else logradouro)
    if complemento:
        partes.append(complemento)
    if bairro:
        partes.append(bairro)
    cidade_uf = " - ".join(parte for parte in [cidade, uf] if parte)
    if cidade_uf:
        partes.append(cidade_uf)

    return " | ".join(partes)
