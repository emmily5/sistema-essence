#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema Essence - Gestão de vendas de perfumes
Aplicação local (Flask + SQLite) de uso individual e offline.

Modelo de dados:
  - perfumes      : produtos e estoque
  - vendas        : a FICHA de um cliente (cabeçalho da compra)
  - venda_itens   : cada perfume comprado (perfume, quantidade, valor, data)
  - pagamentos    : pagamentos parciais registrados (valor, data)
  - config        : meta mensal e dados fixos do rodapé (chave Pix etc.)

Regras de cálculo (explícitas):
  - Lucro do item       = valor_do_item - (preco_custo * quantidade)
  - Total da compra     = soma dos valores dos itens da ficha
  - Total pago          = soma dos pagamentos registrados na ficha
  - Saldo devedor       = total_da_compra - total_pago
  - Compra quitada      = saldo devedor <= 0  -> status "Pago"
  - Inadimplente        = saldo > 0 E data_vencimento < hoje
  - Faturamento do mês  = soma dos valores dos itens com data no mês atual
  - Lucro do mês        = soma do lucro dos itens com data no mês atual
  - Total investido     = soma de (preco_custo * estoque) de todos os perfumes
  - Baixa de estoque    = ao vender, estoque -= quantidade (devolvido ao apagar/editar)
"""

import os
import io
import sqlite3
from datetime import datetime, date, timedelta

from flask import (
    Flask, request, jsonify, send_file, send_from_directory,
    render_template, g, abort
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "essence.db")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

# Itens apagados vão para a lixeira e são removidos de vez após este prazo (dias).
TRASH_RETENTION_DAYS = 7

CONFIG_PADRAO = {
    "meta_mensal": "5000",
    "pix_chave": "84 900000000",
    "pix_nome": "Ana Maria da Silva",
    "pix_empresa": "Cloudwalk Ip Ltda",
}

MESES_EXT = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
             "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]

app = Flask(__name__, static_folder="static", template_folder="templates")


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Cria/atualiza o banco e popula com dados de exemplo na primeira vez."""
    first_time = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS perfumes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nome        TEXT    NOT NULL,
            marca       TEXT    DEFAULT '',
            preco_custo REAL    NOT NULL DEFAULT 0,
            valor_final REAL    NOT NULL DEFAULT 0,
            estoque     INTEGER NOT NULL DEFAULT 0,
            deleted_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );
        """
    )

    # Detecta o esquema antigo (uma venda = um perfume) e migra, se preciso.
    _migrar_esquema_antigo(conn)

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS vendas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente    TEXT    NOT NULL,
            forma_pagamento TEXT    NOT NULL DEFAULT 'Pix',
            status          TEXT    NOT NULL DEFAULT 'Pendente',
            data_vencimento TEXT,
            data_quitacao   TEXT,
            observacao      TEXT    DEFAULT '',
            deleted_at      TEXT
        );

        CREATE TABLE IF NOT EXISTS venda_itens (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id     INTEGER NOT NULL,
            perfume_id   INTEGER,
            perfume_nome TEXT,
            quantidade   INTEGER NOT NULL DEFAULT 1,
            valor        REAL    NOT NULL DEFAULT 0,
            lucro        REAL    NOT NULL DEFAULT 0,
            data_compra  TEXT    NOT NULL,
            observacao   TEXT    DEFAULT '',
            FOREIGN KEY (venda_id) REFERENCES vendas (id) ON DELETE CASCADE,
            FOREIGN KEY (perfume_id) REFERENCES perfumes (id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS pagamentos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            valor    REAL    NOT NULL DEFAULT 0,
            data     TEXT    NOT NULL,
            FOREIGN KEY (venda_id) REFERENCES vendas (id) ON DELETE CASCADE
        );
        """
    )

    for chave, valor in CONFIG_PADRAO.items():
        conn.execute(
            "INSERT OR IGNORE INTO config (chave, valor) VALUES (?, ?)", (chave, valor)
        )

    conn.commit()

    if first_time:
        seed_data(conn)

    purge_trash(conn)
    conn.close()


def _migrar_esquema_antigo(conn):
    """Converte o banco antigo (1 venda = 1 perfume) para o novo (ficha + itens)."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(vendas)")]
    if not cols:
        return  # tabela ainda não existe -> esquema novo será criado
    if "valor_venda" not in cols:
        return  # já está no esquema novo

    conn.execute("ALTER TABLE vendas RENAME TO vendas_antiga")
    conn.executescript(
        """
        CREATE TABLE vendas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente    TEXT    NOT NULL,
            forma_pagamento TEXT    NOT NULL DEFAULT 'Pix',
            status          TEXT    NOT NULL DEFAULT 'Pendente',
            data_vencimento TEXT,
            data_quitacao   TEXT,
            observacao      TEXT    DEFAULT '',
            deleted_at      TEXT
        );
        CREATE TABLE IF NOT EXISTS venda_itens (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id     INTEGER NOT NULL,
            perfume_id   INTEGER,
            perfume_nome TEXT,
            quantidade   INTEGER NOT NULL DEFAULT 1,
            valor        REAL    NOT NULL DEFAULT 0,
            lucro        REAL    NOT NULL DEFAULT 0,
            data_compra  TEXT    NOT NULL,
            observacao   TEXT    DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS pagamentos (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            valor    REAL    NOT NULL DEFAULT 0,
            data     TEXT    NOT NULL
        );
        """
    )
    antigas = conn.execute("SELECT * FROM vendas_antiga").fetchall()
    for v in antigas:
        conn.execute(
            "INSERT INTO vendas (id, nome_cliente, forma_pagamento, status, "
            "data_vencimento, data_quitacao, observacao, deleted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (v["id"], v["nome_cliente"], v["forma_pagamento"], v["status"],
             v["data_pagamento"], v["data_quitacao"], v["observacao"], v["deleted_at"]),
        )
        pnome = None
        if v["perfume_id"]:
            pr = conn.execute(
                "SELECT nome FROM perfumes WHERE id = ?", (v["perfume_id"],)
            ).fetchone()
            pnome = pr["nome"] if pr else None
        conn.execute(
            "INSERT INTO venda_itens (venda_id, perfume_id, perfume_nome, quantidade, "
            "valor, lucro, data_compra, observacao) VALUES (?, ?, ?, 1, ?, ?, ?, ?)",
            (v["id"], v["perfume_id"], pnome, v["valor_venda"], v["lucro_venda"],
             v["data_compra"], v["observacao"] or ""),
        )
        if v["status"] == "Pago":
            conn.execute(
                "INSERT INTO pagamentos (venda_id, valor, data) VALUES (?, ?, ?)",
                (v["id"], v["valor_venda"], v["data_quitacao"] or v["data_compra"]),
            )
    conn.execute("DROP TABLE vendas_antiga")
    conn.commit()


def purge_trash(conn):
    """Remove definitivamente os itens da lixeira mais antigos que o prazo."""
    limite = (datetime.now() - timedelta(days=TRASH_RETENTION_DAYS)).isoformat()
    conn.execute("DELETE FROM perfumes WHERE deleted_at IS NOT NULL AND deleted_at < ?", (limite,))
    conn.execute("DELETE FROM vendas WHERE deleted_at IS NOT NULL AND deleted_at < ?", (limite,))
    conn.commit()


def seed_data(conn):
    """Dados de exemplo para testar todas as telas imediatamente."""
    perfumes = [
        # nome, marca, custo, final, estoque
        ("Delina", "Parfums de Marly", 80.00, 135.00, 6),
        ("English Pear", "Jo Malone", 75.00, 135.00, 5),
        ("My Way", "Giorgio Armani", 78.00, 135.00, 4),
        ("Sauvage", "Dior", 110.00, 190.00, 3),
        ("Capilar Delina", "Parfums de Marly", 35.00, 70.00, 8),
        ("Brisa Cítrica", "Natura", 35.00, 95.00, 10),
    ]
    conn.executemany(
        "INSERT INTO perfumes (nome, marca, preco_custo, valor_final, estoque) "
        "VALUES (?, ?, ?, ?, ?)", perfumes,
    )
    # mapa nome -> (id, custo)
    pmap = {r["nome"]: (r["id"], r["preco_custo"])
            for r in conn.execute("SELECT id, nome, preco_custo FROM perfumes")}

    def add_ficha(nome, forma, vencimento, itens, pagamentos, obs=""):
        cur = conn.execute(
            "INSERT INTO vendas (nome_cliente, forma_pagamento, status, "
            "data_vencimento, observacao) VALUES (?, ?, 'Pendente', ?, ?)",
            (nome, forma, vencimento, obs),
        )
        vid = cur.lastrowid
        for (pnome, qtd, valor, data, iobs) in itens:
            pid, custo = pmap[pnome]
            lucro = valor - custo * qtd
            conn.execute(
                "INSERT INTO venda_itens (venda_id, perfume_id, perfume_nome, "
                "quantidade, valor, lucro, data_compra, observacao) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (vid, pid, pnome, qtd, valor, lucro, data, iobs),
            )
            conn.execute("UPDATE perfumes SET estoque = estoque - ? WHERE id = ?", (qtd, pid))
        for (valor, data) in pagamentos:
            conn.execute(
                "INSERT INTO pagamentos (venda_id, valor, data) VALUES (?, ?, ?)",
                (vid, valor, data),
            )
        _recompute_status(conn, vid)
        return vid

    ano = date.today().year
    mes = date.today().month
    mes_passado = mes - 1 if mes > 1 else 12
    ano_pass = ano if mes > 1 else ano - 1

    def d(dia, m=mes, a=ano):
        return f"{a:04d}-{m:02d}-{dia:02d}"

    # Cliente com vários itens e datas diferentes + pagamentos parciais (Prazo)
    add_ficha(
        "Dorinha Carcará", "Prazo", f"{ano:04d}-{mes:02d}-10",
        itens=[
            ("Delina", 1, 135.00, "2026-03-27", ""),
            ("English Pear", 1, 135.00, "2026-03-27", ""),
            ("My Way", 1, 135.00, "2026-03-27", ""),
            ("Sauvage", 1, 190.00, d(10), "extra forte"),
            ("Capilar Delina", 1, 70.00, d(10), ""),
            ("English Pear", 1, 135.00, d(10), ""),
        ],
        pagamentos=[(137.50, d(10)), (137.50, d(10, mes_passado, ano_pass))],
    )

    # Cliente quitado (Pix)
    add_ficha(
        "Maria Silva", "Pix", None,
        itens=[("Brisa Cítrica", 1, 95.00, d(5), "")],
        pagamentos=[(95.00, d(5))],
    )

    # Cliente inadimplente (venceu no mês passado, ainda deve)
    add_ficha(
        "Fernanda Costa", "Prazo", d(20, mes_passado, ano_pass),
        itens=[
            ("My Way", 1, 135.00, d(15, mes_passado, ano_pass), ""),
            ("Delina", 1, 135.00, d(15, mes_passado, ano_pass), ""),
        ],
        pagamentos=[(100.00, d(18, mes_passado, ano_pass))],
        obs="Cliente prometeu acertar",
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers de valores
# ---------------------------------------------------------------------------
def today_iso():
    return date.today().isoformat()


def parse_float(value, field):
    if value is None or value == "":
        abort(400, description=f"O campo '{field}' é obrigatório.")
    try:
        v = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        abort(400, description=f"O campo '{field}' deve ser um número válido.")
    if v < 0:
        abort(400, description=f"O campo '{field}' não pode ser negativo.")
    return v


def parse_int(value, field, default=0):
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        abort(400, description=f"O campo '{field}' deve ser um número inteiro válido.")


def perfume_to_dict(row):
    preco_custo = row["preco_custo"] or 0
    valor_final = row["valor_final"] or 0
    lucro = valor_final - preco_custo
    margem = (lucro / valor_final * 100) if valor_final else 0
    return {
        "id": row["id"], "nome": row["nome"], "marca": row["marca"] or "",
        "preco_custo": preco_custo, "valor_final": valor_final,
        "estoque": row["estoque"] or 0,
        "lucro": round(lucro, 2), "margem": round(margem, 2),
    }


# ---------------------------------------------------------------------------
# Helpers de venda (totais, status, estoque)
# ---------------------------------------------------------------------------
def _totais(db, venda_id):
    total = db.execute(
        "SELECT COALESCE(SUM(valor), 0) s FROM venda_itens WHERE venda_id = ?",
        (venda_id,)).fetchone()["s"]
    pago = db.execute(
        "SELECT COALESCE(SUM(valor), 0) s FROM pagamentos WHERE venda_id = ?",
        (venda_id,)).fetchone()["s"]
    return round(total, 2), round(pago, 2), round(total - pago, 2)


def _recompute_status(db, venda_id):
    """Define status/quitação a partir do saldo devedor."""
    total, pago, saldo = _totais(db, venda_id)
    if total > 0 and saldo <= 0.004:
        ult = db.execute(
            "SELECT MAX(data) d FROM pagamentos WHERE venda_id = ?", (venda_id,)
        ).fetchone()["d"]
        db.execute("UPDATE vendas SET status = 'Pago', data_quitacao = ? WHERE id = ?",
                   (ult or today_iso(), venda_id))
    else:
        db.execute("UPDATE vendas SET status = 'Pendente', data_quitacao = NULL WHERE id = ?",
                   (venda_id,))


def _devolver_estoque(db, venda_id):
    """Devolve ao estoque a quantidade de todos os itens da ficha."""
    for it in db.execute("SELECT perfume_id, quantidade FROM venda_itens WHERE venda_id = ?",
                         (venda_id,)):
        if it["perfume_id"]:
            db.execute("UPDATE perfumes SET estoque = estoque + ? WHERE id = ?",
                       (it["quantidade"], it["perfume_id"]))


def _validar_e_inserir_itens(db, venda_id, itens):
    """Valida estoque, insere itens e dá baixa no estoque."""
    if not itens:
        abort(400, description="Adicione pelo menos um perfume à compra.")

    # agrega a quantidade necessária por perfume
    necessario = {}
    limpos = []
    for it in itens:
        pid = it.get("perfume_id") or None
        qtd = parse_int(it.get("quantidade"), "Quantidade", 1)
        if qtd < 1:
            abort(400, description="A quantidade de cada item deve ser no mínimo 1.")
        valor = parse_float(it.get("valor"), "Valor do item")
        data_compra = (it.get("data_compra") or "").strip() or today_iso()
        if pid:
            necessario[pid] = necessario.get(pid, 0) + qtd
        limpos.append({
            "pid": pid, "qtd": qtd, "valor": valor,
            "data": data_compra, "obs": (it.get("observacao") or "").strip(),
        })

    # valida estoque disponível
    for pid, qtd in necessario.items():
        p = db.execute(
            "SELECT nome, estoque FROM perfumes WHERE id = ? AND deleted_at IS NULL", (pid,)
        ).fetchone()
        if not p:
            abort(400, description="Um dos perfumes selecionados não existe mais.")
        if qtd > (p["estoque"] or 0):
            abort(400, description=(
                f"Estoque insuficiente de \"{p['nome']}\": "
                f"você tentou vender {qtd} e há apenas {p['estoque'] or 0} em estoque."))

    # insere itens e dá baixa
    for it in limpos:
        custo = 0
        pnome = None
        if it["pid"]:
            pr = db.execute("SELECT nome, preco_custo FROM perfumes WHERE id = ?",
                            (it["pid"],)).fetchone()
            if pr:
                custo, pnome = pr["preco_custo"] or 0, pr["nome"]
        lucro = round(it["valor"] - custo * it["qtd"], 2)
        db.execute(
            "INSERT INTO venda_itens (venda_id, perfume_id, perfume_nome, quantidade, "
            "valor, lucro, data_compra, observacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (venda_id, it["pid"], pnome, it["qtd"], it["valor"], lucro, it["data"], it["obs"]),
        )
        if it["pid"]:
            db.execute("UPDATE perfumes SET estoque = estoque - ? WHERE id = ?",
                       (it["qtd"], it["pid"]))


def _inserir_pagamentos(db, venda_id, pagamentos):
    for p in (pagamentos or []):
        valor = parse_float(p.get("valor"), "Valor do pagamento")
        if valor <= 0:
            continue
        data = (p.get("data") or "").strip() or today_iso()
        db.execute("INSERT INTO pagamentos (venda_id, valor, data) VALUES (?, ?, ?)",
                   (venda_id, valor, data))


def venda_full(db, row):
    vid = row["id"]
    itens = [dict(r) for r in db.execute(
        "SELECT * FROM venda_itens WHERE venda_id = ? ORDER BY data_compra, id", (vid,))]
    pagamentos = [dict(r) for r in db.execute(
        "SELECT * FROM pagamentos WHERE venda_id = ? ORDER BY data, id", (vid,))]
    total, pago, saldo = _totais(db, vid)
    datas = sorted({it["data_compra"] for it in itens if it["data_compra"]})
    venc = row["data_vencimento"]
    atrasada = saldo > 0 and bool(venc) and venc < today_iso()
    return {
        "id": vid,
        "nome_cliente": row["nome_cliente"],
        "forma_pagamento": row["forma_pagamento"],
        "status": row["status"],
        "data_vencimento": venc,
        "data_quitacao": row["data_quitacao"],
        "observacao": row["observacao"] or "",
        "itens": itens,
        "pagamentos": pagamentos,
        "datas_compra": datas,
        "num_itens": len(itens),
        "total": total, "pago": pago, "saldo": saldo,
        "atrasada": atrasada,
    }


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(ASSETS_DIR, filename)


# ---------------------------------------------------------------------------
# API - Perfumes
# ---------------------------------------------------------------------------
@app.route("/api/perfumes", methods=["GET"])
def list_perfumes():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM perfumes WHERE deleted_at IS NULL ORDER BY nome COLLATE NOCASE"
    ).fetchall()
    return jsonify([perfume_to_dict(r) for r in rows])


@app.route("/api/perfumes", methods=["POST"])
def create_perfume():
    data = request.get_json(force=True)
    nome = (data.get("nome") or "").strip()
    if not nome:
        abort(400, description="O nome do perfume é obrigatório.")
    preco_custo = parse_float(data.get("preco_custo"), "Preço de custo")
    valor_final = parse_float(data.get("valor_final"), "Valor final de venda")
    estoque = parse_int(data.get("estoque"), "Estoque", 0)
    db = get_db()
    cur = db.execute(
        "INSERT INTO perfumes (nome, marca, preco_custo, valor_final, estoque) "
        "VALUES (?, ?, ?, ?, ?)",
        (nome, (data.get("marca") or "").strip(), preco_custo, valor_final, estoque))
    db.commit()
    row = db.execute("SELECT * FROM perfumes WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(perfume_to_dict(row)), 201


@app.route("/api/perfumes/<int:pid>", methods=["PUT"])
def update_perfume(pid):
    data = request.get_json(force=True)
    db = get_db()
    if not db.execute("SELECT 1 FROM perfumes WHERE id = ?", (pid,)).fetchone():
        abort(404, description="Perfume não encontrado.")
    nome = (data.get("nome") or "").strip()
    if not nome:
        abort(400, description="O nome do perfume é obrigatório.")
    preco_custo = parse_float(data.get("preco_custo"), "Preço de custo")
    valor_final = parse_float(data.get("valor_final"), "Valor final de venda")
    estoque = parse_int(data.get("estoque"), "Estoque", 0)
    db.execute(
        "UPDATE perfumes SET nome=?, marca=?, preco_custo=?, valor_final=?, estoque=? WHERE id=?",
        (nome, (data.get("marca") or "").strip(), preco_custo, valor_final, estoque, pid))
    db.commit()
    row = db.execute("SELECT * FROM perfumes WHERE id = ?", (pid,)).fetchone()
    return jsonify(perfume_to_dict(row))


@app.route("/api/perfumes/<int:pid>", methods=["DELETE"])
def delete_perfume(pid):
    db = get_db()
    db.execute("UPDATE perfumes SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
               (datetime.now().isoformat(), pid))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API - Vendas / Fichas de clientes
# ---------------------------------------------------------------------------
@app.route("/api/vendas", methods=["GET"])
def list_vendas():
    db = get_db()
    where = ["v.deleted_at IS NULL"]
    params = []

    status = request.args.get("status")
    if status in ("Pago", "Pendente"):
        where.append("v.status = ?")
        params.append(status)

    forma = request.args.get("forma")
    if forma in ("Prazo", "Pix", "Dinheiro", "Cartão"):
        where.append("v.forma_pagamento = ?")
        params.append(forma)

    busca = request.args.get("busca")
    if busca:
        where.append("LOWER(v.nome_cliente) LIKE ?")
        params.append(f"%{busca.lower()}%")

    mes = request.args.get("mes")  # yyyy-mm  (fichas com algum item nesse mês)
    if mes:
        where.append("EXISTS (SELECT 1 FROM venda_itens i WHERE i.venda_id = v.id "
                     "AND substr(i.data_compra,1,7) = ?)")
        params.append(mes)

    sql = "SELECT v.* FROM vendas v WHERE " + " AND ".join(where) + " ORDER BY v.id DESC"
    rows = db.execute(sql, params).fetchall()
    return jsonify([venda_full(db, r) for r in rows])


@app.route("/api/vendas/<int:vid>", methods=["GET"])
def get_venda(vid):
    db = get_db()
    row = db.execute("SELECT * FROM vendas WHERE id = ?", (vid,)).fetchone()
    if not row:
        abort(404, description="Ficha não encontrada.")
    return jsonify(venda_full(db, row))


@app.route("/api/vendas", methods=["POST"])
def create_venda():
    data = request.get_json(force=True)
    db = get_db()
    nome = (data.get("nome_cliente") or "").strip()
    if not nome:
        abort(400, description="O nome do cliente é obrigatório.")
    forma = data.get("forma_pagamento") if data.get("forma_pagamento") in \
        ("Prazo", "Pix", "Dinheiro", "Cartão") else "Pix"
    venc = (data.get("data_vencimento") or "").strip() or None

    cur = db.execute(
        "INSERT INTO vendas (nome_cliente, forma_pagamento, status, data_vencimento, observacao) "
        "VALUES (?, ?, 'Pendente', ?, ?)",
        (nome, forma, venc, (data.get("observacao") or "").strip()))
    vid = cur.lastrowid
    _validar_e_inserir_itens(db, vid, data.get("itens") or [])
    _inserir_pagamentos(db, vid, data.get("pagamentos") or [])
    _recompute_status(db, vid)
    db.commit()
    row = db.execute("SELECT * FROM vendas WHERE id = ?", (vid,)).fetchone()
    return jsonify(venda_full(db, row)), 201


@app.route("/api/vendas/<int:vid>", methods=["PUT"])
def update_venda(vid):
    data = request.get_json(force=True)
    db = get_db()
    row = db.execute("SELECT * FROM vendas WHERE id = ?", (vid,)).fetchone()
    if not row:
        abort(404, description="Ficha não encontrada.")
    nome = (data.get("nome_cliente") or "").strip()
    if not nome:
        abort(400, description="O nome do cliente é obrigatório.")
    forma = data.get("forma_pagamento") if data.get("forma_pagamento") in \
        ("Prazo", "Pix", "Dinheiro", "Cartão") else "Pix"
    venc = (data.get("data_vencimento") or "").strip() or None

    # devolve o estoque dos itens atuais e limpa itens/pagamentos
    _devolver_estoque(db, vid)
    db.execute("DELETE FROM venda_itens WHERE venda_id = ?", (vid,))
    db.execute("DELETE FROM pagamentos WHERE venda_id = ?", (vid,))

    db.execute(
        "UPDATE vendas SET nome_cliente=?, forma_pagamento=?, data_vencimento=?, observacao=? WHERE id=?",
        (nome, forma, venc, (data.get("observacao") or "").strip(), vid))
    _validar_e_inserir_itens(db, vid, data.get("itens") or [])
    _inserir_pagamentos(db, vid, data.get("pagamentos") or [])
    _recompute_status(db, vid)
    db.commit()
    row = db.execute("SELECT * FROM vendas WHERE id = ?", (vid,)).fetchone()
    return jsonify(venda_full(db, row))


@app.route("/api/vendas/<int:vid>/pagamentos", methods=["POST"])
def add_pagamento(vid):
    """Registra um pagamento parcial avulso na ficha."""
    data = request.get_json(force=True)
    db = get_db()
    if not db.execute("SELECT 1 FROM vendas WHERE id = ?", (vid,)).fetchone():
        abort(404, description="Ficha não encontrada.")
    _inserir_pagamentos(db, vid, [data])
    _recompute_status(db, vid)
    db.commit()
    row = db.execute("SELECT * FROM vendas WHERE id = ?", (vid,)).fetchone()
    return jsonify(venda_full(db, row))


@app.route("/api/vendas/<int:vid>/quitar", methods=["POST"])
def quitar_venda(vid):
    """Registra um pagamento do saldo restante, quitando a ficha."""
    db = get_db()
    if not db.execute("SELECT 1 FROM vendas WHERE id = ?", (vid,)).fetchone():
        abort(404, description="Ficha não encontrada.")
    _total, _pago, saldo = _totais(db, vid)
    if saldo > 0:
        db.execute("INSERT INTO pagamentos (venda_id, valor, data) VALUES (?, ?, ?)",
                   (vid, saldo, today_iso()))
    _recompute_status(db, vid)
    db.commit()
    row = db.execute("SELECT * FROM vendas WHERE id = ?", (vid,)).fetchone()
    return jsonify(venda_full(db, row))


@app.route("/api/vendas/<int:vid>", methods=["DELETE"])
def delete_venda(vid):
    """Envia a ficha para a lixeira e devolve o estoque dos itens."""
    db = get_db()
    row = db.execute("SELECT deleted_at FROM vendas WHERE id = ?", (vid,)).fetchone()
    if row and row["deleted_at"] is None:
        _devolver_estoque(db, vid)
        db.execute("UPDATE vendas SET deleted_at = ? WHERE id = ?",
                   (datetime.now().isoformat(), vid))
        db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API - Inadimplência (considera o saldo devedor)
# ---------------------------------------------------------------------------
def _inadimplentes(db):
    rows = db.execute(
        "SELECT * FROM vendas WHERE deleted_at IS NULL AND status = 'Pendente' "
        "AND data_vencimento IS NOT NULL AND data_vencimento < ? ORDER BY data_vencimento",
        (today_iso(),)).fetchall()
    result = []
    for r in rows:
        info = venda_full(db, r)
        if info["saldo"] <= 0:
            continue
        try:
            venc = datetime.strptime(r["data_vencimento"], "%Y-%m-%d").date()
            info["dias_atraso"] = (date.today() - venc).days
        except (ValueError, TypeError):
            info["dias_atraso"] = 0
        result.append(info)
    return result


@app.route("/api/inadimplencia", methods=["GET"])
def inadimplencia():
    return jsonify(_inadimplentes(get_db()))


# ---------------------------------------------------------------------------
# API - Dashboard
# ---------------------------------------------------------------------------
@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    db = get_db()
    mes_atual = date.today().strftime("%Y-%m")

    itens_mes = db.execute(
        "SELECT i.valor, i.lucro FROM venda_itens i JOIN vendas v ON v.id = i.venda_id "
        "WHERE v.deleted_at IS NULL AND substr(i.data_compra, 1, 7) = ?",
        (mes_atual,)).fetchall()
    faturamento = sum(i["valor"] or 0 for i in itens_mes)
    lucro = sum(i["lucro"] or 0 for i in itens_mes)
    num_vendas = len(itens_mes)
    ticket_medio = (faturamento / num_vendas) if num_vendas else 0

    perfumes = db.execute(
        "SELECT preco_custo, estoque FROM perfumes WHERE deleted_at IS NULL").fetchall()
    total_investido = sum((p["preco_custo"] or 0) * (p["estoque"] or 0) for p in perfumes)

    meta_row = db.execute("SELECT valor FROM config WHERE chave = 'meta_mensal'").fetchone()
    meta = float(meta_row["valor"]) if meta_row and meta_row["valor"] else 0
    falta = meta - faturamento
    progresso = (faturamento / meta * 100) if meta else 0

    inad = _inadimplentes(db)
    debitos = sum(i["saldo"] for i in inad)

    return jsonify({
        "mes": mes_atual, "meta": meta,
        "faturamento": round(faturamento, 2), "lucro": round(lucro, 2),
        "falta_meta": round(max(falta, 0), 2),
        "meta_atingida": faturamento >= meta and meta > 0,
        "progresso": round(min(progresso, 100), 1),
        "total_investido": round(total_investido, 2),
        "num_vendas": num_vendas, "ticket_medio": round(ticket_medio, 2),
        "debitos_abertos": round(debitos, 2), "debitos_qtd": len(inad),
    })


# ---------------------------------------------------------------------------
# API - Config (meta e dados do rodapé do relatório)
# ---------------------------------------------------------------------------
@app.route("/api/config", methods=["GET"])
def get_config():
    db = get_db()
    rows = db.execute("SELECT chave, valor FROM config").fetchall()
    return jsonify({r["chave"]: r["valor"] for r in rows})


@app.route("/api/config", methods=["PUT"])
def set_config():
    data = request.get_json(force=True)
    db = get_db()
    if "meta_mensal" in data:
        meta = parse_float(data.get("meta_mensal"), "Meta mensal")
        data["meta_mensal"] = str(meta)
    for chave in ("meta_mensal", "pix_chave", "pix_nome", "pix_empresa"):
        if chave in data:
            db.execute(
                "INSERT INTO config (chave, valor) VALUES (?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                (chave, str(data[chave])))
    db.commit()
    return get_config()


# ---------------------------------------------------------------------------
# API - Relatório de texto por cliente (para colar no WhatsApp)
# ---------------------------------------------------------------------------
def _data_br(iso):
    if not iso:
        return "-"
    p = str(iso).split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else str(iso)


def _moeda_compacta(v):
    """Formata 137.5 -> 'R$137,50' (sem espaço, padrão brasileiro)."""
    s = f"{(v or 0):,.2f}"  # 1,234.56
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$" + s


def gerar_relatorio_cliente(db, vid):
    row = db.execute("SELECT * FROM vendas WHERE id = ?", (vid,)).fetchone()
    if not row:
        abort(404, description="Ficha não encontrada.")
    info = venda_full(db, row)
    cfg = {r["chave"]: r["valor"] for r in db.execute("SELECT chave, valor FROM config")}

    linhas = [info["nome_cliente"].upper()]

    linhas.append("Data da compra:")
    for data in info["datas_compra"]:
        linhas.append(_data_br(data))

    linhas.append("Resumo da Compra:")
    for it in info["itens"]:
        obs = f" ({it['observacao']})" if it["observacao"] else ""
        linhas.append(
            f"{_moeda_compacta(it['valor'])} - {it['quantidade']} Perfume "
            f"{it['perfume_nome'] or 'Perfume'}{obs}")

    linhas.append(f"Total: {_moeda_compacta(info['total'])}")

    linhas.append("Pagamentos:")
    for pg in info["pagamentos"]:
        try:
            dt = datetime.strptime(pg["data"], "%Y-%m-%d").date()
            quando = f"{dt.day} {MESES_EXT[dt.month - 1]}"
        except (ValueError, TypeError):
            quando = _data_br(pg["data"])
        linhas.append(f"{quando} - {_moeda_compacta(pg['valor'])}")

    linhas.append("")
    linhas.append(f"chave pix: {cfg.get('pix_chave', '')}")
    linhas.append(cfg.get("pix_nome", ""))
    linhas.append(cfg.get("pix_empresa", ""))

    return "\n".join(linhas)


@app.route("/api/vendas/<int:vid>/relatorio", methods=["GET"])
def relatorio_cliente(vid):
    texto = gerar_relatorio_cliente(get_db(), vid)
    return jsonify({"texto": texto})


# ---------------------------------------------------------------------------
# API - Lixeira (apagar reversível, com restauração)
# ---------------------------------------------------------------------------
def _dias_restantes(deleted_at):
    try:
        apagado = datetime.fromisoformat(deleted_at)
    except (ValueError, TypeError):
        return 0
    restante = (apagado + timedelta(days=TRASH_RETENTION_DAYS)) - datetime.now()
    return max(restante.days + (1 if restante.seconds > 0 else 0), 0)


@app.route("/api/lixeira", methods=["GET"])
def lixeira():
    db = get_db()
    purge_trash(db)
    perfumes = db.execute(
        "SELECT * FROM perfumes WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC").fetchall()
    vendas = db.execute(
        "SELECT * FROM vendas WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC").fetchall()

    def pf(r):
        d = perfume_to_dict(r)
        d["dias_restantes"] = _dias_restantes(r["deleted_at"])
        return d

    def vf(r):
        d = venda_full(db, r)
        d["dias_restantes"] = _dias_restantes(r["deleted_at"])
        return d

    return jsonify({
        "retencao_dias": TRASH_RETENTION_DAYS,
        "perfumes": [pf(r) for r in perfumes],
        "vendas": [vf(r) for r in vendas],
    })


@app.route("/api/lixeira/<tipo>/<int:item_id>/restaurar", methods=["POST"])
def restaurar_item(tipo, item_id):
    db = get_db()
    if tipo == "perfumes":
        db.execute("UPDATE perfumes SET deleted_at = NULL WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"ok": True})
    if tipo == "vendas":
        # ao restaurar uma ficha, dá baixa no estoque de novo (validando)
        itens = db.execute("SELECT perfume_id, quantidade, perfume_nome "
                           "FROM venda_itens WHERE venda_id = ?", (item_id,)).fetchall()
        necessario = {}
        for it in itens:
            if it["perfume_id"]:
                necessario[it["perfume_id"]] = necessario.get(it["perfume_id"], 0) + it["quantidade"]
        for pid, qtd in necessario.items():
            p = db.execute("SELECT nome, estoque FROM perfumes WHERE id = ? AND deleted_at IS NULL",
                           (pid,)).fetchone()
            if p and qtd > (p["estoque"] or 0):
                abort(400, description=(
                    f"Não dá para restaurar: estoque insuficiente de \"{p['nome']}\" "
                    f"(precisa de {qtd}, há {p['estoque'] or 0})."))
        for pid, qtd in necessario.items():
            db.execute("UPDATE perfumes SET estoque = estoque - ? WHERE id = ?", (qtd, pid))
        db.execute("UPDATE vendas SET deleted_at = NULL WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"ok": True})
    abort(404, description="Tipo inválido.")


@app.route("/api/lixeira/<tipo>/<int:item_id>", methods=["DELETE"])
def excluir_definitivo(tipo, item_id):
    db = get_db()
    tabela = {"perfumes": "perfumes", "vendas": "vendas"}.get(tipo)
    if not tabela:
        abort(404, description="Tipo inválido.")
    db.execute(f"DELETE FROM {tabela} WHERE id = ? AND deleted_at IS NOT NULL", (item_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/lixeira/esvaziar", methods=["POST"])
def esvaziar_lixeira():
    db = get_db()
    db.execute("DELETE FROM perfumes WHERE deleted_at IS NOT NULL")
    db.execute("DELETE FROM vendas WHERE deleted_at IS NOT NULL")
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API - Relatório geral em PDF (sem bibliotecas externas)
# ---------------------------------------------------------------------------
def _pdf_escape(t):
    return (t or "").replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def gerar_pdf_relatorio(linhas_dados, gerado_em, resumo):
    PAGE_W, PAGE_H = 842, 595
    cols = [("Cliente", 40), ("Perfume", 200), ("Qtd", 330), ("Valor", 380),
            ("Compra", 460), ("Forma", 560), ("Status", 660)]
    larguras = {"Cliente": 26, "Perfume": 22, "Forma": 12, "Status": 12}
    por_pagina = 22
    paginas = [linhas_dados[i:i + por_pagina]
               for i in range(0, len(linhas_dados), por_pagina)] or [[]]
    total_pag = len(paginas)

    def conteudo(linhas_pg, idx):
        partes = [
            "BT /F2 18 Tf 1 0 0 1 40 555 Tm (Relatorio Geral de Vendas) Tj ET",
            f"BT /F1 10 Tf 1 0 0 1 40 537 Tm (Essence - Gestao de Perfumes   |   Gerado em {_pdf_escape(gerado_em)}) Tj ET",
            "0.6 0.6 0.6 RG 1 w 40 528 m 802 528 l S",
        ]
        if idx == 0:
            partes.append(f"BT /F2 11 Tf 1 0 0 1 40 512 Tm ({_pdf_escape(resumo)}) Tj ET")
            cabec_y, y = 492, 474
        else:
            cabec_y, y = 512, 494
        partes.append("1 0.55 0 rg")
        for nome, x in cols:
            partes.append(f"BT /F2 10 Tf 1 0 0 1 {x} {cabec_y} Tm ({_pdf_escape(nome)}) Tj ET")
        partes.append("0 0 0 rg")
        partes.append(f"0.8 0.8 0.8 RG 0.5 w 40 {cabec_y - 6} m 802 {cabec_y - 6} l S")
        for linha in linhas_pg:
            for (nome, x), cel in zip(cols, linha):
                lim = larguras.get(nome, 14)
                txt = cel if len(cel) <= lim else cel[:lim - 1] + "…"
                partes.append(f"BT /F1 9 Tf 1 0 0 1 {x} {y} Tm ({_pdf_escape(txt)}) Tj ET")
            y -= 19
        partes.append(f"BT /F1 8 Tf 1 0 0 1 40 25 Tm (Pagina {idx + 1} de {total_pag}) Tj ET")
        return "\n".join(partes)

    objetos = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    }
    kids, num = [], 5
    for idx, linhas_pg in enumerate(paginas):
        cont_num, page_num = num, num + 1
        num += 2
        kids.append(f"{page_num} 0 R")
        objetos[cont_num] = ("__STREAM__", conteudo(linhas_pg, idx).encode("cp1252", "replace"))
        objetos[page_num] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {cont_num} 0 R >>")
    objetos[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(paginas)} >>"

    buf = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for n in sorted(objetos):
        offsets[n] = len(buf)
        corpo = objetos[n]
        buf += f"{n} 0 obj\n".encode("latin-1")
        if isinstance(corpo, tuple):
            stream = corpo[1]
            buf += f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            buf += stream + b"\nendstream"
        else:
            buf += corpo.encode("latin-1")
        buf += b"\nendobj\n"
    xref_pos = len(buf)
    maxn = max(objetos) + 1
    buf += f"xref\n0 {maxn}\n".encode("latin-1")
    buf += b"0000000000 65535 f \n"
    for n in range(1, maxn):
        buf += f"{offsets.get(n, 0):010d} 00000 n \n".encode("latin-1")
    buf += (f"trailer\n<< /Size {maxn} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF").encode("latin-1")
    return bytes(buf)


@app.route("/api/relatorio.pdf", methods=["GET"])
def relatorio_pdf():
    db = get_db()
    rows = db.execute(
        "SELECT v.nome_cliente, v.forma_pagamento, v.status, i.perfume_nome, "
        "i.quantidade, i.valor, i.data_compra "
        "FROM venda_itens i JOIN vendas v ON v.id = i.venda_id "
        "WHERE v.deleted_at IS NULL "
        "ORDER BY v.nome_cliente COLLATE NOCASE, i.data_compra").fetchall()

    linhas = []
    total = 0
    for r in rows:
        total += r["valor"] or 0
        linhas.append([
            r["nome_cliente"] or "", r["perfume_nome"] or "-",
            str(r["quantidade"] or 1), _moeda_compacta(r["valor"]),
            _data_br(r["data_compra"]), r["forma_pagamento"] or "", r["status"] or "",
        ])
    resumo = f"Total de itens vendidos: {len(rows)}    Valor total: {_moeda_compacta(total)}"
    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf = gerar_pdf_relatorio(linhas, gerado_em, resumo)
    nome = "relatorio_geral_" + datetime.now().strftime("%Y-%m-%d") + ".pdf"
    return send_file(io.BytesIO(pdf), as_attachment=True, download_name=nome,
                     mimetype="application/pdf")


# ---------------------------------------------------------------------------
# API - Backup / Restauração
# ---------------------------------------------------------------------------
@app.route("/api/backup", methods=["GET"])
def backup():
    if not os.path.exists(DB_PATH):
        abort(404, description="Banco de dados não encontrado.")
    nome = "essence_backup_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".db"
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    tmp_path = os.path.join(BACKUPS_DIR, nome)
    src = sqlite3.connect(DB_PATH)
    disk = sqlite3.connect(tmp_path)
    src.backup(disk)
    disk.close()
    src.close()
    with open(tmp_path, "rb") as f:
        buf = io.BytesIO(f.read())
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=nome,
                     mimetype="application/octet-stream")


@app.route("/api/restore", methods=["POST"])
def restore():
    if "arquivo" not in request.files:
        abort(400, description="Nenhum arquivo enviado.")
    file = request.files["arquivo"]
    if not file.filename:
        abort(400, description="Nenhum arquivo selecionado.")
    conteudo = file.read()
    if not conteudo.startswith(b"SQLite format 3"):
        abort(400, description="O arquivo não é um backup válido do sistema.")
    if os.path.exists(DB_PATH):
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        seguranca = os.path.join(
            BACKUPS_DIR, "antes_de_restaurar_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".db")
        with open(DB_PATH, "rb") as orig, open(seguranca, "wb") as dst:
            dst.write(orig.read())
    with open(DB_PATH, "wb") as f:
        f.write(conteudo)
    try:
        test = sqlite3.connect(DB_PATH)
        test.execute("SELECT COUNT(*) FROM perfumes")
        test.close()
    except sqlite3.Error:
        abort(400, description="O arquivo enviado não pôde ser aberto como banco.")
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Tratamento de erros -> sempre JSON nas rotas /api
# ---------------------------------------------------------------------------
@app.errorhandler(400)
@app.errorhandler(404)
def handle_error(err):
    return jsonify({"erro": getattr(err, "description", str(err))}), err.code


if __name__ == "__main__":
    init_db()
    porta = int(os.environ.get("ESSENCE_PORT", "8000"))
    print("=" * 55)
    print("  Sistema Essence iniciado!")
    print(f"  Abra no navegador:  http://127.0.0.1:{porta}")
    print("  Para encerrar, feche esta janela.")
    print("=" * 55)
    app.run(host="127.0.0.1", port=porta, debug=False)
