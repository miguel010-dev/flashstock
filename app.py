# -*- coding: utf-8 -*-
"""
Flash Stock — Móveis Planejados
Backend Flask + SQLite (sem ORM externo, apenas sqlite3 da stdlib)
"""
import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory, flash, jsonify, abort
)
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "flashstock.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "gif"}

ADMIN_EMAIL = "flashtock@gmail.com"
ADMIN_SENHA = "@Batatas123"

CATEGORIAS = [
    "Cozinha", "Closet", "Dormitório", "Home Office",
    "Sala de Estar", "Banheiro", "Área de Serviço", "Comercial"
]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASHSTOCK_SECRET", "flashstock-" + uuid.uuid4().hex)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB por requisição

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        categoria TEXT NOT NULL,
        descricao TEXT DEFAULT '',
        material TEXT DEFAULT '',
        acabamento TEXT DEFAULT '',
        largura_min REAL DEFAULT 0,
        largura_max REAL DEFAULT 0,
        altura_min REAL DEFAULT 0,
        altura_max REAL DEFAULT 0,
        profundidade_min REAL DEFAULT 0,
        profundidade_max REAL DEFAULT 0,
        preco_estimado REAL,
        prazo_producao_dias INTEGER,
        destaque INTEGER DEFAULT 0,
        ativo INTEGER DEFAULT 1,
        criado_em TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS imagens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        ordem INTEGER DEFAULT 0,
        FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
    );
    """)
    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def salvar_imagens(files, produto_id):
    """Salva arquivos enviados e retorna lista de filenames salvos."""
    salvos = []
    for f in files:
        if not f or not f.filename:
            continue
        if not allowed_file(f.filename):
            continue
        ext = f.filename.rsplit(".", 1)[1].lower()
        nome_seguro = f"{produto_id}_{uuid.uuid4().hex}.{ext}"
        caminho = os.path.join(UPLOAD_FOLDER, nome_seguro)
        f.save(caminho)
        salvos.append(nome_seguro)
    return salvos


def produto_para_dict(row):
    return dict(row)


def to_float(valor, default=0.0):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return default


def to_int_or_none(valor):
    try:
        v = int(valor)
        return v
    except (TypeError, ValueError):
        return None


def to_float_or_none(valor):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


@app.context_processor
def inject_globals():
    return {"ano": datetime.now().year}


# ---------------------------------------------------------------------------
# Rotas públicas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/sobre")
def sobre():
    return render_template("sobre.html")


@app.route("/catalogo")
def catalogo():
    categoria = request.args.get("categoria", "").strip()
    conn = get_db()
    if categoria:
        rows = conn.execute(
            "SELECT * FROM produtos WHERE ativo = 1 AND categoria = ? ORDER BY destaque DESC, criado_em DESC",
            (categoria,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM produtos WHERE ativo = 1 ORDER BY destaque DESC, criado_em DESC"
        ).fetchall()

    produtos = []
    for r in rows:
        p = dict(r)
        capa = conn.execute(
            "SELECT filename FROM imagens WHERE produto_id = ? ORDER BY ordem ASC, id ASC LIMIT 1",
            (p["id"],)
        ).fetchone()
        p["capa"] = capa["filename"] if capa else None
        produtos.append(p)
    conn.close()

    return render_template(
        "catalogo.html",
        produtos=produtos,
        categorias=CATEGORIAS,
        categoria_atual=categoria
    )


@app.route("/catalogo/produto/<int:produto_id>")
def produto_detalhe(produto_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM produtos WHERE id = ? AND ativo = 1", (produto_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)
    produto = dict(row)
    imagens = conn.execute(
        "SELECT * FROM imagens WHERE produto_id = ? ORDER BY ordem ASC, id ASC", (produto_id,)
    ).fetchall()

    relacionados_rows = conn.execute(
        "SELECT * FROM produtos WHERE ativo = 1 AND categoria = ? AND id != ? ORDER BY criado_em DESC LIMIT 3",
        (produto["categoria"], produto_id)
    ).fetchall()
    relacionados = []
    for r in relacionados_rows:
        rp = dict(r)
        capa = conn.execute(
            "SELECT filename FROM imagens WHERE produto_id = ? ORDER BY ordem ASC, id ASC LIMIT 1",
            (rp["id"],)
        ).fetchone()
        rp["capa"] = capa["filename"] if capa else None
        relacionados.append(rp)
    conn.close()

    return render_template("produto.html", produto=produto, imagens=imagens, relacionados=relacionados)


@app.errorhandler(404)
def pagina_nao_encontrada(e):
    return render_template("catalogo.html", produtos=[], categorias=CATEGORIAS, categoria_atual=""), 404


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logado"):
        return redirect(url_for("cadastro"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        if email == ADMIN_EMAIL.lower() and senha == ADMIN_SENHA:
            session["admin_logado"] = True
            return redirect(url_for("cadastro"))
        return render_template("login.html", erro="E-mail ou senha inválidos.")

    return render_template("login.html", erro=None)


@app.route("/logout")
def logout():
    session.pop("admin_logado", None)
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Painel administrativo — cadastro de móveis planejados
# ---------------------------------------------------------------------------
@app.route("/cadastro")
@login_required
def cadastro():
    conn = get_db()
    rows = conn.execute("SELECT * FROM produtos ORDER BY criado_em DESC").fetchall()
    produtos = []
    for r in rows:
        p = dict(r)
        capa = conn.execute(
            "SELECT filename FROM imagens WHERE produto_id = ? ORDER BY ordem ASC, id ASC LIMIT 1",
            (p["id"],)
        ).fetchone()
        p["capa"] = capa["filename"] if capa else None
        produtos.append(p)
    conn.close()
    return render_template("cadastro.html", produtos=produtos, categorias=CATEGORIAS, produto_edicao=None, imagens_edicao=[])


@app.route("/cadastro/produto/<int:produto_id>/editar")
@login_required
def cadastro_editar_form(produto_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)
    produto_edicao = dict(row)
    imagens_edicao = conn.execute(
        "SELECT * FROM imagens WHERE produto_id = ? ORDER BY ordem ASC, id ASC", (produto_id,)
    ).fetchall()

    rows_all = conn.execute("SELECT * FROM produtos ORDER BY criado_em DESC").fetchall()
    produtos = []
    for r in rows_all:
        p = dict(r)
        capa = conn.execute(
            "SELECT filename FROM imagens WHERE produto_id = ? ORDER BY ordem ASC, id ASC LIMIT 1",
            (p["id"],)
        ).fetchone()
        p["capa"] = capa["filename"] if capa else None
        produtos.append(p)
    conn.close()

    return render_template(
        "cadastro.html", produtos=produtos, categorias=CATEGORIAS,
        produto_edicao=produto_edicao, imagens_edicao=imagens_edicao
    )


def _ler_dados_formulario(form):
    return {
        "nome": (form.get("nome") or "").strip(),
        "categoria": (form.get("categoria") or CATEGORIAS[0]).strip(),
        "descricao": (form.get("descricao") or "").strip(),
        "material": (form.get("material") or "").strip(),
        "acabamento": (form.get("acabamento") or "").strip(),
        "largura_min": to_float(form.get("largura_min"), 0),
        "largura_max": to_float(form.get("largura_max"), 0),
        "altura_min": to_float(form.get("altura_min"), 0),
        "altura_max": to_float(form.get("altura_max"), 0),
        "profundidade_min": to_float(form.get("profundidade_min"), 0),
        "profundidade_max": to_float(form.get("profundidade_max"), 0),
        "preco_estimado": to_float_or_none(form.get("preco_estimado")),
        "prazo_producao_dias": to_int_or_none(form.get("prazo_producao_dias")),
        "destaque": 1 if form.get("destaque") == "on" else 0,
        "ativo": 1 if form.get("ativo") == "on" else 0,
    }


@app.route("/cadastro/novo", methods=["POST"])
@login_required
def cadastro_novo():
    dados = _ler_dados_formulario(request.form)
    if not dados["nome"]:
        flash("O nome do produto é obrigatório.", "error")
        return redirect(url_for("cadastro"))

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO produtos (
            nome, categoria, descricao, material, acabamento,
            largura_min, largura_max, altura_min, altura_max,
            profundidade_min, profundidade_max, preco_estimado,
            prazo_producao_dias, destaque, ativo, criado_em
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        dados["nome"], dados["categoria"], dados["descricao"], dados["material"], dados["acabamento"],
        dados["largura_min"], dados["largura_max"], dados["altura_min"], dados["altura_max"],
        dados["profundidade_min"], dados["profundidade_max"], dados["preco_estimado"],
        dados["prazo_producao_dias"], dados["destaque"], dados["ativo"], datetime.now().isoformat()
    ))
    produto_id = cur.lastrowid

    arquivos = request.files.getlist("imagens")
    salvos = salvar_imagens(arquivos, produto_id)
    for ordem, filename in enumerate(salvos):
        conn.execute("INSERT INTO imagens (produto_id, filename, ordem) VALUES (?,?,?)", (produto_id, filename, ordem))

    conn.commit()
    conn.close()
    flash("Produto cadastrado com sucesso!", "success")
    return redirect(url_for("cadastro"))


@app.route("/cadastro/produto/<int:produto_id>/editar", methods=["POST"])
@login_required
def cadastro_editar(produto_id):
    conn = get_db()
    existente = conn.execute("SELECT id FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if not existente:
        conn.close()
        abort(404)

    dados = _ler_dados_formulario(request.form)
    if not dados["nome"]:
        conn.close()
        flash("O nome do produto é obrigatório.", "error")
        return redirect(url_for("cadastro_editar_form", produto_id=produto_id))

    conn.execute("""
        UPDATE produtos SET
            nome=?, categoria=?, descricao=?, material=?, acabamento=?,
            largura_min=?, largura_max=?, altura_min=?, altura_max=?,
            profundidade_min=?, profundidade_max=?, preco_estimado=?,
            prazo_producao_dias=?, destaque=?, ativo=?
        WHERE id=?
    """, (
        dados["nome"], dados["categoria"], dados["descricao"], dados["material"], dados["acabamento"],
        dados["largura_min"], dados["largura_max"], dados["altura_min"], dados["altura_max"],
        dados["profundidade_min"], dados["profundidade_max"], dados["preco_estimado"],
        dados["prazo_producao_dias"], dados["destaque"], dados["ativo"], produto_id
    ))

    # remover imagens marcadas
    excluir_ids = request.form.getlist("excluir_imagem")
    for img_id in excluir_ids:
        img = conn.execute("SELECT * FROM imagens WHERE id = ? AND produto_id = ?", (img_id, produto_id)).fetchone()
        if img:
            caminho = os.path.join(UPLOAD_FOLDER, img["filename"])
            if os.path.exists(caminho):
                os.remove(caminho)
            conn.execute("DELETE FROM imagens WHERE id = ?", (img_id,))

    # adicionar novas imagens
    arquivos = request.files.getlist("imagens")
    maior_ordem = conn.execute(
        "SELECT COALESCE(MAX(ordem), -1) AS m FROM imagens WHERE produto_id = ?", (produto_id,)
    ).fetchone()["m"]
    salvos = salvar_imagens(arquivos, produto_id)
    for i, filename in enumerate(salvos):
        conn.execute("INSERT INTO imagens (produto_id, filename, ordem) VALUES (?,?,?)", (produto_id, filename, maior_ordem + 1 + i))

    conn.commit()
    conn.close()
    flash("Produto atualizado com sucesso!", "success")
    return redirect(url_for("cadastro"))


@app.route("/cadastro/produto/<int:produto_id>/excluir", methods=["POST"])
@login_required
def cadastro_excluir(produto_id):
    conn = get_db()
    imagens = conn.execute("SELECT filename FROM imagens WHERE produto_id = ?", (produto_id,)).fetchall()
    for img in imagens:
        caminho = os.path.join(UPLOAD_FOLDER, img["filename"])
        if os.path.exists(caminho):
            os.remove(caminho)
    conn.execute("DELETE FROM imagens WHERE produto_id = ?", (produto_id,))
    conn.execute("DELETE FROM produtos WHERE id = ?", (produto_id,))
    conn.commit()
    conn.close()
    flash("Produto excluído.", "success")
    return redirect(url_for("cadastro"))


@app.route("/cadastro/produto/<int:produto_id>/toggle-ativo", methods=["POST"])
@login_required
def cadastro_toggle_ativo(produto_id):
    conn = get_db()
    row = conn.execute("SELECT ativo FROM produtos WHERE id = ?", (produto_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)
    novo = 0 if row["ativo"] else 1
    conn.execute("UPDATE produtos SET ativo=? WHERE id=?", (novo, produto_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "ativo": novo})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
