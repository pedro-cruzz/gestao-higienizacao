# Perfis de Usuário

## Visão Geral

O sistema usa autenticação nativa do Django e controle de acesso por grupos. Existem três perfis principais:

- Desenvolvedores
- Administradores
- Equipe

As permissões são aplicadas por decoradores de rota e por funções de verificacao de perfil.

## Perfil: Desenvolvedor

### Identificacao

Um usuário é considerado desenvolvedor quando:

- e superusuario; ou
- pertence ao grupo `Desenvolvedores`.

### Permissoes

O desenvolvedor pode:

- acessar a área de gestão de acessos;
- listar administradores e desenvolvedores;
- criar usuários administradores;
- criar outros usuários desenvolvedores;
- editar usuários de acesso;
- excluir usuários de acesso, exceto o próprio usuário;
- acessar dados de todos os owners;
- acessar todas as funcionalidades de administrador.

### Restrições

- Não pode excluir o próprio usuário.
- Ao editar o próprio usuário, não pode remover o próprio perfil dev.
- Ao editar o próprio usuário, não pode desativar a própria conta.

## Perfil: Administrador

### Identificacao

Um usuário é considerado administrador quando:

- e desenvolvedor; ou
- possui `is_staff=True`; ou
- pertence ao grupo `Administradores`.

### Permissoes

O administrador pode:

- acessar o dashboard;
- gerenciar o próprio perfil;
- cadastrar e editar foto de perfil;
- trocar a própria senha;
- acessar leads, clientes, catálogo, orçamentos, ordens e agenda;
- cadastrar, editar e excluir leads;
- cadastrar, editar e excluir clientes;
- cadastrar, editar e excluir categorias sem itens vinculados;
- cadastrar, editar e excluir itens do catálogo;
- fazer upload de imagens para itens do catálogo;
- cadastrar adicionais e multiplicadores de orçamento;
- criar, editar, aprovar, concluir e excluir orçamentos;
- gerar PDF de orçamento;
- personalizar PDF com marca, frase, cor e logo;
- cadastrar e editar equipes técnicas;
- criar, editar, vincular responsavel/cliente e excluir ordens de serviço;
- concluir ordens de serviço;
- visualizar mapas e rotas;
- alternar modo claro/escuro da interface.

### Restrições

- Não acessa a área `Acessos`, reservada para desenvolvedores.
- Não pode visualizar dados de outros administradores, exceto se também for desenvolvedor.
- Não pode excluir categorias que possuem itens vinculados.
- Não pode aprovar orçamento sem criar ou vincular cliente quando o fluxo exigir cliente.
- Para criar cliente automaticamente a partir de orçamento, o orçamento precisa ter email.

## Perfil: Equipe

### Identificacao

Um usuário é considerado equipe quando:

- e administrador; ou
- pertence ao grupo `Equipe`.

Na prática, o usuário operacional é criado a partir do cadastro de `Tecnico`, que gera ou atualiza um usuário Django vinculado ao técnico.

### Permissoes

O usuário de equipe pode:

- fazer login no sistema;
- ser redirecionado para a agenda após login;
- acessar a agenda;
- listar ordens de serviço visiveis para seu usuário técnico;
- abrir detalhe de OS visivel;
- atualizar status de OS;
- concluir OS com status final, checklist e observações;
- consultar mapa/rota de OS visivel.

### Restrições

- Não acessa dashboard administrativo.
- Não acessa leads, catálogo, clientes, orçamentos, configurações ou gestão de técnicos.
- Não cria nem edita orçamentos.
- Não cria nem edita clientes.
- Não gerencia acessos.
- Quando não e administrador, visualiza apenas ordens em que `técnico.user` e o próprio usuário.

## Usuário Sem Perfil

Usuários autenticados sem perfil valido:

- não são autorizados a entrar no HigiFlow;
- recebem erro no login informando que ainda não possuem perfil de acesso.

## Regras de Redirecionamento

- Administrador ou desenvolvedor entra no dashboard.
- Equipe sem perfil administrativo entra na agenda.
- A raiz do sistema (`/`) decide automaticamente entre dashboard e agenda conforme perfil.

## Matriz Resumida de Acesso

| Funcionalidade | Desenvolvedor | Administrador | Equipe |
| --- | --- | --- | --- |
| Login/logout | Sim | Sim | Sim |
| Dashboard | Sim | Sim | Não |
| Perfil próprio | Sim | Sim | Não, no estado atual |
| Gestão de acessos | Sim | Não | Não |
| Leads | Sim | Sim | Não |
| Clientes | Sim | Sim | Não |
| Catálogo | Sim | Sim | Não |
| Orçamentos | Sim | Sim | Não |
| PDF de orçamento | Sim | Sim | Não |
| Equipe técnica | Sim | Sim | Não |
| Ordens de serviço | Sim | Sim | Sim, apenas visiveis |
| Agenda | Sim | Sim | Sim |
| Mapas de OS | Sim | Sim | Sim, apenas visiveis |

## Regras de Segregacao de Dados

- A maioria dos registros de negócio possui campo `owner`.
- Para administradores, consultas usam `owner=request.user`.
- Para desenvolvedores, a regra de ownership não filtra dados.
- Para equipe, ordens são filtradas por técnico vinculado ao usuário.


