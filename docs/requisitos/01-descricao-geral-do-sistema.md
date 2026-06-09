# Descrição Geral do Sistema

## Visão Geral

O HigiFlow e um ERP web para operacoes de higienização. Ele centraliza o processo comercial e operacional desde a entrada de um lead até a execução do serviço em uma ordem de serviço agendada.

O sistema permite que a empresa cadastre serviços, gere orçamentos, converta leads em clientes, aprove propostas, organize equipes técnicas e acompanhe a agenda de atendimentos.

## Objetivos do Sistema

- Organizar o funil comercial de leads.
- Padronizar o catálogo de serviços e valores.
- Automatizar o cálculo de orçamentos.
- Facilitar a aprovação de propostas.
- Converter orçamentos e leads em clientes.
- Gerar ordens de serviço a partir de orçamentos aprovados.
- Distribuir atendimentos entre equipes técnicas.
- Acompanhar status das ordens e conclusoes.
- Gerar PDFs de proposta comercial para envio ao cliente.
- Exibir mapas e rotas para facilitar deslocamentos.

## Fluxo Principal de Negócio

1. O administrador cadastra categorias e itens no catálogo.
2. O administrador registra um lead ou seleciona um cliente existente.
3. O administrador cria um orçamento com itens do catálogo, quantidade, adicionais e multiplicadores.
4. O sistema calcula o valor total do orçamento.
5. O orçamento pode ser vinculado a um cliente existente ou gerar um novo cliente automaticamente.
6. Ao aprovar o orçamento, o lead relacionado e convertido, quando existir.
7. O sistema pode criar automaticamente uma ordem de serviço para o orçamento aprovado.
8. A ordem de serviço recebe data, horario, responsavel e status.
9. A equipe técnica ou o administrador atualiza o andamento da ordem.
10. A ordem e concluida com checklist e observações de execução.

## Módulos do Sistema

### Autenticacao e Perfil

Controla login, logout, recuperação de senha, redirecionamento por perfil, edicao de dados do usuário, troca de senha e foto de perfil.

### Dashboard

Apresenta indicadores de leads, taxa de conversão, serviços ativos, catálogo e faturamento, alem de leads e ordens recentes.

### Leads

Permite criar, listar, filtrar e converter leads. Leads possuem status, origem, contato e endereço.

### Clientes

Permite criar, editar, listar, excluir e visualizar detalhes de clientes. Clientes podem ser criados manualmente, a partir de leads ou a partir de orçamentos.

### Catálogo

Permite cadastrar categorias e itens/serviços do catálogo. Itens possuem preço base, imagem, descrição e características técnicas.

### Orçamentos

Permite criar, editar, listar, detalhar, aprovar e excluir orçamentos. O cálculo usa itens do catálogo, quantidade, adicionais fixos e multiplicadores.

### PDF de Orçamento

Gera proposta comercial em PDF com dados do cliente, serviços, valores e personalização de marca, frase, cor e logo.

### Ordens de Serviço

Permite criar, editar, listar, detalhar, atualizar status, vincular cliente/responsavel, concluir e excluir ordens de serviço.

### Agenda

Exibe ordens de serviço em visão mensal e semanal, com rota diária quando houver endereços.

### Mapas e Endereço

Integra ViaCEP para busca de endereço por CEP e Nominatim para geocodificação de endereços em orçamentos e ordens de serviço. Tambem gera links para Google Maps.

## Escopo de Dados

Os principais dados do sistema são:

- dados de usuários e grupos;
- perfis de usuário com foto;
- categorias do catálogo;
- itens do catálogo;
- leads;
- clientes;
- orçamentos;
- adicionais e multiplicadores;
- técnicos/equipes;
- ordens de serviço;
- arquivos de mídia, como imagens de catálogo, logos de PDF e fotos de perfil.

## Regras Gerais de Propriedade de Dados

- Registros de negócio usam o campo `owner` para separar dados por conta/administrador.
- Usuários do grupo Desenvolvedores, ou superusuarios, podem acessar dados de todos os owners.
- Usuários administradores acessam e gerenciam apenas os próprios dados.
- Usuários de equipe visualizam ordens vinculadas ao seu usuário técnico.

## Interfaces Principais

- `/login/`: tela de login.
- `/`: dashboard ou redirecionamento para agenda, dependendo do perfil.
- `/perfil/`: perfil do usuário administrador.
- `/admins/`: gestão de acessos de administradores e desenvolvedores.
- `/leads/`: listagem e filtros de leads.
- `/clientes/`: listagem de clientes.
- `/catálogo/`: catálogo de serviços.
- `/orçamentos/`: listagem de orçamentos.
- `/ordens-serviço/`: listagem operacional de OS.
- `/agenda/`: agenda mensal/semanal.

## Fora do Escopo Atual Observado

- Portal do cliente final.
- Pagamento online.
- Assinatura digital.
- Controle de estoque.
- Emissao fiscal.
- Aplicativo mobile nativo.


