# Documento de Requisitos - HigiFlow

## Objetivo

Este conjunto de documentos descreve os requisitos do sistema HigiFlow, um ERP web para empresas de higienização que precisam gerenciar leads, catálogo de serviços, orçamentos, clientes, equipes técnicas, ordens de serviço e agenda operacional.

Os requisitos foram levantados a partir do código atual do projeto Django, incluindo models, forms, views, rotas, testes automatizados, serviços externos e templates.

## Documentos

- [Descrição geral do sistema](./01-descricao-geral-do-sistema.md)
- [Perfis de usuário](./02-perfis-de-usuario.md)
- [Requisitos funcionais](./03-requisitos-funcionais.md)
- [Requisitos não funcionais](./04-requisitos-nao-funcionais.md)

## Escopo Funcional Atual

O sistema contempla:

- autenticação e controle de acesso por perfis;
- painel inicial com métricas comerciais e operacionais;
- gestão de leads;
- conversão de leads em clientes e orçamentos;
- gestão de clientes;
- cadastro de categorias e itens do catálogo;
- upload de imagens para itens do catálogo;
- criação e cálculo de orçamentos;
- adicionais e multiplicadores de preço em orçamentos;
- aprovação de orçamentos;
- geração de clientes a partir de orçamentos;
- geração automática ou manual de ordens de serviço;
- gestão de equipes técnicas;
- agenda mensal e semanal das ordens;
- atualização de status e conclusão de ordens de serviço;
- visualização de mapas e rotas;
- geração de PDF de proposta comercial;
- personalização parcial do PDF;
- perfil de usuário com dados, senha e foto;
- modo claro/escuro persistido no navegador.

## Principais Entidades de Negócio

- Usuário: conta Django usada para login e permissão.
- UserProfile: dados complementares do usuário, atualmente foto de perfil.
- CategoriaCatalogo: agrupamento de serviços/itens.
- Service_catalog: item ou serviço do catálogo, com preço base e características.
- Lead: contato comercial em prospecção.
- Cliente: cliente final convertido ou cadastrado manualmente.
- Orçamento: proposta comercial baseada em itens do catálogo.
- AdicionalOrcamento: valor fixo adicional aplicado ao orçamento.
- MultiplicadorOrcamento: fator multiplicador aplicado ao total do orçamento.
- Técnico: equipe/técnico operacional vinculado opcionalmente a um usuário.
- OrdemServico: execução agendada de um serviço.

## Premissas

- O sistema é multiusuário por dono dos dados (`owner`).
- Desenvolvedores podem visualizar todos os dados.
- Administradores gerenciam os dados da própria conta.
- Equipe técnica acessa apenas áreas operacionais permitidas e ordens atribuídas.
- Orçamentos aprovados podem gerar clientes e ordens de serviço.
- Endereços podem ser preenchidos manualmente ou auxiliados por ViaCEP.
- Mapas dependem de geocodificação via Nominatim e links externos do Google Maps.

## Observações

- Algumas telas contêm exemplos ou dados de fallback quando não há registros.
- A documentação descreve o comportamento atual observado no código, não um roadmap futuro.
- A acentuação e alguns textos da interface ainda aparecem sem normalização completa em partes do código legado.


