# Sistema Essence

Aplicação web local para gestão de perfumes (estoque, vendas a prazo, pagamentos, inadimplência e relatórios). Roda inteiramente offline, sem autenticação, persistindo em SQLite no próprio host.

## Stack

- **Backend:** Python 3.9+ / Flask (`>=2.3,<4.0`) — API REST em [`app.py`](app.py), arquivo único.
- **Persistência:** SQLite via `sqlite3` da stdlib (`essence.db`). `PRAGMA foreign_keys = ON` por conexão.
- **Frontend:** SPA vanilla — [`templates/index.html`](templates/index.html), [`static/js/app.js`](static/js/app.js), [`static/css/style.css`](static/css/style.css). Sem build step, sem dependências de frontend.
- **PDF:** geração manual de `%PDF-1.4` em [`app.py`](app.py) (`gerar_pdf_relatorio`), sem bibliotecas externas.
- **Servidor:** `app.run` em `127.0.0.1`, dev server do Flask (`debug=False`).

Única dependência externa é o Flask (ver [`requirements.txt`](requirements.txt)).

## Como rodar

Os scripts criam o virtualenv, instalam dependências na primeira execução e abrem o navegador.

```bash
# macOS / Linux
./iniciar.sh

# Windows
iniciar.bat
```

Manual:

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Servidor sobe em `http://127.0.0.1:8000`. Porta configurável via env `ESSENCE_PORT`.

## Modelo de dados

`init_db()` cria o schema no boot e popula dados de exemplo apenas na primeira execução (`first_time`). `_migrar_esquema_antigo()` migra automaticamente do schema legado (1 venda = 1 perfume) para o atual (ficha + itens).

| Tabela | Função |
|---|---|
| `perfumes` | catálogo/estoque. `preco_custo`, `valor_final`, `estoque`, `deleted_at` (soft delete). |
| `vendas` | ficha do cliente. `status` (`Pendente`/`Pago`), `data_vencimento`, `data_quitacao`, `deleted_at`. |
| `venda_itens` | itens da ficha. FK → `vendas` (`ON DELETE CASCADE`) e `perfumes` (`ON DELETE SET NULL`). Guarda `perfume_nome` desnormalizado, `valor`, `lucro`, `data_compra`. |
| `pagamentos` | pagamentos parciais por venda. FK → `vendas` (`ON DELETE CASCADE`). |
| `config` | key/value (meta do mês, dados do rodapé do relatório, Pix). |

Pontos relevantes:

- **Soft delete:** `perfumes` e `vendas` usam `deleted_at`. `purge_trash()` remove definitivamente após `TRASH_RETENTION_DAYS = 7` (executado no boot).
- **Estoque transacional:** baixa no registro da venda e é estornado/recalculado ao editar ou apagar a ficha. Venda não pode exceder o estoque disponível.
- **Saldo:** `Total − Σ pagamentos`. Ficha vira `Pago`/`Quitada` quando o saldo zera.

## API

Todas as rotas retornam JSON, exceto `/`, `/assets/...`, `/api/backup` e `/api/relatorio.pdf`.

```
GET    /                              SPA
GET    /assets/<filename>             logo/favicon

GET    /api/perfumes
POST   /api/perfumes
PUT    /api/perfumes/<pid>
DELETE /api/perfumes/<pid>            soft delete

GET    /api/vendas
GET    /api/vendas/<vid>
POST   /api/vendas
PUT    /api/vendas/<vid>
DELETE /api/vendas/<vid>              soft delete
POST   /api/vendas/<vid>/pagamentos   registra pagamento parcial
POST   /api/vendas/<vid>/quitar       quita saldo restante
GET    /api/vendas/<vid>/relatorio    texto pronto p/ WhatsApp

GET    /api/inadimplencia            vendas com saldo + vencimento expirado
GET    /api/dashboard                agregados do mês

GET    /api/config
PUT    /api/config

GET    /api/lixeira
POST   /api/lixeira/<tipo>/<id>/restaurar
DELETE /api/lixeira/<tipo>/<id>      exclusão definitiva
POST   /api/lixeira/esvaziar

GET    /api/relatorio.pdf            relatório geral (download)
GET    /api/backup                   dump .db (download)
POST   /api/restore                  substitui o banco a partir de upload
```

## Cálculos (em [`app.py`](app.py))

- Lucro do item = `valor_final − preco_custo`
- Margem (%) = `lucro / valor_final × 100`
- Faturamento/lucro do mês = soma das vendas/lucros do mês corrente
- Total investido = `Σ (preco_custo × estoque)`
- Inadimplente = venda com saldo devedor **e** `data_vencimento` no passado

## Backup e restore

- **Backup:** `GET /api/backup` usa `sqlite3` backup API para gerar um `.db` consistente e baixa via `send_file`. Equivalente manual: copiar `essence.db`.
- **Restore:** `POST /api/restore` valida o upload (abre como SQLite), grava uma cópia de segurança dos dados atuais em `backups/` e então substitui `essence.db`.

## Layout do projeto

```
app.py              # backend + API + schema + PDF
templates/          # SPA (index.html)
static/             # css, js
assets/             # logo.jpeg, favicon.jpeg
essence.db          # banco (criado no primeiro boot)
backups/            # cópias automáticas pré-restore (gitignored)
iniciar.sh / .bat   # bootstrap venv + run
```

`venv/`, `backups/` e caches estão no [`.gitignore`](.gitignore).

## Notas

- Sem auth e bind em `127.0.0.1` — projetado para uso local single-user, não para deploy exposto.
- Dev server do Flask; para produção use um WSGI server (gunicorn/waitress).
- Migração de schema legado é automática e idempotente no boot.
```
