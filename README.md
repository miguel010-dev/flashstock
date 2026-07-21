# Flash Stock — Site + Painel de Móveis Planejados

## Como rodar

```bash
pip install -r requirements.txt
python app.py
```

Acesse: http://localhost:5000

## Páginas

- `/` — Página inicial (landing)
- `/sobre` — Sobre Nós
- `/catalogo` — Catálogo de produtos (com filtro por categoria)
- `/catalogo/produto/<id>` — Página individual do produto, com galeria de fotos e especificações
- `/login` — Login administrativo
- `/cadastro` — Painel de cadastro de produtos (protegido por login)

## Acesso administrativo

- **E-mail:** flashtock@gmail.com
- **Senha:** @Batatas123

No painel `/cadastro` é possível cadastrar, editar e excluir móveis planejados, com:
- Categoria, descrição, material e acabamento
- Faixas de largura, altura e profundidade (móveis sob medida)
- Preço estimado e prazo de produção
- Marcação de destaque e visibilidade (ativo/inativo)
- Upload de várias fotos por produto, com opção de excluir fotos existentes

## Banco de dados

SQLite (`flashstock.db`), criado automaticamente na primeira execução. Tabelas: `produtos` e `imagens`.

## Estrutura

```
app.py
templates/
  index.html, sobre.html, catalogo.html, produto.html, login.html, cadastro.html
static/
  css/shared.css, js/shared.js
  uploads/   (fotos dos produtos)
  assets/    (logo.png opcional)
```
