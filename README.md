# ERP Higienizacao

Projeto inicial em Django para gerenciamento de:

- catalogo de produtos
- orcamentos
- clientes gerados a partir de orcamentos aprovados

## Stack

- Python 3.14
- Django 6.0.4
- SQLite
- Bootstrap 5

## Funcionalidades Atuais

- cadastro e listagem de produtos do catalogo
- criacao de orcamentos com selecao de itens do catalogo
- aprovacao de orcamento com criacao automatica de cliente
- listagem de clientes
- cadastro de equipe tecnica
- ordens de servico com agenda, responsavel e conclusao
- autenticacao com perfil de administrador e equipe
- painel web com navbar e sidebar

## Modelos Principais

### `Service_catalog`

Representa os produtos/servicos do catalogo.

Campos principais:

- `name`
- `tipo`
- `valor`
- `descricao`
- `tempo`
- `formato`
- `tamanho`
- `largura`
- `comprimento`
- `tecido`

### `Orcamento`

Representa um orcamento criado a partir de itens do catalogo.

Campos principais:

- `name`
- `email`
- `telefone`
- `endereco`
- `valor`
- `descricao`
- `quantidade`
- `aprovado`
- `cliente`
- `itens`

### `Cliente`

Representa o cliente final vinculado a um orcamento aprovado.

Campos principais:

- `name`
- `email`
- `telefone`
- `endereco`

### `Tecnico`

Representa uma equipe ou tecnico que pode receber ordens de servico.

Campos principais:

- `name`
- `email`
- `telefone`
- `especialidade`
- `ativo`

### `OrdemServico`

Representa um servico agendado a partir de um orcamento aprovado ou criado manualmente.

Campos principais:

- `orcamento`
- `cliente`
- `tecnico`
- `administrador_executa`
- `titulo`
- `data_agendada`
- `hora_inicio`
- `status`
- `checklist`
- `observacoes_execucao`

## Fluxo Principal

1. Cadastrar produtos no catalogo
2. Criar um orcamento selecionando itens do catalogo
3. Aprovar o orcamento
4. Criar automaticamente o cliente com base nos dados do orcamento
5. Criar e agendar a ordem de servico
6. Atribuir uma equipe tecnica ou marcar execucao pelo administrador/dono
7. Concluir a OS com checklist e observacoes da execucao

## Rotas Principais

- `/login/` - entrada do sistema
- `/logout/` - saida do sistema
- `/catalogo/` - listagem do catalogo
- `/catalogo/novo/` - cadastro de produto
- `/orcamentos/novo/` - criacao de orcamento
- `/orcamentos/<id>/` - detalhe do orcamento
- `/orcamentos/<id>/aprovar/` - aprovacao do orcamento
- `/ordens-servico/` - listagem de ordens de servico
- `/ordens-servico/nova/` - criacao e agendamento de OS
- `/agenda/` - agenda semanal das OS
- `/tecnicos/` - cadastro de equipes tecnicas
- `/clientes/` - listagem de clientes

## Como Rodar Localmente

### 1. Ativar o ambiente virtual

No PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Aplicar migrations

```powershell
python manage.py migrate
```

### 3. Criar os grupos de acesso

```powershell
python manage.py setup_access_groups
```

Use o admin do Django para colocar usuarios no grupo `Administradores` ou `Equipe`.
Superusuarios e usuarios staff tambem entram com acesso de administrador.

### 4. Rodar o servidor

```powershell
python manage.py runserver
```

Abra no navegador:

```text
http://127.0.0.1:8000/
```

## Deploy no Render com Neon

Para iniciar com dados novos, use um banco Neon vazio ou recrie o banco atual no painel da Neon. Depois configure as variáveis de ambiente no Render com base em `.env.example`.

Variáveis obrigatórias para produção:

- `DJANGO_DEBUG=False`
- `SECRET_KEY`
- `DATABASE_URL` com a URL PostgreSQL da Neon e SSL
- `DJANGO_ALLOWED_HOSTS` com o domínio do Render ou domínio próprio
- `DJANGO_CSRF_TRUSTED_ORIGINS` com `https://...`
- `HIGIFLOW_DEV_USERNAME`
- `HIGIFLOW_DEV_PASSWORD`

O `build.sh` instala dependências, coleta estáticos, aplica migrations e roda `setup_access_groups`. Quando `HIGIFLOW_DEV_USERNAME` e `HIGIFLOW_DEV_PASSWORD` estiverem definidos, esse comando também cria ou atualiza o usuário dev inicial.

Depois do primeiro login com o dev inicial, crie os admins/donos das empresas pelo menu de usuários e permissões.

## Comandos Uteis

### Criar novas migrations

```powershell
python manage.py makemigrations
```

### Aplicar migrations

```powershell
python manage.py migrate
```

### Rodar testes

```powershell
python manage.py test service
```

### Verificar o projeto

```powershell
python manage.py check
```

## Estrutura Inicial

```text
core/       configuracao principal do Django
service/    app principal com models, views, forms, urls e templates
venv/       ambiente virtual local
db.sqlite3  banco local de desenvolvimento
```

## Observacoes

- o projeto usa `db.sqlite3` apenas para desenvolvimento local
- existe `.gitignore` para evitar subir ambiente virtual, cache e arquivos locais
- o visual atual usa Bootstrap por CDN
