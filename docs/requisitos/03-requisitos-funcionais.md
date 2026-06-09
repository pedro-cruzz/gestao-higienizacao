# Requisitos Funcionais

## RF-001 - Autenticacao

O sistema deve permitir login com usuário e senha.

Critérios:

- usuários autenticados com perfil valido acessam o sistema;
- usuários sem perfil valido recebem erro de acesso;
- usuários de equipe são redirecionados para a agenda;
- administradores e desenvolvedores são redirecionados para o dashboard;
- deve existir logout com mensagem de saida segura.

## RF-002 - Recuperação de Senha

O sistema deve permitir fluxo de esqueci minha senha.

Critérios:

- deve haver tela para solicitar reset;
- deve haver email de reset;
- deve haver tela de confirmacao;
- deve haver tela de conclusão.

## RF-003 - Perfil do Usuário

O sistema deve permitir que administradores atualizem seus dados de perfil.

Critérios:

- editar nome, sobrenome, usuário e email;
- normalizar email para minusculas;
- trocar senha mediante senha atual correta;
- validar nova senha usando validadores do Django;
- salvar foto de perfil;
- aceitar apenas arquivo de imagem para foto;
- limitar foto de perfil a 3 MB;
- manter sessao ativa após troca de senha.

## RF-004 - Tema Claro/Escuro

O sistema deve permitir alternar a interface entre modo claro e escuro.

Critérios:

- o botao fica no topo do sistema autenticado;
- o tema selecionado é salvo no navegador;
- o login respeita o tema salvo;
- quando não houver tema salvo, deve ser considerada a preferencia do sistema operacional.

## RF-005 - Dashboard

O sistema deve exibir painel inicial para administradores.

Critérios:

- total de leads;
- taxa de conversão de orçamentos;
- total de serviços ativos;
- quantidade de serviços no catálogo;
- faturamento baseado em orçamentos aprovados;
- comparativos do mes atual contra o mes anterior;
- leads recentes;
- ordens recentes ou orçamentos recentes como fallback.

## RF-006 - Gestão de Acessos

O sistema deve permitir que desenvolvedores gerenciem acessos administrativos.

Critérios:

- listar usuários administradores e desenvolvedores;
- buscar por nome, sobrenome, usuário ou email;
- criar usuário administrador;
- criar usuário desenvolvedor;
- editar usuário;
- alterar senha quando preenchida;
- ativar/desativar usuário;
- excluir usuário;
- impedir exclusão do próprio usuário;
- impedir que um usuário remova o próprio perfil dev;
- impedir que um usuário desative o próprio acesso.

## RF-007 - Gestão de Leads

O sistema deve permitir cadastro e acompanhamento de leads.

Critérios:

- cadastrar lead com nome, email, telefone, endereço e origem;
- status permitidos: Novo, Contatado, Aguardando e Convertido;
- origens permitidas: Manual, WhatsApp, Instagram, Indicacao, Site e Outro;
- normalizar email;
- normalizar telefone para formato com DDD;
- rejeitar telefone invalido;
- armazenar endereço estruturado quando preenchido;
- montar endereço legível com logradouro, numero, complemento, bairro, cidade e UF;
- listar leads;
- filtrar por busca textual, status, origem e período;
- indicar visualmente status e origem;
- indicar quando o lead já foi convertido;
- permitir criar cliente a partir do lead;
- permitir criar orçamento a partir do lead.

## RF-008 - Conversao de Lead

O sistema deve converter lead em cliente ou orçamento.

Critérios:

- ao criar cliente a partir de lead, copiar dados do lead;
- ao criar cliente a partir de lead, marcar lead como Convertido;
- ao criar orçamento a partir de lead, copiar dados do lead;
- se o orçamento for criado sem cliente, lead Novo deve passar para Contatado;
- se o orçamento for vinculado a cliente, lead deve passar para Convertido.

## RF-009 - Gestão de Clientes

O sistema deve permitir gestão de clientes.

Critérios:

- cadastrar cliente manualmente;
- cadastrar cliente a partir de lead;
- cadastrar cliente a partir de orçamento;
- editar cliente;
- excluir cliente;
- listar clientes;
- buscar por nome, email, telefone, endereço, bairro, cidade, UF ou status;
- calcular total de serviços por cliente;
- calcular total gasto por cliente;
- calcular ticket medio;
- classificar cliente como Residencial ou Empresarial por heuristica textual;
- exibir detalhe do cliente com orçamentos e ordens recentes.

## RF-010 - Catálogo de Serviços

O sistema deve permitir gestão do catálogo.

Critérios:

- cadastrar categoria;
- editar categoria;
- excluir categoria sem itens vinculados;
- impedir exclusão de categoria com itens vinculados;
- cadastrar item/serviço;
- editar item/serviço;
- excluir item/serviço;
- associar item a categoria;
- ao salvar item com categoria, copiar nome da categoria para o campo `tipo`;
- informar valor base;
- permitir imagem do item;
- aceitar upload de imagem no catálogo;
- listar itens por categoria/tipo/nome;
- buscar por nome, tipo, categoria ou descrição;
- exibir total de itens, total de categorias e valor medio.

## RF-011 - Adicionais de Orçamento

O sistema deve permitir criar valores adicionais de orçamento.

Critérios:

- cadastrar adicional com nome, valor e status ativo;
- editar adicional;
- excluir adicional;
- listar adicionais;
- pesquisar adicional por nome;
- usar apenas adicionais ativos na criação de orçamento.

## RF-012 - Multiplicadores de Orçamento

O sistema deve permitir criar fatores multiplicadores de preço.

Critérios:

- cadastrar multiplicador com nome, fator e status ativo;
- fator deve ser maior que zero;
- editar multiplicador;
- excluir multiplicador;
- listar multiplicadores;
- pesquisar multiplicador por nome;
- usar apenas multiplicadores ativos na criação de orçamento.

## RF-013 - Criacao de Orçamento

O sistema deve permitir criar orçamentos.

Critérios:

- selecionar lead de origem opcional;
- selecionar cliente existente opcional;
- preencher dados do cliente manualmente quando não houver cliente selecionado;
- selecionar um ou mais itens do catálogo;
- informar quantidade minima 1;
- selecionar adicionais opcionais;
- selecionar multiplicadores opcionais;
- preencher observações;
- preencher endereço estruturado;
- normalizar email;
- normalizar telefone;
- montar endereço legível;
- exigir nome do cliente quando não houver cliente selecionado;
- exigir email quando for solicitado criar cliente automaticamente.

## RF-014 - Cálculo de Orçamento

O sistema deve calcular o valor total do orçamento.

Formula atual:

```text
valor_total = (soma_valor_itens + soma_adicionais) * quantidade * produto_dos_multiplicadores
```

Critérios:

- todos os itens selecionados entram na soma;
- adicionais entram como valores fixos;
- multiplicadores ativos selecionados são multiplicados entre si;
- quantidade multiplica o total final;
- valor final é salvo no orçamento.

## RF-015 - Edicao de Orçamento

O sistema deve permitir editar orçamento existente.

Critérios:

- carregar dados atuais do orçamento;
- carregar itens, adicionais e multiplicadores já selecionados;
- recalcular valor ao salvar;
- manter vinculo com lead/cliente quando aplicavel;
- permitir criar ou vincular cliente conforme regras do fluxo.

## RF-016 - Listagem e Detalhe de Orçamentos

O sistema deve permitir listar e detalhar orçamentos.

Critérios:

- listar orçamentos por data de criação decrescente;
- buscar por cliente, email, telefone ou descrição;
- exibir status Pendente ou Aprovado;
- exibir validade visual de 15 dias a partir da criação;
- exibir total, pendentes e aprovados;
- exibir itens vinculados;
- exibir cliente vinculado;
- exibir mapa quando houver endereço;
- exibir ordem de serviço relacionada quando existir.

## RF-017 - Aprovacao de Orçamento

O sistema deve permitir aprovar orçamentos.

Critérios:

- aprovar orçamento pela rota atual ou rota legada;
- se não houver cliente vinculado, criar ou atualizar cliente a partir do email do orçamento;
- orçamento sem email não pode criar cliente automaticamente;
- marcar orçamento como aprovado;
- vincular cliente ao orçamento;
- converter lead relacionado;
- criar ordem de serviço automaticamente, salvo quando solicitado não criar;
- se o orçamento já estiver aprovado, informar ao usuário.

## RF-018 - Vinculo Manual de Cliente ao Orçamento

O sistema deve permitir vincular cliente existente ao orçamento.

Critérios:

- selecionar cliente cadastrado do mesmo owner;
- vincular cliente ao orçamento;
- opcionalmente aprovar o orçamento no mesmo fluxo;
- converter lead relacionado quando houver.

## RF-019 - Cadastro de Cliente a Partir de Orçamento

O sistema deve permitir criar cliente a partir de orçamento.

Critérios:

- copiar nome, email, telefone e endereço do orçamento;
- atualizar cliente existente com mesmo email e owner, quando existir;
- criar novo cliente quando não existir;
- marcar cliente como Convertido;
- vincular cliente ao orçamento;
- opcionalmente aprovar o orçamento.

## RF-020 - PDF de Orçamento

O sistema deve gerar PDF de proposta comercial.

Critérios:

- gerar arquivo PDF com content type `application/pdf`;
- nome do arquivo deve conter o id do orçamento;
- incluir dados do cliente;
- incluir contato e endereço;
- incluir itens do orçamento;
- incluir quantidade, valor unitario e total;
- incluir valor total da proposta;
- quebrar texto longo para preservar layout;
- paginar quando houver muitos itens;
- permitir marca personalizada de até 42 caracteres;
- permitir frase personalizada de até 180 caracteres;
- permitir cor de destaque em hexadecimal;
- usar cor padrão quando cor invalida;
- permitir upload de logo;
- aceitar logo PNG/JPEG/WebP de até 3 MB;
- salvar frase e logo no orçamento quando enviados por POST.

## RF-021 - Gestão de Equipe Tecnica

O sistema deve permitir gerenciar equipes/técnicos.

Critérios:

- listar técnicos;
- buscar por nome, email, telefone ou especialidade;
- cadastrar técnico;
- editar técnico;
- informar nome, email, telefone, especialidade, ativo e observações;
- criar ou atualizar usuário de acesso vinculado ao técnico;
- usuário de técnico deve entrar no grupo `Equipe`;
- username deve ser unico;
- senha inicial e obrigatoria na criação;
- senha nova e opcional na edicao;
- técnico inativo não deve ser selecionavel como responsavel de nova OS.

## RF-022 - Criacao de Ordem de Serviço

O sistema deve permitir criar ordem de serviço.

Critérios:

- criar OS manualmente;
- criar OS a partir de orçamento aprovado sem OS;
- carregar dados iniciais do orçamento;
- selecionar cliente opcional;
- selecionar técnico ativo opcional;
- permitir marcar que administrador/dono executa o serviço;
- exigir técnico ou administrador executor;
- informar titulo, descrição, endereço, data, hora inicial, hora final prevista, status, valor, instrucoes e checklist;
- hora final, quando preenchida, deve ser posterior a hora inicial;
- salvar owner da OS.

## RF-023 - Listagem de Ordens de Serviço

O sistema deve permitir listar ordens de serviço.

Critérios:

- administradores veem ordens do próprio owner;
- equipe ve ordens atribuídas ao seu usuário técnico;
- buscar por titulo, cliente, orçamento, técnico ou endereço;
- ordenar por data e hora decrescentes;
- exibir status, cliente, responsavel, valor e mapa;
- exibir totais por status;
- permitir atualização rápida de cliente e responsavel por administradores.

## RF-024 - Agenda

O sistema deve exibir agenda de ordens de serviço.

Critérios:

- exibir visão mensal;
- exibir visão semanal;
- navegar por mes e semana;
- destacar dia atual;
- listar ordens por data e horario;
- exibir rota diária quando houver endereços;
- abrir modal de detalhe da OS;
- usar apenas ordens visiveis ao usuário logado.

## RF-025 - Status e Conclusão de Ordem de Serviço

O sistema deve permitir alterar status e concluir OS.

Status permitidos:

- Agendada;
- Em andamento;
- Concluida;
- Cancelada.

Critérios:

- atualizar status por requisicao POST;
- rejeitar status invalido;
- ao marcar Concluida, preencher data de conclusão se ainda não existir;
- ao sair de Concluida, limpar data de conclusão;
- permitir conclusão com checklist e observações de execução;
- retornar totais atualizados por status em alteracao via JSON.

## RF-026 - Mapas e Rotas

O sistema deve permitir consultar mapa de orçamento e OS.

Critérios:

- montar endereço a partir de logradouro, numero, bairro, cidade, UF e CEP;
- usar endereço livre como fallback;
- retornar erro quando não houver endereço suficiente;
- geocodificar endereço via Nominatim;
- retornar latitude, longitude e display name;
- gerar links para Google Maps;
- gerar rota com destino;
- gerar rota diária com waypoints quando houver mais de um endereço.

## RF-027 - Busca de Endereço por CEP

O sistema deve buscar endereço por CEP.

Critérios:

- aceitar apenas CEP com 8 digitos;
- consultar ViaCEP;
- retornar cep, logradouro, bairro, cidade, UF e complemento;
- retornar erro de validação quando CEP for invalido ou inexistente;
- retornar erro temporario quando a API estiver indisponível.

## RF-028 - Exclusoes

O sistema deve permitir exclusões controladas.

Critérios:

- excluir lead indiretamente não esta exposto nas rotas atuais;
- excluir cliente sem apagar orçamento relacionado, mantendo FK nula;
- excluir orçamento;
- excluir item do catálogo;
- excluir categoria apenas quando não houver item vinculado;
- excluir OS;
- rejeitar exclusões por GET redirecionando para a tela principal do recurso.

## RF-029 - Uploads e Mídia

O sistema deve permitir uploads em pontos especificos.

Critérios:

- imagem de item do catálogo em `catálogo/`;
- logo de PDF em `orçamentos/logos/`;
- foto de perfil em `perfis/`;
- arquivos devem ser servidos pelo `MEDIA_URL`;
- fotos de perfil e logos devem ter validação de tipo/tamanho conforme formulario/fluxo.

## RF-030 - Interface e Navegacao

O sistema deve fornecer navegacao consistente.

Critérios:

- sidebar com links conforme perfil;
- topbar com busca;
- área de usuário com nome, perfil, foto/iniciais e logout;
- alertas via SweetAlert;
- confirmacao para ações destrutivas quando configurada no template;
- uso de Bootstrap e Bootstrap Icons.


