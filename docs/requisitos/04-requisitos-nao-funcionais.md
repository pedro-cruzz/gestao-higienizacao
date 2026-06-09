# Requisitos Não Funcionais

## RNF-001 - Plataforma

O sistema deve ser uma aplicação web baseada em Django.

Stack atual:

- Python 3.14;
- Django 6.0.4;
- templates Django;
- Bootstrap 5 via CDN;
- Bootstrap Icons via CDN;
- SweetAlert2 via CDN;
- ReportLab para PDF;
- Pillow para imagens;
- WhiteNoise para arquivos estáticos;
- dj-database-url para configuração de banco por URL.

## RNF-002 - Banco de Dados

O sistema deve suportar configuração de banco por variável de ambiente.

Critérios:

- usar `DATABASE_URL` quando informada;
- usar SQLite local quando `DATABASE_URL` não existir;
- exigir SSL para bancos não SQLite quando configurado por URL;
- manter migrations Django como fonte da estrutura de banco.

## RNF-003 - Seguranca de Acesso

O sistema deve restringir rotas por autenticação e perfil.

Critérios:

- rotas internas exigem login;
- rotas administrativas exigem perfil Administrador ou Desenvolvedor;
- rotas de dev exigem perfil Desenvolvedor;
- rotas operacionais de equipe exigem perfil Equipe, Administrador ou Desenvolvedor;
- usuários sem perfil valido não acessam o sistema;
- ações de escrita sensíveis devem usar POST;
- exclusões via GET devem ser bloqueadas por redirecionamento.

## RNF-004 - Segregacao de Dados

O sistema deve isolar dados por dono.

Critérios:

- entidades de negócio devem usar `owner` quando aplicavel;
- consultas administrativas devem filtrar por owner;
- desenvolvedores podem visualizar todos os dados;
- equipe visualiza somente ordens relacionadas ao técnico vinculado ao usuário;
- criação de registros deve preencher owner do usuário logado.

## RNF-005 - Validacao de Dados

O sistema deve validar entradas antes de persistir.

Critérios:

- emails devem ser normalizados para minusculas;
- telefones devem ser normalizados para formato com DDD;
- telefones invalidos devem gerar erro;
- UF deve ser salva em maiusculas;
- quantidade de orçamento deve ser no mínimo 1;
- multiplicador deve ser maior que zero;
- OS deve ter técnico ou execução por administrador;
- hora final da OS deve ser posterior a hora inicial;
- username deve ser unico;
- senha deve usar validadores do Django.

## RNF-006 - Arquivos e Mídia

O sistema deve armazenar arquivos de mídia no `MEDIA_ROOT`.

Critérios:

- `MEDIA_URL` deve apontar para `/media/`;
- imagens de catálogo devem ficar em `catálogo/`;
- logos de PDF devem ficar em `orçamentos/logos/`;
- fotos de perfil devem ficar em `perfis/`;
- upload de foto de perfil deve aceitar imagem até 3 MB;
- upload de logo de PDF deve aceitar tipos de imagem permitidos até 3 MB;
- arquivos antigos de foto de perfil devem ser removidos quando substituidos.

## RNF-007 - Arquivos Estáticos

O sistema deve servir arquivos estáticos de forma apropriada para desenvolvimento e produção.

Critérios:

- `STATIC_URL` deve ser `/static/`;
- `STATIC_ROOT` deve apontar para `staticfiles`;
- em produção, WhiteNoise deve poder usar armazenamento comprimido e manifestado;
- em desenvolvimento/testes, usar storage estatico padrão.

## RNF-008 - Configuração por Ambiente

O sistema deve ler configurações sensíveis e variáveis por ambiente.

Critérios:

- carregar `.env`;
- `SECRET_KEY` deve ser configuravel;
- `DJANGO_DEBUG` deve controlar debug;
- `RENDER_EXTERNAL_HOSTNAME` deve poder entrar em `ALLOWED_HOSTS`;
- backend de email deve ser configuravel por `EMAIL_BACKEND`;
- remetente padrão deve ser configuravel por `DEFAULT_FROM_EMAIL`.

## RNF-009 - Integrações Externas

O sistema depende de serviços externos para endereço e mapa.

ViaCEP:

- base URL: `https://viacep.com.br`;
- timeout padrão: 5 segundos;
- deve tratar CEP invalido;
- deve tratar indisponibilidade temporaria;
- deve permitir preenchimento manual quando a consulta falhar.

Nominatim:

- base URL: `https://nominatim.openstreetmap.org`;
- timeout padrão: 5 segundos;
- user-agent: `HigiFlow/1.0`;
- deve limitar busca ao Brasil;
- deve tentar consulta estruturada e consultas textuais alternativas;
- deve tratar rate limit e indisponibilidade temporaria.

Google Maps:

- o sistema gera links externos de busca, embed e rota;
- não há chave de API configurada no código atual para esses links.

## RNF-010 - Disponibilidade e Degradacao

O sistema deve continuar utilizável quando integrações externas falharem.

Critérios:

- falha no ViaCEP não deve impedir preenchimento manual de endereço;
- falha no Nominatim deve retornar mensagem de erro compreensivel;
- ausência de endereço deve impedir apenas mapa/rota, não o cadastro principal;
- PDF deve continuar usando iniciais da marca quando logo não puder ser carregada.

## RNF-011 - Usabilidade

O sistema deve oferecer interface organizada para uso recorrente.

Critérios:

- sidebar fixa no desktop;
- navegacao responsiva em telas menores;
- topbar com busca;
- botoes com icones;
- alertas visuais para sucesso, erro e confirmacao;
- modo claro/escuro persistente;
- fallback de avatar por iniciais quando não houver foto;
- tabelas e cards devem manter leitura em desktop e mobile.

## RNF-012 - Compatibilidade de Navegador

O sistema deve funcionar em navegadores modernos.

Critérios:

- usar HTML, CSS e JavaScript padrão;
- usar `localStorage` para tema quando disponivel;
- se `localStorage` falhar, usar tema claro como fallback;
- usar `prefers-color-scheme` para definir tema inicial quando não houver preferencia salva.

## RNF-013 - PDF e Layout

O PDF de orçamento deve ser legível e resiliente a dados longos.

Critérios:

- textos longos devem quebrar linha;
- palavras longas devem ser divididas quando necessario;
- conteúdo deve paginar quando houver muitos itens;
- valores monetarios devem ser formatados em Real;
- PDF deve conter cabeçalho, resumo do cliente, tabela de serviços e bloco final de total;
- PDF deve manter layout mesmo sem logo.

## RNF-014 - Internacionalizacao e Localidade

O sistema usa configuração técnica em ingles, mas textos de negócio em portugues.

Estado atual:

- `LANGUAGE_CODE = 'en-us'`;
- `TIME_ZONE = 'UTC'`;
- interface em portugues;
- datas e moedas são formatadas manualmente em alguns pontos.

Requisito recomendado:

- se o sistema for usado em produção no Brasil, alinhar `LANGUAGE_CODE` e `TIME_ZONE` ao contexto brasileiro.

## RNF-015 - Auditoria Basica

O sistema deve registrar datas básicas de criação e atualização.

Critérios:

- entidades principais possuem `created_at`;
- entidades principais possuem `updated_at`;
- data de conclusão da OS deve ser registrada quando status for Concluida.

## RNF-016 - Manutenibilidade

O sistema deve manter regras de negócio centralizadas sempre que possível.

Critérios:

- validações de formulario devem ficar nos forms;
- filtros de owner devem usar `owned_queryset`;
- preenchimento de owner deve usar `set_owner` quando aplicavel;
- integrações externas devem ficar em `service/services`;
- rotas devem permanecer declaradas em `service/urls.py`.

## RNF-017 - Testabilidade

O sistema deve manter cobertura automatizada para fluxos críticos.

Fluxos atualmente cobertos por testes:

- autenticação e redirecionamento por perfil;
- gestão de acessos;
- isolamento de dados por owner;
- dashboard;
- perfil e foto;
- leads e filtros;
- conversão de lead;
- clientes;
- catálogo e upload de imagem;
- categorias;
- orçamentos e cálculo;
- ViaCEP;
- mapa/geocodificação;
- aprovação de orçamento;
- PDF;
- técnicos;
- ordens de serviço.

## RNF-018 - Limitacoes Conhecidas

- Algumas views antigas ou auxiliares mantem dados de exemplo/fallback.
- Algumas rotas possuem comportamento legado preservado para compatibilidade.
- A agenda e as OS dependem fortemente do preenchimento correto de owner/técnico.
- A interface usa CDNs externos para Bootstrap, Bootstrap Icons e SweetAlert2.
- Não há, no código atual, controle de permissões por objeto alem do owner e técnico vinculado.


