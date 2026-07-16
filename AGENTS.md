# Regras de implementação do frontend

## Idioma da interface

- Toda a interface do sistema deve ser escrita em português do Brasil.
- Preserve obrigatoriamente todos os acentos, cedilhas, pontuação e caracteres especiais.
- Nunca remova acentos dos textos apresentados ao usuário.
- Não transforme textos visíveis em nomes técnicos de programação.

Exemplos corretos:

- Catálogo
- Serviços
- Orçamentos
- Configurações
- Valor médio
- Itens cadastrados
- Categorias
- Tipos de serviço
- Ordens de serviço

Exemplos incorretos:

- Catalogo
- Servicos
- Orcamentos
- Configuracoes
- Valor medio
- Tipos de servico
- Ordens de Servico

## Separação entre código e conteúdo visual

Nomes técnicos podem permanecer sem acentos:

- Variáveis
- Funções
- Rotas
- IDs
- Classes CSS
- Nomes de arquivos
- Chaves de objetos
- Componentes

Exemplo:

```tsx
const configuracoes = {
  path: "/configuracoes",
  label: "Configurações"
};