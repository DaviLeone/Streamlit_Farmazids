import base64
import hashlib
import html
import inspect
import io
import json
import re
import secrets
import sqlite3
import textwrap
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import altair as alt
import boto3
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# --- CONFIGURAÇÕES AWS ---
STATE_MACHINE_ARN = "arn:aws:states:us-east-2:906513713169:stateMachine:farmazids-t1-equipe-06-bedrockV2"
REGIAO = "us-east-2"
# -------------------------

# --- CONFIGURAÇÃO DE CAMINHOS RELATIVOS PARA O GITHUB ---
BASE = Path(__file__).resolve().parent
DB = BASE / "farmazids.db"
LOGO = BASE / "logo.png"          # Logo retangular na raiz
EMBLEMA = BASE / "emblema.png"    # Emblema redondo na raiz

USUARIO_OK = re.compile(r"^[a-z0-9_.-]{3,30}$")
RECENTES_LIMIT = 5    # Limite máximo de conversas no menu lateral
MAX_LINHAS = 200      # Linhas exibidas na tabela da tela

# Paleta de Cores Farmazids e Mapeamento Específico de Farmácias
ROXO, DOURADO, CINZA, FUNDO, LILAS = "#42205A", "#C9AD7A", "#C9D0DA", "#FBF9F4", "#D8C3EE"

FARMA_CORES = {
    "veracruz": "#DC2626",      # Vermelho
    "farmaponte": "#2563EB",    # Azul
    "farmazids": "#42205A",     # Roxo Farmazids
}
CORES_EXTRA = ["#10B981", "#F97316", "#C9AD7A", "#0D9488", "#6366F1", "#EC4899", "#8B5CF6"]


def cor_farmacia(nome_farmacia):
    if not nome_farmacia:
        return None
    s = str(nome_farmacia).strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    for key, color in FARMA_CORES.items():
        if key in s:
            return color
    return None


def mapa_cores_farmacias(lista_farmacias):
    domain = []
    range_colors = []
    idx_extra = 0
    for f in lista_farmacias:
        domain.append(f)
        c = cor_farmacia(f)
        if not c:
            c = CORES_EXTRA[idx_extra % len(CORES_EXTRA)]
            idx_extra += 1
        range_colors.append(c)
    return domain, range_colors


def fmt_br(val):
    if val is None or np.isnan(val):
        return "—"
    if abs(val) >= 1000:
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{val:,.2f}".replace(".", ",")


def _esticar(fn):
    return {"width": "stretch"} if "width" in inspect.signature(fn).parameters else {"use_container_width": True}


ESTICAR = _esticar(st.button)
ESTICAR_FORM = _esticar(st.form_submit_button)
ESTICAR_ALT = _esticar(st.altair_chart)

# ---------------------------------------------------------------- ESTILO CSS
PRIM = [
    '.stButton button[kind="primary"]',
    '[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]',
    '[data-testid="stBaseButton-primary"]',
    '[data-testid="stBaseButton-primaryFormSubmit"]',
]

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Cinzel:wght@600;700&display=swap');

:root { 
    --roxo:#42205A; 
    --roxo-hover:#311644;
    --dourado:#C9AD7A; 
    --cinza:#E5E8EB; 
    --fundo:#F8F9FA; 
    --lilas:#E8DFFA;
    --texto:#1E1E24; 
    --mudo:#667085; 
    --borda:#EAECF0; 
    --sombra: 0 4px 20px -2px rgba(16, 24, 40, 0.05);
}

/* Remoção das setas nativas do Streamlit na Sidebar e desativação do controle */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* Background & Tipografia Geral Gemini-style */
.stApp { background-color:var(--fundo) !important; color:var(--texto) !important; }
.stApp, .stApp p, .stApp label, .stApp input, .stApp button, .stApp li, .stApp td, .stApp th, .stApp textarea { 
    font-family:'Plus Jakarta Sans', sans-serif !important; 
}
[data-testid="stToolbar"], [data-testid="stDecoration"], footer, [data-testid="InputInstructions"] { display:none !important; }
[data-testid="stHeader"] { background:transparent !important; }
.block-container { max-width:1100px; padding-top:1rem; padding-bottom:4rem; }

/* Títulos Clean e Elegantes */
.h1 { font-weight:800; font-size:2rem; line-height:1.25; color:var(--roxo) !important; margin:0; letter-spacing:-0.02em; }
.h1::after { content:""; display:block; width:36px; height:3px; border-radius:10px; background:var(--dourado); margin-top:.7rem; }
.h2 { font-weight:700; font-size:1.15rem; color:var(--roxo) !important; margin:0 0 .25rem; letter-spacing:-0.01em; }
.mudo { color:var(--mudo) !important; font-size:.92rem; line-height:1.6; margin:.4rem 0 1.4rem; }
.rot { color:var(--mudo) !important; font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; margin:1.8rem 0 .65rem; }
.pergunta { font-weight:700; font-size:1.3rem; line-height:1.35; color:var(--texto) !important; margin:1.4rem 0 .65rem; word-break:break-word; letter-spacing:-0.01em; }
.chip { display:inline-block; background:#F2EEFB; color:var(--roxo) !important; border-radius:100px; padding:.25rem .85rem; font-size:.78rem; font-weight:600; margin:0 .4rem .8rem 0; border:1px solid rgba(66,32,90,.08); }

/* Card da Resposta com Visual Gemini AI */
.st-key-resposta { 
    background:#ffffff !important; 
    border:1px solid var(--borda) !important; 
    border-radius:20px !important; 
    padding:1.8rem 2rem !important; 
    box-shadow:var(--sombra) !important; 
    margin-bottom:1.5rem !important; 
}
.st-key-resposta [data-testid="stMarkdownContainer"] :is(p, li, h1, h2, h3, h4, h5, h6, strong, em, span, a):not(.bot-nome) { 
    font-family:'Plus Jakarta Sans',sans-serif !important; 
    text-transform:none !important; 
    letter-spacing:normal !important; 
}
.st-key-resposta [data-testid="stMarkdownContainer"] :is(p, li, h1, h2, h3, h4, h5, h6) { 
    font-size:1.02rem !important; 
    font-weight:400 !important; 
    line-height:1.8 !important; 
    color:var(--texto) !important; 
    margin:0 0 .85rem !important; 
}
.st-key-resposta [data-testid="stMarkdownContainer"] :is(strong, b) { font-weight:700 !important; color:var(--roxo) !important; }

.bot-header { display:flex; align-items:center; gap:12px; margin-bottom:1.2rem; border-bottom:1px solid var(--borda); padding-bottom:.75rem; }
.bot-header img { width:32px; height:32px; border-radius:50%; }
.bot-header .bot-nome { font-weight:700; font-size:1.05rem; color:var(--roxo) !important; letter-spacing:-0.01em; }

/* Estados Vazios e Cards Informativos */
.vazio { background:#ffffff !important; border:1px solid var(--borda) !important; border-radius:20px; padding:2.5rem; margin-top:1.5rem; box-shadow:var(--sombra); }
.vazio .h2 { margin-bottom:.8rem; }
.dica { color:var(--mudo) !important; font-size:.95rem; line-height:1.65; padding-left:1.4rem; position:relative; margin:.6rem 0; }
.dica::before { content:""; position:absolute; left:0; top:.65em; width:.45rem; height:.45rem; border-radius:50%; background:var(--dourado); }
.troca { color:var(--mudo) !important; font-size:.9rem; text-align:center; margin:1.5rem 0 .5rem; }

/* Histórico Cards */
.hist-card { background:#ffffff !important; border:1px solid var(--borda) !important; border-radius:18px; padding:1.4rem 1.6rem; margin-bottom:1rem; box-shadow:var(--sombra); transition:transform .15s ease; }
.hist-pergunta { font-weight:700; font-size:1.05rem; color:var(--roxo) !important; margin-bottom:.3rem; letter-spacing:-0.01em; }
.hist-data { font-size:.78rem; color:var(--mudo) !important; margin-bottom:.75rem; font-weight:500; }
.hist-resposta { font-size:.92rem; color:var(--texto) !important; line-height:1.6; background:var(--fundo); padding:1rem 1.2rem; border-radius:12px; border:1px solid var(--borda); margin-bottom:.8rem; }

/* Inputs e Formulários */
[data-testid="stWidgetLabel"] p { color:var(--mudo) !important; font-size:.82rem; font-weight:600; text-transform:uppercase; letter-spacing:0.03em; }
div[data-baseweb="input"] { background:#ffffff !important; border:1px solid var(--borda) !important; border-radius:14px !important; box-shadow:0 1px 2px rgba(16, 24, 40, 0.05); transition:all 0.2s ease; }
div[data-baseweb="input"]:focus-within { border-color:var(--roxo) !important; box-shadow:0 0 0 4px rgba(66,32,90,0.08) !important; }
div[data-baseweb="base-input"] { background:transparent !important; }
[data-testid="stTextInput"] input { background:#ffffff !important; height:3.1rem; font-size:.98rem; color:var(--texto) !important; padding-left:1.1rem; }
[data-testid="stTextInput"] input::placeholder { color:#98A2B3 !important; }
[data-testid="stForm"] { background:#ffffff !important; border:1px solid var(--borda) !important; border-radius:24px; padding:1.6rem; box-shadow:var(--sombra); }

[data-testid="stExpander"] { display:none !important; }

/* Botões Modernos */
.stButton button, [data-testid="stFormSubmitButton"] button, [data-testid="stDownloadButton"] button { 
    border-radius:12px; 
    height:2.8rem; 
    border:1px solid var(--borda); 
    background:#ffffff !important; 
    transition:all .18s cubic-bezier(0.4, 0, 0.2, 1); 
    box-shadow:0 1px 2px rgba(16, 24, 40, 0.04);
}
.stButton button p, [data-testid="stFormSubmitButton"] button p, [data-testid="stDownloadButton"] button p { color:var(--texto) !important; font-weight:600; font-size:.88rem; }
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover, [data-testid="stDownloadButton"] button:hover { background:#F9F8FD !important; border-color:var(--roxo); }
{{PRIM}} { background:var(--roxo) !important; border-color:var(--roxo) !important; box-shadow:0 2px 5px rgba(66,32,90,0.18) !important; }
{{PRIM_P}} { color:#ffffff !important; font-weight:600 !important; }
{{PRIM_H}} { background:var(--roxo-hover) !important; border-color:var(--roxo-hover) !important; }

/* Foto do Perfil Aumentada */
.perfil-foto-circulo {
    width: 42px !important;
    height: 42px !important;
    border-radius: 50% !important;
    object-fit: cover !important;
    border: 2px solid var(--dourado) !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
    margin: 0 !important;
    display: block !important;
}

.box-foto-alinha {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    height: 100% !important;
}

/* Botão de Histórico com Destaque Discreto */
.btn-historico button {
    background: #F4EFFB !important;
    border: 1px solid var(--lilas) !important;
}
.btn-historico button p {
    color: var(--roxo) !important;
    font-weight: 700 !important;
}
.btn-historico button:hover {
    background: #E8DFFA !important;
}

/* Botão de Sair com Ícone */
.btn-sair-icone button {
    border: 1px solid var(--borda) !important;
    background: #ffffff !important;
    border-radius: 12px !important;
    padding: 0 0.6rem !important;
    transition: all 0.2s ease !important;
}
.btn-sair-icone button:hover {
    background: #FEF2F2 !important;
    border-color: #FCA5A5 !important;
}
.btn-sair-icone button p {
    color: #344054 !important;
    font-size: 1.1rem !important;
}
.btn-sair-icone button:hover p {
    color: #D92D20 !important;
}

/* Ajustes no Menu Lateral */
section[data-testid="stSidebar"] { 
    background:#ffffff !important; 
    border-right:1px solid var(--borda); 
    width:310px !important; 
    min-width:310px !important; 
}
[data-testid="stSidebar"] .stButton button[kind="secondary"] { 
    border:none; 
    background:transparent !important; 
    height:auto; 
    padding:.55rem .65rem; 
    justify-content:flex-start; 
    text-align:left; 
    border-radius:10px; 
    box-shadow:none; 
}
[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover { background:#F4EFFB !important; }

/* Formatação de 1 linha única para perguntas recentes */
.item-recente button p {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: block !important;
    max-width: 175px !important;
}

/* Tabela Estilizada Clean */
.tabela-wrap { overflow:auto; max-height:520px; background:#ffffff !important; border:1px solid var(--borda); border-radius:16px; margin:1rem 0 1.2rem; box-shadow:var(--sombra); }
.tabela { width:100%; border-collapse:separate; border-spacing:0; font-size:.88rem; }
.tabela th { position:sticky; top:0; z-index:1; background:#FAF9FC !important; color:var(--roxo) !important; text-align:left; font-weight:700; padding:.9rem 1.2rem; white-space:nowrap; border-bottom:1px solid var(--borda); }
.tabela td { padding:.8rem 1.2rem; border-bottom:1px solid var(--borda); color:var(--texto) !important; }
.tabela tbody tr:nth-child(even) td { background:#FCFCFD !important; }
.tabela tbody tr:hover td { background:#F4EFFB !important; }
.tabela tbody tr:last-child td { border-bottom:none; }
.tabela .num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.tabela a { color: var(--roxo) !important; font-weight: 600; text-decoration: underline; }
.tabela a:hover { color: var(--dourado) !important; }

/* Painel Lateral de Entrada (Login/Cadastro) */
.painel { background:linear-gradient(145deg, #42205A 0%, #2A133B 100%) !important; border-radius:28px; padding:3rem 2.5rem; min-height:640px; display:flex; flex-direction:column; justify-content:center; gap:1.8rem; box-shadow:0 12px 32px rgba(66,32,90,0.18); }
.painel-logo { background:#ffffff !important; border-radius:18px; border-bottom:4px solid var(--dourado); padding:1.2rem 1.8rem; max-width:340px; text-align:center; margin:0 auto; box-shadow:0 8px 16px rgba(0,0,0,0.12); }
.painel-t { font-weight:800; font-size:1.85rem; line-height:1.28; color:#ffffff !important; letter-spacing:-0.02em; }
.painel-p { color:var(--lilas) !important; font-size:1rem; line-height:1.7; max-width:38ch; opacity:0.95; }
.painel-i { color:#ffffff !important; font-size:.95rem; padding-left:1.5rem; position:relative; margin:.65rem 0; font-weight:500; }
.painel-i::before { content:""; position:absolute; left:0; top:.65em; width:.5rem; height:.5rem; border-radius:50%; background:var(--dourado); }

/* Logo na Sidebar */
.side-logo { 
    display: flex; 
    justify-content: center; 
    align-items: center; 
    text-align: center; 
    padding: 0.6rem 0 1rem 0; 
    border-bottom: 1px solid var(--borda); 
    margin-bottom: 1rem; 
}
.side-logo img { 
    margin: 0 auto !important; 
    display: block !important; 
}

.side-titulo { color:var(--mudo) !important; font-size:.72rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; padding:0 .6rem; margin:1.2rem 0 .4rem; }
.side-linha { border:0; border-top:1px solid var(--borda); margin:1rem 0 .6rem; }
</style>"""

CSS = (
    CSS.replace("{{PRIM}}", ",".join(PRIM))
    .replace("{{PRIM_P}}", ",".join(s + " p" for s in PRIM))
    .replace("{{PRIM_H}}", ",".join(s + ":hover" for s in PRIM))
)


# ---------------------------------------------------------------- BANCO DE DADOS (SQLITE)
@contextmanager
def conexao():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


@st.cache_resource
def iniciar_db():
    with conexao() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario TEXT PRIMARY KEY, nome TEXT NOT NULL,
                salt BLOB NOT NULL, hash BLOB NOT NULL, foto TEXT);
            CREATE TABLE IF NOT EXISTS perguntas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL,
                pergunta TEXT NOT NULL, resposta TEXT, linhas TEXT, sql TEXT,
                criada_em TEXT NOT NULL);
            """
        )
        try:
            con.execute("ALTER TABLE usuarios ADD COLUMN foto TEXT")
        except sqlite3.OperationalError:
            pass


def gerar_hash(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, 200_000)


def criar_usuario(nome, usuario, senha):
    salt = secrets.token_bytes(16)
    try:
        with conexao() as con:
            con.execute("INSERT INTO usuarios (usuario, nome, salt, hash, foto) VALUES (?,?,?,?,?)",
                        (usuario, nome, salt, gerar_hash(senha, salt), None))
        return True
    except sqlite3.IntegrityError:
        return False


def autenticar(usuario, senha):
    with conexao() as con:
        u = con.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
    if u and secrets.compare_digest(gerar_hash(senha, u["salt"]), u["hash"]):
        return u["nome"], u["foto"] if "foto" in u.keys() else None
    return None, None


def trocar_senha(usuario, senha):
    salt = secrets.token_bytes(16)
    with conexao() as con:
        con.execute("UPDATE usuarios SET salt=?, hash=? WHERE usuario=?", (salt, gerar_hash(senha, salt), usuario))


def salvar_foto(usuario, foto_b64):
    with conexao() as con:
        con.execute("UPDATE usuarios SET foto=? WHERE usuario=?", (foto_b64, usuario))


def remover_foto(usuario):
    with conexao() as con:
        con.execute("UPDATE usuarios SET foto=NULL WHERE usuario=?", (usuario,))


def atualizar_nome(usuario, novo_nome):
    with conexao() as con:
        con.execute("UPDATE usuarios SET nome=? WHERE usuario=?", (novo_nome, usuario))


def salvar_pergunta(usuario, pergunta, resposta, linhas, quando):
    with conexao() as con:
        con.execute(
            "INSERT INTO perguntas (usuario, pergunta, resposta, linhas, criada_em) VALUES (?,?,?,?,?)",
            (usuario, pergunta, resposta, json.dumps(linhas, ensure_ascii=False), quando),
        )


def deletar_pergunta(id_, usuario):
    with conexao() as con:
        con.execute("DELETE FROM perguntas WHERE id=? AND usuario=?", (id_, usuario))


def deletar_pergunta_callback(id_):
    deletar_pergunta(id_, st.session_state.usuario)
    res = st.session_state.get("resultado")
    if res and res.get("id") == id_:
        st.session_state.resultado = None


def listar_perguntas(usuario, limite=None):
    with conexao() as con:
        if limite:
            return con.execute(
                "SELECT id, pergunta, resposta, criada_em FROM perguntas WHERE usuario=? ORDER BY id DESC LIMIT ?", 
                (usuario, limite)
            ).fetchall()
        return con.execute(
            "SELECT id, pergunta, resposta, criada_em FROM perguntas WHERE usuario=? ORDER BY id DESC", 
            (usuario,)
        ).fetchall()


def total_perguntas(usuario):
    with conexao() as con:
        return con.execute("SELECT COUNT(*) FROM perguntas WHERE usuario=?", (usuario,)).fetchone()[0]


# ---------------------------------------------------------------- INTEGRAÇÃO AWS STEP FUNCTIONS
@st.cache_resource
def cliente_sfn():
    try:
        aws = st.secrets["aws"]
        return boto3.client(
            "stepfunctions",
            region_name=aws.get("region", REGIAO),
            aws_access_key_id=aws["access_key_id"],
            aws_secret_access_key=aws["secret_access_key"],
            aws_session_token=aws.get("session_token"),
        )
    except (KeyError, FileNotFoundError):
        return boto3.client("stepfunctions", region_name=REGIAO)


def consultar(pergunta):
    r = cliente_sfn().start_sync_execution(
        stateMachineArn=STATE_MACHINE_ARN, input=json.dumps({"pergunta": pergunta})
    )
    if r["status"] != "SUCCEEDED":
        raise RuntimeError(r.get("cause") or r.get("error") or r["status"])
    return json.loads(r["output"])


def erro_amigavel(e):
    t = str(e).lower()
    if "bedrock" in t or "503" in t or "serviceunavailable" in t:
        return "O serviço de Inteligência Artificial (Amazon Bedrock) está temporariamente em alta demanda. Por favor, tente novamente em instantes."
    if "credentials" in t:
        return "As credenciais da AWS não estão configuradas. Adicione-as em Settings → Secrets do app."
    if "accessdenied" in t or "not authorized" in t:
        return "A conta da AWS não tem permissão para executar esta consulta."
    return "Não foi possível concluir a consulta. Tente novamente em instantes."


# ---------------------------------------------------------------- HELPER DE LOGOS E GRÁFICOS
HINT_ID = re.compile(r"(^|_)(id|cod|codigo|código|gtin|ean|cnpj|cpf|cep|fone|telefone|sku|ncm)(_|$)", re.I)
HINT_ORDEM = re.compile(r"^(ano|year|mes|mês|month|dia|semana|trimestre)$", re.I)
BLOCOS = re.compile(r"[█▓▒░▇▆▅▄▃▂▁■]")
GRAFICO_TEXTO = re.compile(r"(?:^[ \t]*[#*\s]*Gr[áa]fico[^\n]*\n+)?^[ \t]*```[^\n]*\n(.*?)^[ \t]*```[ \t]*\n?", re.M | re.S)


@lru_cache(maxsize=None)
def img_b64(caminho):
    p = Path(caminho)
    if p.exists() and p.is_file():
        try:
            return base64.b64encode(p.read_bytes()).decode("utf-8")
        except Exception:
            return None
    return None


def logo_html(largura=200):
    b64 = img_b64(LOGO)
    if b64:
        return (f"<img class='logo' alt='Farmazids Medicina Oriental' style='width:{largura}px; height:auto; display:block; margin:0 auto;' "
                f"src='data:image/png;base64,{b64}'>")
    return "<div class='logo-txt' style='font-family:Cinzel,serif; font-weight:800; color:#42205A; font-size:1.5rem; text-align:center;'>FARMAZIDS</div>"


def emblema_html(largura=28):
    b64 = img_b64(EMBLEMA)
    if b64:
        return f"<img alt='Emblema' style='width:{largura}px; height:{largura}px; border-radius:50%; object-fit:cover;' src='data:image/png;base64,{b64}'>"
    return "🌿"


def esc(texto):
    return html.escape(str(texto)).replace("$", "&#36;")


def rotulo_col(c):
    s = str(c).replace("_", " ").strip()
    return s[:1].upper() + s[1:]


def limpar_resposta(texto):
    texto = GRAFICO_TEXTO.sub(lambda m: "" if BLOCOS.search(m.group(1)) else m.group(0), str(texto))
    texto = re.sub(r"^\s*#{1,6}\s*Resposta\s*:?\s*\n", "", texto, flags=re.I)
    return texto.replace("$", "\\$").strip()


def numerica(s):
    if s.dtype == bool or s.dropna().empty:
        return None
    if s.dtype == object or str(s.dtype).startswith("str"):
        if s.dropna().astype(str).str.match(r"^0\d").any():
            return None
    n = pd.to_numeric(s, errors="coerce")
    return n if n.notna().sum() >= 0.95 * s.notna().sum() else None


def colunas_numericas(df):
    out = {}
    for c in df.columns:
        if HINT_ID.search(str(c)):
            continue
        n = numerica(df[c])
        if n is None:
            continue
        v = n.dropna()
        if (v % 1 == 0).all() and v.min() >= 1e11:
            continue
        out[c] = n
    return out


def como_data(s):
    txt = s.astype(str)
    try:
        if txt.str.match(r"^\d{4}-\d{2}(-\d{2})?").all():
            d = pd.to_datetime(txt, errors="coerce", format="mixed")
        elif txt.str.match(r"^\d{2}/\d{2}/\d{4}").all():
            d = pd.to_datetime(txt, errors="coerce", dayfirst=True, format="mixed")
        else:
            return None
    except (TypeError, ValueError):
        return None
    return d if d.notna().all() else None


ADITIVA = re.compile(r"(quant|qtd|total|venda|valor|unidade|receita|faturamento|soma|preco|preço)", re.I)


def _dimensao(c, s, ja_numerica):
    if ja_numerica:
        return ("ordem", s) if HINT_ORDEM.match(str(c)) else (None, None)
    data = como_data(s)
    if data is not None:
        return "tempo", data
    if HINT_ID.search(str(c)):
        return None, None
    return "cat", s.astype(str)


def analisar(df):
    if len(df) < 2:
        return None

    # Detecta se há coluna de farmácia no DataFrame
    col_farmacia = None
    for c in df.columns:
        if re.search(r"(farmacia|farmácia|drogaria|estabelecimento|loja)", str(c), re.I):
            col_farmacia = c
            break

    nums = colunas_numericas(df)
    for c in df.columns:
        series = {}
        for m in nums:
            if m == c:
                continue
            
            if col_farmacia and col_farmacia != c and col_farmacia != m:
                sub = pd.DataFrame({
                    "cat": nums[c] if c in nums else df[c],
                    "farmacia": df[col_farmacia],
                    "val": nums[m]
                }).dropna()
            else:
                sub = pd.DataFrame({
                    "cat": nums[c] if c in nums else df[c],
                    "val": nums[m]
                }).dropna()

            if len(sub) < 2:
                continue
            tipo, cat = _dimensao(c, sub["cat"], c in nums)
            if tipo is None:
                continue
            sub["cat"] = cat

            if "farmacia" in sub.columns:
                if sub.duplicated(subset=["cat", "farmacia"]).any():
                    sub = sub.groupby(["cat", "farmacia"], as_index=False, sort=False)["val"].sum()
            else:
                agregado = not sub["cat"].is_unique
                if agregado:
                    if not ADITIVA.search(str(m)):
                        continue
                    sub = sub.groupby("cat", as_index=False, sort=False)["val"].sum()

            if not (2 <= len(sub) <= 350) or (tipo == "cat" and len(sub) > 180):
                continue
            
            series[m] = {
                "df": sub, 
                "tipo": tipo, 
                "agregado": "farmacia" in sub.columns or not sub["cat"].is_unique,
                "tem_farmacia": "farmacia" in sub.columns
            }

        if series:
            return {"dim": c, "series": series, "col_farmacia": col_farmacia}
            
    return None


def fmt_num(x, inteiro):
    if x is None or x != x:
        return "—"
    s = f"{int(round(x)):,}" if inteiro else f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def tabela_html(df):
    nums = colunas_numericas(df)
    inteiros = {c for c, n in nums.items() if (n.dropna() % 1 == 0).all()}
    recorte = df.head(MAX_LINHAS)
    colunas = []
    
    for c in df.columns:
        if c in nums:
            colunas.append([fmt_num(x, c in inteiros) for x in nums[c].head(MAX_LINHAS)])
        else:
            valores_formatados = []
            for x in recorte[c]:
                if x is None or x == "" or (isinstance(x, float) and x != x):
                    valores_formatados.append("—")
                elif str(c).lower() == "url_produto" or str(x).startswith("http"):
                    link = str(x)
                    valores_formatados.append(f"<a href='{esc(link)}' target='_blank' rel='noopener noreferrer'>Acessar Produto</a>")
                else:
                    valores_formatados.append(esc(x))
            colunas.append(valores_formatados)
            
    cab = "".join(f"<th class='{'num' if c in nums else ''}'>{esc(rotulo_col(c))}</th>" for c in df.columns)
    corpo = "".join(
        "<tr>" + "".join(
            f"<td class='{'num' if c in nums else ''}'>{v if ('<a href=' in v or v == '—') else v}</td>" for c, v in zip(df.columns, linha)
        ) + "</tr>"
        for linha in zip(*colunas)
    )
    return f"<div class='tabela-wrap'><table class='tabela'><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table></div>"


def gerar_tabela_png(df):
    recorte = df.head(30).copy()
    
    for col in recorte.columns:
        recorte[col] = recorte[col].astype(str).apply(lambda x: re.sub(r'<[^>]*>', '', str(x)))
    
    for col in recorte.columns:
        if 'url' in str(col).lower() or 'link' in str(col).lower():
            recorte[col] = recorte[col].apply(
                lambda x: "\n".join(textwrap.wrap(str(x), width=28, break_long_words=True, break_on_hyphens=True))
            )
        else:
            recorte[col] = recorte[col].apply(
                lambda x: "\n".join(textwrap.wrap(str(x), width=28)) if len(str(x)) > 28 else str(x)
            )

    col_names = [rotulo_col(c) for c in recorte.columns]
    table_data = [col_names] + recorte.values.tolist()
    num_cols = len(recorte.columns)

    col_widths = []
    for col in recorte.columns:
        c_lower = str(col).lower()
        if 'url' in c_lower:
            col_widths.append(0.35)
        elif 'nome' in c_lower or 'produto' in c_lower:
            col_widths.append(0.30)
        else:
            col_widths.append(0.12)
            
    total_w = sum(col_widths)
    col_widths = [w / total_w for w in col_widths]

    row_line_counts = []
    for row in table_data:
        max_lines_in_row = max(str(cell).count('\n') + 1 for cell in row)
        row_line_counts.append(max_lines_in_row)

    total_text_lines = sum(row_line_counts)
    
    fig_w = 16.0
    fig_h = max(4.0, total_text_lines * 0.45 + 1.0)
    
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
    fig.patch.set_facecolor('#FBF9F4')
    ax.axis('off')

    table = ax.table(
        cellText=table_data, 
        colWidths=col_widths,
        loc='center', 
        cellLoc='left'
    )
    table.auto_set_font_size(False)

    for row_idx, line_count in enumerate(row_line_counts):
        cell_height = (line_count / total_text_lines) * 0.92
        for col_idx in range(num_cols):
            cell = table[row_idx, col_idx]
            cell.set_height(cell_height)
            cell.set_fontsize(8.5)
            
            if row_idx == 0:
                cell.set_facecolor('#42205A')
                cell.set_text_props(color='#C9AD7A', weight='bold', ha='center', va='center')
            else:
                cell.set_facecolor('#FBF9F4' if row_idx % 2 == 0 else '#FFFFFF')
                cell.set_text_props(color='#2B2B2B', va='center')
            cell.set_edgecolor('#C9D0DA')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.2, dpi=200, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def gerar_grafico_png(d, dim, medida, forma, tipo, col_farmacia=None, farma_sel="Todas as Farmácias (Sobreposto)", modo_visao="Sobreposto"):
    d_plot = d.copy()
    t_cat, t_val = rotulo_col(dim), rotulo_col(medida)

    # Filtragem de farmácia individual se selecionada
    if farma_sel and farma_sel not in ["Todas as Farmácias (Sobreposto)", "Painéis Separados (Facet)"] and "farmacia" in d_plot.columns:
        d_plot = d_plot[d_plot["farmacia"] == farma_sel].copy()

    tem_farmacia_multisserie = ("farmacia" in d_plot.columns) and (d_plot["farmacia"].nunique() > 1) and (farma_sel in ["Todas as Farmácias (Sobreposto)", "Painéis Separados (Facet)"])

    # Determinar se a dimensão é categórica com nomes longos/muitos itens
    is_cat_longo = (tipo == "cat") or (d_plot["cat"].astype(str).str.len().max() > 12)
    
    # Rótulo bruto e lista de categorias
    d_plot['cat_str'] = d_plot['cat'].astype(str)

    # Limite para top N se houver muitos itens categóricos
    subtitulo_top = ""
    cats_totais = d_plot['cat_str'].unique()
    if is_cat_longo and len(cats_totais) > 20:
        top_cats = d_plot.groupby("cat_str")["val"].sum().nlargest(20).index.tolist()
        d_plot = d_plot[d_plot["cat_str"].isin(top_cats)].copy()
        cats_totais = top_cats
        subtitulo_top = " (Top 20 com Maiores Valores)"

    # Formatação dos rótulos
    if tipo == "tempo":
        so_mes = (pd.to_datetime(d_plot['cat'], errors='coerce').dt.day == 1).all() if not pd.to_datetime(d_plot['cat'], errors='coerce').isna().any() else False
        d_plot['rot_clean'] = pd.to_datetime(d_plot['cat'], errors='coerce').dt.strftime("%m/%Y" if so_mes else "%d/%m/%Y")
        d_plot['rot_clean'] = d_plot['rot_clean'].fillna(d_plot['cat_str'])
    else:
        d_plot['rot_clean'] = d_plot['cat_str']

    cats_unicas = d_plot['rot_clean'].unique()
    num_x = len(cats_unicas)

    # PAINÉIS SEPARADOS POR FARMÁCIA (FACET)
    if tem_farmacia_multisserie and modo_visao == "Painéis Separados (Facet)":
        farmacias = list(d_plot["farmacia"].unique())
        num_f = len(farmacias)

        if is_cat_longo:
            fig, axes = plt.subplots(num_f, 1, figsize=(11.5, max(4.0, num_x * 0.35) * num_f), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            if num_f == 1:
                axes = [axes]

            for idx, f in enumerate(farmacias):
                ax = axes[idx]
                ax.set_facecolor('#FFFFFF')
                sub = d_plot[d_plot["farmacia"] == f].sort_values("val", ascending=True)
                cor = cor_farmacia(f) or '#42205A'

                sub_clean = ["\n".join(textwrap.wrap(str(c), width=35)) for c in sub['rot_clean']]
                bars = ax.barh(sub_clean, sub['val'], color=cor, edgecolor='#FFFFFF', height=0.55)
                for bar in bars:
                    w = bar.get_width()
                    if w > 0:
                        ax.annotate(fmt_br(w), xy=(w, bar.get_y() + bar.get_height()/2),
                                    xytext=(5, 0), textcoords="offset points", ha='left', va='center',
                                    fontsize=7.5, fontweight='bold', color=cor)

                ax.set_title(f"Farmácia: {f}", fontsize=11, fontweight='bold', color=cor, loc='left')
                ax.set_xlabel(t_val, fontsize=9.5, color='#42205A', fontweight='bold')
                ax.grid(axis='x', linestyle='--', alpha=0.5, color='#C9D0DA')
                max_v = sub['val'].max() if not sub['val'].empty else 1
                ax.set_xlim(0, max_v * 1.22)

            fig.suptitle(f"Histórico de {t_val} por Farmácia - Comparativo Individual{subtitulo_top}", fontsize=13, fontweight='bold', color='#42205A', y=0.99)
            plt.tight_layout()

        else:
            fig, axes = plt.subplots(num_f, 1, figsize=(11.0, 3.5 * num_f), sharex=True, dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            if num_f == 1:
                axes = [axes]

            for idx, f in enumerate(farmacias):
                ax = axes[idx]
                ax.set_facecolor('#FFFFFF')
                sub = d_plot[d_plot["farmacia"] == f]
                cor = cor_farmacia(f) or '#42205A'

                if "Linhas" in forma:
                    ax.plot(sub['rot_clean'], sub['val'], color=cor, marker='o', linewidth=2.5, markersize=6, label=f)
                    for _, row in sub.iterrows():
                        ax.annotate(fmt_br(row['val']), xy=(row['rot_clean'], row['val']),
                                    xytext=(0, 5), textcoords="offset points", ha='center', va='bottom',
                                    fontsize=7.5, fontweight='bold', color=cor)
                else:
                    bars = ax.bar(sub['rot_clean'], sub['val'], color=cor, edgecolor='#FFFFFF', width=0.5)
                    for bar in bars:
                        h = bar.get_height()
                        ax.annotate(fmt_br(h), xy=(bar.get_x() + bar.get_width()/2, h),
                                    xytext=(0, 4), textcoords="offset points", ha='center', va='bottom',
                                    fontsize=7.5, fontweight='bold', color=cor)

                ax.set_title(f"Farmácia: {f}", fontsize=11, fontweight='bold', color=cor, loc='left')
                ax.set_ylabel(t_val, fontsize=9.5, color='#42205A', fontweight='bold')
                ax.grid(axis='y', linestyle='--', alpha=0.5, color='#C9D0DA')
                max_v = sub['val'].max() if not sub['val'].empty else 1
                ax.set_ylim(0, max_v * 1.25)

            axes[-1].tick_params(axis='x', rotation=30 if num_x > 5 else 0)
            fig.suptitle(f"Histórico de {t_val} por Farmácia - Comparativo Individual{subtitulo_top}", fontsize=13, fontweight='bold', color='#42205A', y=0.99)
            plt.tight_layout()

    # MULTISSÉRIE SOBREPOSTA
    elif tem_farmacia_multisserie:
        farmacias = list(d_plot["farmacia"].unique())

        if is_cat_longo and "Setores" not in forma:
            cats_ordenadas = d_plot.groupby("rot_clean")["val"].max().sort_values(ascending=True).index.tolist()
            num_cats = len(cats_ordenadas)
            num_f = len(farmacias)

            fig_h = max(5.5, num_cats * 0.45 + 1.5)
            fig_w = 12.0

            fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            ax.set_facecolor('#FFFFFF')

            y_indices = np.arange(num_cats)
            total_height = 0.75
            bar_h = total_height / num_f
            cats_clean = ["\n".join(textwrap.wrap(str(c), width=38)) for c in cats_ordenadas]

            for i, f in enumerate(farmacias):
                sub = d_plot[d_plot["farmacia"] == f]
                sub_dict = dict(zip(sub['rot_clean'], sub['val']))
                vals = [sub_dict.get(cat, 0) for cat in cats_ordenadas]
                pos = y_indices - (total_height / 2) + (i + 0.5) * bar_h
                cor = cor_farmacia(f) or '#42205A'

                bars = ax.barh(pos, vals, height=bar_h, label=f, color=cor, edgecolor='#FFFFFF', linewidth=0.8)
                for bar in bars:
                    w = bar.get_width()
                    if w > 0:
                        ax.annotate(fmt_br(w), xy=(w, bar.get_y() + bar.get_height() / 2),
                                    xytext=(5, 0), textcoords="offset points", ha='left', va='center',
                                    fontsize=7.5, fontweight='bold', color=cor)

            ax.set_yticks(y_indices)
            ax.set_yticklabels(cats_clean, fontsize=8.5, fontweight='500', color='#1E1E24')
            ax.set_title(f"Comparativo de {t_val} por {t_cat}{subtitulo_top}", fontsize=13, fontweight='bold', color='#42205A', pad=18)
            ax.set_xlabel(t_val, color='#42205A', fontweight='bold', fontsize=10.5)
            ax.grid(axis='x', linestyle='--', alpha=0.5, color='#C9D0DA')
            ax.legend(title="Farmácia", title_fontsize='9.5', fontsize='8.5', loc='upper right', frameon=True, facecolor='#FFFFFF', edgecolor='#C9D0DA')
            max_v = d_plot['val'].max() if not d_plot['val'].empty else 1
            ax.set_xlim(0, max_v * 1.20)

        elif "Linhas" in forma:
            fig_w = max(11.0, num_x * 0.85)
            fig_h = 6.0
            fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            ax.set_facecolor('#FFFFFF')

            for f in farmacias:
                sub = d_plot[d_plot["farmacia"] == f]
                cor = cor_farmacia(f) or '#42205A'
                ax.plot(sub['rot_clean'], sub['val'], color=cor, marker='o', label=f, linewidth=2.8, markersize=7)
                if num_x <= 15:
                    for _, row in sub.iterrows():
                        ax.annotate(fmt_br(row['val']), xy=(row['rot_clean'], row['val']),
                                    xytext=(0, 6), textcoords="offset points", ha='center', va='bottom',
                                    fontsize=8, fontweight='bold', color=cor)

            ax.set_title(f"Histórico de {t_val} por {t_cat} - Comparativo das Farmácias{subtitulo_top}", fontsize=13, fontweight='bold', color='#42205A', pad=18)
            ax.set_ylabel(t_val, color='#42205A', fontweight='bold', fontsize=10.5)
            ax.tick_params(axis='x', rotation=30 if num_x > 5 else 0, labelsize=9)
            ax.grid(axis='y', linestyle='--', alpha=0.5, color='#C9D0DA')
            ax.legend(title="Farmácia", title_fontsize='9.5', fontsize='8.5', loc='upper left', bbox_to_anchor=(1.02, 1), frameon=True, facecolor='#FFFFFF', edgecolor='#C9D0DA')
            max_v = d_plot['val'].max() if not d_plot['val'].empty else 1
            ax.set_ylim(0, max_v * 1.18)

        elif "Barras Empilhadas" in forma:
            sub_pivot = d_plot.pivot_table(index='rot_clean', columns='farmacia', values='val', aggfunc='sum').fillna(0)
            bottoms = np.zeros(len(sub_pivot))
            fig, ax = plt.subplots(figsize=(11.0, 6.0), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            ax.set_facecolor('#FFFFFF')

            for f in farmacias:
                if f in sub_pivot.columns:
                    vals = sub_pivot[f].values
                    cor = cor_farmacia(f) or '#42205A'
                    ax.bar(sub_pivot.index, vals, bottom=bottoms, label=f, color=cor, edgecolor='#FFFFFF', width=0.55)
                    bottoms += vals

            ax.set_title(f"Composição de {t_val} por {t_cat} (Empilhado){subtitulo_top}", fontsize=13, fontweight='bold', color='#42205A', pad=18)
            ax.set_ylabel(t_val, color='#42205A', fontweight='bold', fontsize=10.5)
            ax.tick_params(axis='x', rotation=30 if len(sub_pivot) > 5 else 0)
            ax.grid(axis='y', linestyle='--', alpha=0.5, color='#C9D0DA')
            ax.legend(title="Farmácia", title_fontsize='9.5', fontsize='8.5', loc='upper left', bbox_to_anchor=(1.02, 1), frameon=True, facecolor='#FFFFFF', edgecolor='#C9D0DA')

        elif "Setores" in forma:
            sub_farma = d_plot.groupby("farmacia", as_index=False)["val"].sum()
            cores = [cor_farmacia(f) or '#42205A' for f in sub_farma["farmacia"]]
            fig, ax = plt.subplots(figsize=(8.5, 6.0), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')

            wedges, texts, autotexts = ax.pie(
                sub_farma['val'], 
                labels=sub_farma['farmacia'], 
                autopct='%1.1f%%',
                startangle=140,
                colors=cores,
                textprops=dict(color="#42205A", fontsize=9, fontweight='bold'),
                pctdistance=0.75,
                wedgeprops=dict(width=0.4, edgecolor='#FBF9F4', linewidth=2)
            )
            for autotext in autotexts:
                autotext.set_color('#FFFFFF')
                autotext.set_fontsize(8.5)
                autotext.set_fontweight('bold')

            ax.set_title(f"Participação no Total de {t_val} por Farmácia", fontsize=13, fontweight='bold', color='#42205A', pad=18)

        else:
            x_indices = np.arange(len(cats_unicas))
            num_f = len(farmacias)
            total_width = 0.75
            bar_w = total_width / num_f
            fig, ax = plt.subplots(figsize=(max(11.0, num_x * 0.85), 6.0), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            ax.set_facecolor('#FFFFFF')

            for i, f in enumerate(farmacias):
                sub = d_plot[d_plot["farmacia"] == f]
                sub_dict = dict(zip(sub['rot_clean'], sub['val']))
                vals = [sub_dict.get(cat, 0) for cat in cats_unicas]
                pos = x_indices - (total_width / 2) + (i + 0.5) * bar_w
                cor = cor_farmacia(f) or '#42205A'
                bars = ax.bar(pos, vals, width=bar_w, label=f, color=cor, edgecolor='#FFFFFF', linewidth=0.8)
                if num_x <= 10:
                    for bar in bars:
                        h = bar.get_height()
                        if h > 0:
                            ax.annotate(fmt_br(h), xy=(bar.get_x() + bar.get_width()/2, h),
                                        xytext=(0, 4), textcoords="offset points", ha='center', va='bottom',
                                        fontsize=7.5, fontweight='bold', color=cor)

            ax.set_xticks(x_indices)
            ax.set_xticklabels([textwrap.fill(str(c), 15) for c in cats_unicas], rotation=30 if num_x > 5 else 0)
            ax.set_title(f"Comparativo de {t_val} por {t_cat}{subtitulo_top}", fontsize=13, fontweight='bold', color='#42205A', pad=18)
            ax.set_ylabel(t_val, color='#42205A', fontweight='bold', fontsize=10.5)
            ax.grid(axis='y', linestyle='--', alpha=0.5, color='#C9D0DA')
            ax.legend(title="Farmácia", title_fontsize='9.5', fontsize='8.5', loc='upper left', bbox_to_anchor=(1.02, 1), frameon=True, facecolor='#FFFFFF', edgecolor='#C9D0DA')
            max_v = d_plot['val'].max() if not d_plot['val'].empty else 1
            ax.set_ylim(0, max_v * 1.18)

    else:
        # Padrão para 1 farmácia ou categoria única
        cor_base = cor_farmacia(farma_sel) if farma_sel and farma_sel not in ["Todas as Farmácias (Sobreposto)", "Painéis Separados (Facet)"] else '#42205A'
        if not cor_base:
            cor_base = '#42205A'

        if is_cat_longo and "Setores" not in forma:
            sub = d_plot.sort_values("val", ascending=True)
            num_cats = len(sub)
            fig_h = max(5.0, num_cats * 0.42 + 1.5)
            fig, ax = plt.subplots(figsize=(11.5, fig_h), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            ax.set_facecolor('#FFFFFF')

            cats_clean = ["\n".join(textwrap.wrap(str(c), width=42)) for c in sub['rot_clean']]
            bars = ax.barh(cats_clean, sub['val'], color=cor_base, edgecolor='#C9AD7A', linewidth=1.0, height=0.55)
            for bar in bars:
                w = bar.get_width()
                if w > 0:
                    ax.annotate(fmt_br(w), xy=(w, bar.get_y() + bar.get_height() / 2),
                                xytext=(5, 0), textcoords="offset points", ha='left', va='center',
                                fontsize=8, fontweight='bold', color=cor_base)

            ax.set_xlabel(t_val, color='#42205A', fontweight='bold', fontsize=10.5)
            ax.set_title(f"{t_val} por {t_cat}{subtitulo_top}" + (f" ({farma_sel})" if farma_sel and "Todas" not in farma_sel else ""), fontsize=13, fontweight='bold', color='#42205A', pad=18)
            ax.grid(axis='x', linestyle='--', alpha=0.5, color='#C9D0DA')
            max_v = sub['val'].max() if not sub['val'].empty else 1
            ax.set_xlim(0, max_v * 1.20)

        else:
            fig, ax = plt.subplots(figsize=(10.0, 5.5), dpi=200)
            fig.patch.set_facecolor('#FBF9F4')
            ax.set_facecolor('#FFFFFF')

            if "Linhas" in forma:
                ax.plot(d_plot['rot_clean'], d_plot['val'], color=cor_base, marker='o', markerfacecolor='#C9AD7A', linewidth=2.8, markersize=7)
                if num_x <= 15:
                    for _, row in d_plot.iterrows():
                        ax.annotate(fmt_br(row['val']), xy=(row['rot_clean'], row['val']),
                                    xytext=(0, 6), textcoords="offset points", ha='center', va='bottom',
                                    fontsize=8, fontweight='bold', color=cor_base)
                ax.tick_params(axis='x', rotation=30 if num_x > 5 else 0)
                ax.set_title(f"Histórico de {t_val} por {t_cat}{subtitulo_top}" + (f" ({farma_sel})" if farma_sel and "Todas" not in farma_sel else ""), fontsize=13, fontweight='bold', color='#42205A', pad=18)
                ax.set_ylabel(t_val, color='#42205A', fontweight='bold', fontsize=10.5)
                ax.grid(axis='y', linestyle='--', alpha=0.5, color='#C9D0DA')
                max_v = d_plot['val'].max() if not d_plot['val'].empty else 1
                ax.set_ylim(0, max_v * 1.18)

            else:
                bars = ax.bar(d_plot['rot_clean'], d_plot['val'], color=cor_base, edgecolor='#C9AD7A', linewidth=1.2, width=0.55)
                max_val = d_plot['val'].max() if not d_plot['val'].empty else 1
                ax.set_ylim(0, max_val * 1.18)
                for bar in bars:
                    height = bar.get_height()
                    ax.annotate(fmt_br(height), xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 4), textcoords="offset points", ha='center', va='bottom', fontsize=8, color='#42205A', fontweight='bold')
                ax.tick_params(axis='x', rotation=30 if num_x > 5 else 0)
                ax.set_ylabel(t_val, color='#42205A', fontweight='bold', fontsize=10.5)
                ax.grid(axis='y', linestyle='--', alpha=0.5, color='#C9D0DA')
                ax.set_title(f"{t_val} por {t_cat}{subtitulo_top}" + (f" ({farma_sel})" if farma_sel and "Todas" not in farma_sel else ""), fontsize=13, fontweight='bold', color='#42205A', pad=18)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.3, dpi=200)
    plt.close()
    buf.seek(0)
    return buf.getvalue()


def grafico(info):
    dim, series = info["dim"], info["series"]
    medidas = list(series)
    
    d_raw = series[medidas[0]]["df"]
    tem_farmacia = "farmacia" in d_raw.columns
    farmacias_unicas = list(d_raw["farmacia"].unique()) if tem_farmacia else []
    tem_multi_farma = len(farmacias_unicas) > 1

    # MONTAGEM DINÂMICA DE COLUNAS SEM ESPAÇOS FANTASMA
    if tem_multi_farma and len(medidas) > 1:
        c1, c2, c3 = st.columns([1, 1.2, 1], vertical_alignment="bottom")
        medida = c1.selectbox("Valor exibido", medidas, format_func=rotulo_col)
        
        opts_farma = ["Todas as Farmácias (Sobreposto)", "Painéis Separados por Farmácia"] + [f"Somente {f}" for f in farmacias_unicas]
        farma_choice = c2.selectbox("Visão por Farmácia", opts_farma)
        
        opcoes_forma = ["Linhas (Histórico)", "Barras Agrupadas", "Barras Empilhadas", "Setores (Market Share)"]
        forma = c3.selectbox("Tipo de gráfico", opcoes_forma)

    elif tem_multi_farma:
        c1, c2 = st.columns([1.3, 1], vertical_alignment="bottom")
        medida = medidas[0]
        
        opts_farma = ["Todas as Farmácias (Sobreposto)", "Painéis Separados por Farmácia"] + [f"Somente {f}" for f in farmacias_unicas]
        farma_choice = c1.selectbox("Visão por Farmácia", opts_farma)
        
        opcoes_forma = ["Linhas (Histórico)", "Barras Agrupadas", "Barras Empilhadas", "Setores (Market Share)"]
        forma = c2.selectbox("Tipo de gráfico", opcoes_forma)

    elif len(medidas) > 1:
        c1, c2 = st.columns([1, 1], vertical_alignment="bottom")
        medida = c1.selectbox("Valor exibido", medidas, format_func=rotulo_col)
        farma_choice = "Todas as Farmácias (Sobreposto)"
        
        opcoes_forma = ["Linhas (Histórico)", "Barras Agrupadas", "Setores"]
        forma = c2.selectbox("Tipo de gráfico", opcoes_forma)

    else:
        c1, _ = st.columns([1, 1], vertical_alignment="bottom")
        medida = medidas[0]
        farma_choice = "Todas as Farmácias (Sobreposto)"
        
        opcoes_forma = ["Linhas (Histórico)", "Barras Agrupadas", "Setores"]
        forma = c1.selectbox("Tipo de gráfico", opcoes_forma)

    # TRADUÇÃO DA ESCOLHA DE FARMÁCIA
    if farma_choice == "Todas as Farmácias (Sobreposto)":
        farma_sel = "Todas as Farmácias (Sobreposto)"
        modo_visao = "Sobreposto"
    elif farma_choice == "Painéis Separados por Farmácia":
        farma_sel = "Painéis Separados (Facet)"
        modo_visao = "Painéis Separados (Facet)"
    elif farma_choice.startswith("Somente "):
        farma_sel = farma_choice.replace("Somente ", "")
        modo_visao = "Sobreposto"
    else:
        farma_sel = "Todas as Farmácias (Sobreposto)"
        modo_visao = "Sobreposto"

    d = series[medida]["df"].copy()
    tipo = series[medida]["tipo"]

    if series[medida]["agregado"]:
        st.markdown(f"<div class='nota'>Valores somados por {esc(rotulo_col(dim).lower())}.</div>", unsafe_allow_html=True)

    if farma_sel not in ["Todas as Farmácias (Sobreposto)", "Painéis Separados (Facet)"] and "farmacia" in d.columns:
        d_exib = d[d["farmacia"] == farma_sel].copy()
        tem_farmacia_multisserie = False
    else:
        d_exib = d.copy()
        tem_farmacia_multisserie = "farmacia" in d_exib.columns and d_exib["farmacia"].nunique() > 1

    if tipo == "cat":
        d_exib = d_exib.sort_values("val", ascending=True if len(d_exib) > 8 else False)
    else:
        d_exib = d_exib.sort_values("cat")

    t_cat, t_val = rotulo_col(dim), rotulo_col(medida)
    if tipo == "tempo":
        so_mes = (d_exib["cat"].dt.day == 1).all()
        d_exib["rot"] = d_exib["cat"].dt.strftime("%m/%Y" if so_mes else "%d/%m/%Y")
    else:
        d_exib["rot"] = d_exib["cat"].astype(str)

    rotacao_x = -45 if len(d_exib) > 6 or d_exib["rot"].str.len().max() > 8 else 0
    eixo_y = alt.Axis(grid=True, gridColor=CINZA, gridOpacity=0.6, domain=False, ticks=False)

    if tem_farmacia_multisserie and modo_visao == "Painéis Separados (Facet)":
        domain, range_colors = mapa_cores_farmacias(d_exib["farmacia"].unique())
        scale_cores = alt.Scale(domain=domain, range=range_colors)
        
        if "Linhas" in forma:
            graf = alt.Chart(d_exib).mark_line(
                strokeWidth=2.8, point=alt.OverlayMarkDef(filled=True, size=60)
            ).encode(
                x=alt.X("rot:O", title=None, axis=alt.Axis(labelAngle=rotacao_x)),
                y=alt.Y("val:Q", title=t_val, axis=eixo_y),
                color=alt.Color("farmacia:N", title="Farmácia", scale=scale_cores, legend=None),
                tooltip=[alt.Tooltip("farmacia:N", title="Farmácia"), alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]
            ).properties(width=850, height=180).facet(
                row=alt.Row("farmacia:N", title=None)
            )
        else:
            graf = alt.Chart(d_exib).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("rot:O", title=None, axis=alt.Axis(labelAngle=rotacao_x)),
                y=alt.Y("val:Q", title=t_val, axis=eixo_y),
                color=alt.Color("farmacia:N", title="Farmácia", scale=scale_cores, legend=None),
                tooltip=[alt.Tooltip("farmacia:N", title="Farmácia"), alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]
            ).properties(width=850, height=180).facet(
                row=alt.Row("farmacia:N", title=None)
            )

    elif tem_farmacia_multisserie:
        domain, range_colors = mapa_cores_farmacias(d_exib["farmacia"].unique())
        scale_cores = alt.Scale(domain=domain, range=range_colors)

        if "Linhas" in forma:
            x_enc = alt.X("cat:T", title=None, axis=alt.Axis(grid=False, labelAngle=rotacao_x, format="%m/%Y" if so_mes else "%d/%m", labelOverlap="greedy")) \
                    if tipo == "tempo" else alt.X("rot:O", title=None, axis=alt.Axis(grid=False, labelAngle=rotacao_x, labelOverlap="greedy"))
            graf = alt.Chart(d_exib).mark_line(
                strokeWidth=2.8, point=alt.OverlayMarkDef(filled=True, size=65)
            ).encode(
                x=x_enc,
                y=alt.Y("val:Q", title=t_val, axis=eixo_y),
                color=alt.Color("farmacia:N", title="Farmácia", scale=scale_cores),
                tooltip=[alt.Tooltip("farmacia:N", title="Farmácia"), alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]
            ).properties(height=400)

        elif "Barras Agrupadas" in forma or forma == "Barras":
            graf = alt.Chart(d_exib).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                x=alt.X("rot:N", title=None, axis=alt.Axis(labelAngle=rotacao_x, labelLimit=160, grid=False, domain=False, ticks=False)),
                y=alt.Y("val:Q", title=t_val, axis=eixo_y),
                xOffset="farmacia:N",
                color=alt.Color("farmacia:N", title="Farmácia", scale=scale_cores),
                tooltip=[alt.Tooltip("farmacia:N", title="Farmácia"), alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]
            ).properties(height=400)

        elif "Barras Empilhadas" in forma:
            graf = alt.Chart(d_exib).mark_bar().encode(
                x=alt.X("rot:N", title=None, axis=alt.Axis(labelAngle=rotacao_x, labelLimit=160, grid=False, domain=False, ticks=False)),
                y=alt.Y("val:Q", title=t_val, axis=eixo_y),
                color=alt.Color("farmacia:N", title="Farmácia", scale=scale_cores),
                tooltip=[alt.Tooltip("farmacia:N", title="Farmácia"), alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]
            ).properties(height=400)

        elif "Setores" in forma:
            graf = alt.Chart(d_exib).mark_arc(innerRadius=50, stroke="#fff").encode(
                theta=alt.Theta(field="val", type="quantitative"),
                color=alt.Color(field="farmacia", type="nominal", title="Farmácia", scale=scale_cores),
                tooltip=[alt.Tooltip("farmacia:N", title="Farmácia"), alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]
            ).properties(height=380)

    else:
        cat_farmacia_names = [cor_farmacia(x) for x in d_exib["rot"]]
        tem_cores_especificas = any(c is not None for c in cat_farmacia_names)
        
        cor_single = cor_farmacia(farma_sel) if farma_sel not in ["Todas as Farmácias (Sobreposto)", "Painéis Separados (Facet)"] else ROXO
        if not cor_single:
            cor_single = ROXO

        tip = [alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]

        if tem_cores_especificas:
            domain, range_colors = mapa_cores_farmacias(d_exib["rot"].unique())
            scale_cores = alt.Scale(domain=domain, range=range_colors)
            enc_color = alt.Color("rot:N", title=t_cat, scale=scale_cores, legend=None)
        else:
            enc_color = alt.value(cor_single)

        if "Linhas" in forma:
            x_enc = alt.X("cat:T", title=None, axis=alt.Axis(grid=False, labelAngle=rotacao_x, format="%m/%Y" if so_mes else "%d/%m", labelOverlap="greedy")) \
                    if tipo == "tempo" else alt.X("rot:O", title=None, axis=alt.Axis(grid=False, labelAngle=rotacao_x, labelOverlap="greedy"))
            graf = alt.Chart(d_exib).mark_line(
                color=cor_single, strokeWidth=2.8, point=alt.OverlayMarkDef(color=DOURADO, stroke=cor_single, filled=True, size=70)
            ).encode(x=x_enc, y=alt.Y("val:Q", title=t_val, axis=eixo_y), tooltip=tip).properties(height=380)

        elif "Setores" in forma:
            if tem_cores_especificas:
                graf = alt.Chart(d_exib).mark_arc(innerRadius=50, stroke="#fff").encode(
                    theta=alt.Theta(field="val", type="quantitative"),
                    color=enc_color,
                    tooltip=tip
                ).properties(height=380)
            else:
                graf = alt.Chart(d_exib).mark_arc(innerRadius=50, stroke="#fff").encode(
                    theta=alt.Theta(field="val", type="quantitative"),
                    color=alt.Color(field="rot", type="nominal", title=t_cat, scale=alt.Scale(scheme="purples")),
                    tooltip=tip
                ).properties(height=380)

        elif tipo == "cat" and (len(d_exib) > 8 or d_exib["rot"].str.len().max() > 16):
            graf = alt.Chart(d_exib).mark_bar(cornerRadiusEnd=4, size=18).encode(
                y=alt.Y("rot:N", sort=list(d_exib["rot"]), title=None, axis=alt.Axis(labelLimit=300, domain=False, ticks=False)),
                x=alt.X("val:Q", title=t_val, axis=alt.Axis(grid=True, gridColor=CINZA, gridOpacity=0.6, domain=False, ticks=False)),
                color=enc_color,
                tooltip=tip,
            ).properties(height=max(240, 32 * len(d_exib)))

        else:
            graf = alt.Chart(d_exib).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X("rot:N", sort=list(d_exib["rot"]), title=None, axis=alt.Axis(labelAngle=rotacao_x, labelLimit=160, grid=False, domain=False, ticks=False)),
                y=alt.Y("val:Q", title=t_val, axis=eixo_y),
                color=enc_color,
                tooltip=tip,
            ).properties(height=380)

    graf = graf.configure(font="Poppins", background="transparent").configure_view(stroke=None).configure_axis(
        labelColor="#5E4A70", titleColor=ROXO, labelFontSize=11, titleFontSize=12, titleFontWeight=600
    )
    st.altair_chart(graf, theme=None, **ESTICAR_ALT)

    col_dl1, col_dl2 = st.columns([1, 1])
    try:
        png_data = gerar_grafico_png(d, dim, medida, forma, tipo, col_farmacia=info.get("col_farmacia"), farma_sel=farma_sel, modo_visao=modo_visao)
        col_dl1.download_button(
            "Baixar Gráfico em PNG",
            data=png_data,
            file_name="grafico_farmazids.png",
            mime="image/png"
        )
    except Exception:
        pass

    try:
        html_str = graf.to_html()
        col_dl2.download_button(
            "Baixar Gráfico (HTML Interativo)",
            data=html_str,
            file_name="grafico_farmazids.html",
            mime="text/html"
        )
    except Exception:
        pass


# ---------------------------------------------------------------- NAVEGAÇÃO E HELPERS VISUAIS
def ir(pagina):
    st.session_state.pagina = pagina


def alternar_menu():
    st.session_state.menu_aberto = not st.session_state.get("menu_aberto", True)


@st.dialog("Confirmar Saída")
def modal_confirmar_saida():
    st.write("Tem certeza que deseja sair da sua conta?")
    c_sim, c_nao = st.columns(2)
    if c_sim.button("Sim, Sair", type="primary", use_container_width=True):
        sair_efetivo()
        st.rerun()
    if c_nao.button("Cancelar", use_container_width=True):
        st.rerun()


def solicitar_sair():
    modal_confirmar_saida()


def sair_efetivo():
    for k in ("usuario", "nome", "foto", "resultado"):
        st.session_state.pop(k, None)
    ir("login")


def nova_consulta():
    st.session_state.resultado = None
    st.session_state.consulta_pergunta = ""
    ir("consulta")


def abrir_pergunta(id_):
    with conexao() as con:
        p = con.execute("SELECT * FROM perguntas WHERE id=? AND usuario=?", (id_, st.session_state.usuario)).fetchone()
    if p:
        st.session_state.resultado = {
            "id": p["id"],
            "pergunta": p["pergunta"], "resposta": p["resposta"],
            "linhas": json.loads(p["linhas"] or "[]"), "quando": p["criada_em"],
        }
        ir("consulta")


def limpar_busca():
    st.session_state.consulta_pergunta = ""


def titulo(texto, subtitulo=""):
    st.markdown(f"<div class='h1'>{esc(texto)}</div><div class='mudo'>{esc(subtitulo)}</div>", unsafe_allow_html=True)


def aviso():
    msg = st.session_state.pop("aviso", None)
    if msg:
        getattr(st, msg[0])(msg[1])


def painel_marca():
    st.markdown(
        f"<div class='painel'><div class='painel-logo'>{logo_html(260)}</div>"
        "<div class='painel-t'>Consulta inteligente aos dados da Farmazids</div>"
        "<div class='painel-p'>Pergunte em linguagem natural e receba a resposta, a tabela e "
        "um gráfico na mesma página.</div>"
        "<div><div class='painel-i'>Perguntas em linguagem natural</div>"
        "<div class='painel-i'>Tabelas prontas para baixar em CSV e PNG</div>"
        "<div class='painel-i'>Gráficos gerados automaticamente em PNG</div>"
        "<div class='painel-i'>Suas últimas consultas sempre à mão</div></div></div>",
        unsafe_allow_html=True,
    )


def tela_dividida():
    esq, dir_ = st.columns([1, 1], gap="large")
    with esq:
        painel_marca()
    return dir_


def topo():
    c1, c2, c3 = st.columns([1, 4, 3.4], vertical_alignment="center")
    
    with c1:
        st.button("☰", key="btn_toggle_menu", help="Alternar menu lateral", on_click=alternar_menu)
        
    with c2:
        st.markdown(logo_html(190), unsafe_allow_html=True)
        
    with c3:
        nome = st.session_state.get("nome", "Usuário")
        foto = st.session_state.get("foto")
        
        raw_b64 = foto if foto else img_b64(EMBLEMA)
        if raw_b64:
            img_tag = f"<img class='perfil-foto-circulo' src='data:image/png;base64,{raw_b64}'>"
        else:
            letra = nome[:1].upper() if nome else "U"
            img_tag = f"<div class='perfil-foto-circulo' style='background:#42205A; color:#C9AD7A; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:1rem;'>{letra}</div>"
            
        col_perfil_bloco, col_sair = st.columns([3.5, 1], vertical_alignment="center")
        
        with col_perfil_bloco:
            col_foto, col_btn = st.columns([0.35, 0.65], vertical_alignment="center")
            with col_foto:
                st.markdown(f"<div class='box-foto-alinha'>{img_tag}</div>", unsafe_allow_html=True)
            with col_btn:
                st.button(nome, key="btn_topo_perfil", on_click=ir, args=("perfil",), use_container_width=True)
            
        with col_sair:
            st.markdown("<div class='btn-sair-icone'>", unsafe_allow_html=True)
            st.button("➔", key="btn_topo_sair", help="Sair da conta", on_click=solicitar_sair, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)


def menu_lateral():
    with st.sidebar:
        st.markdown(f"<div class='side-logo'>{logo_html(180)}</div>", unsafe_allow_html=True)
        st.button(" Nova consulta", key="nova", type="primary", on_click=nova_consulta, **ESTICAR)
        
        st.markdown("<div class='side-titulo'>Consultas recentes</div>", unsafe_allow_html=True)
        perguntas = listar_perguntas(st.session_state.usuario, limite=RECENTES_LIMIT)
        if not perguntas:
            st.markdown("<div class='side-vazio' style='color:var(--mudo); font-size:0.85rem; padding: 0.5rem 0.8rem;'>Suas perguntas aparecerão aqui.</div>", unsafe_allow_html=True)
        for p in perguntas:
            texto_bruto = p["pergunta"].strip()
            c_p, c_del = st.columns([0.80, 0.20], vertical_alignment="center")
            
            st.markdown("<div class='item-recente'>", unsafe_allow_html=True)
            c_p.button(texto_bruto, key=f"hist_{p['id']}", on_click=abrir_pergunta, args=(p["id"],), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            c_del.button("×", key=f"del_side_{p['id']}", help="Excluir consulta", on_click=deletar_pergunta_callback, args=(p["id"],), use_container_width=True)
        
        tot = total_perguntas(st.session_state.usuario)
        if tot > 0:
            st.button(" Histórico de consultas", key="ver_historico_completo", type="primary", on_click=ir, args=("historico",), **ESTICAR)

        st.markdown("<hr class='side-linha'>", unsafe_allow_html=True)
        st.button("Perfil", key="perfil", on_click=ir, args=("perfil",), **ESTICAR)
        
        st.markdown("<div class='btn-sair-icone'>", unsafe_allow_html=True)
        st.button("Sair", key="sair", on_click=solicitar_sair, **ESTICAR)
        st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- PÁGINAS DA APLICAÇÃO
def pagina_login():
    with tela_dividida():
        st.markdown("<div class='form-topo'></div>", unsafe_allow_html=True)
        titulo("Bem-vindo de volta", "Entre com seu usuário e senha para consultar os dados.")
        aviso()
        with st.form("form_login", border=False):
            usuario = st.text_input("Usuário", key="login_usuario", placeholder="Digite seu usuário")
            senha = st.text_input("Senha", key="login_senha", type="password", placeholder="Digite sua senha")
            entrar = st.form_submit_button("Entrar", type="primary", **ESTICAR_FORM)
        st.markdown("<div class='troca'>Ainda não tem conta?</div>", unsafe_allow_html=True)
        st.button("Criar conta", key="b_criar", on_click=ir, args=("cadastro",), **ESTICAR)

    if entrar:
        usuario = usuario.strip().lower()
        nome, foto = autenticar(usuario, senha)
        if nome:
            st.session_state.update(usuario=usuario, nome=nome, foto=foto, resultado=None, menu_aberto=True)
            ir("consulta")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")


def pagina_cadastro():
    with tela_dividida():
        st.markdown("<div class='form-topo'></div>", unsafe_allow_html=True)
        st.button("← Voltar ao login", key="voltar", on_click=ir, args=("login",))
        titulo("Criar conta", "Preencha os dados abaixo para acessar o sistema.")
        with st.form("form_cadastro", border=False):
            nome = st.text_input("Nome completo", key="cad_nome", placeholder="Digite seu nome")
            usuario = st.text_input("Usuário", key="cad_usuario", placeholder="Escolha um nome de usuário")
            c1, c2 = st.columns(2)
            senha = c1.text_input("Senha", key="cad_senha", type="password", placeholder="Mínimo de 6 caracteres")
            conf = c2.text_input("Confirmar senha", key="cad_conf", type="password", placeholder="Repita a senha")
            ok = st.form_submit_button("Criar conta", type="primary", **ESTICAR_FORM)

    if ok:
        usuario = usuario.strip().lower()
        if not (nome.strip() and usuario and senha):
            st.error("Preencha todos os campos.")
        elif not USUARIO_OK.match(usuario):
            st.error("O usuário deve ter de 3 a 30 caracteres, só com letras, números, ponto, hífen ou _.")
        elif len(senha) < 6:
            st.error("A senha precisa ter pelo menos 6 caracteres.")
        elif senha != conf:
            st.error("As senhas não conferem.")
        elif not criar_usuario(nome.strip(), usuario, senha):
            st.error("Esse nome de usuário já existe. Escolha outro.")
        else:
            st.session_state.aviso = ("success", "Conta criada. Entre com seu usuário e senha.")
            ir("login")
            st.rerun()


def mostrar_resultado(res):
    linhas = res.get("linhas") or []
    df = pd.DataFrame(linhas) if linhas else pd.DataFrame()

    st.markdown(f"<div class='pergunta'>{esc(res['pergunta'])}</div>", unsafe_allow_html=True)
    chips = []
    if not df.empty:
        n = len(df)
        chips.append(f"{n:,} registro{'s' if n != 1 else ''}".replace(",", "."))
        chips.append(f"{len(df.columns)} coluna{'s' if len(df.columns) != 1 else ''}")
    try:
        chips.append(datetime.fromisoformat(res["quando"]).strftime("%d/%m/%Y %H:%M"))
    except (KeyError, ValueError, TypeError):
        pass
    st.markdown("".join(f"<span class='chip'>{esc(c)}</span>" for c in chips), unsafe_allow_html=True)

    if res.get("resposta"):
        try:
            caixa = st.container(key="resposta")
        except TypeError:
            caixa = st.container(border=True)
        with caixa:
            st.markdown(
                f"<div class='bot-header'>{emblema_html(28)}<span class='bot-nome'>Farmazids AI</span></div>",
                unsafe_allow_html=True
            )
            st.markdown(limpar_resposta(res["resposta"]))
    elif df.empty:
        st.warning("Não foram encontrados dados para os critérios informados. Verifique a grafia ou tente buscar sem especificar a dosagem ou quantidade exata.")

    if df.empty:
        return

    st.markdown("<div class='rot'>Tabela de Dados</div>", unsafe_allow_html=True)

    colunas_padrao = [c for c in ["nome", "farmacia", "preco_pix_avista", "valor_cartao_total", "url_produto"] if c in df.columns]
    if not colunas_padrao:
        colunas_padrao = list(df.columns)

    colunas_selecionadas = st.multiselect(
        "Selecione as colunas para exibir na tabela:",
        options=list(df.columns),
        default=colunas_padrao,
        format_func=rotulo_col
    )

    if not colunas_selecionadas:
        colunas_selecionadas = colunas_padrao

    df_exibicao = df[colunas_selecionadas]

    st.markdown(tabela_html(df_exibicao), unsafe_allow_html=True)
    if len(df_exibicao) > MAX_LINHAS:
        st.markdown(f"<div class='nota'>Exibindo {MAX_LINHAS} de {len(df_exibicao)} linhas. Baixe o CSV para ver todas.</div>",
                    unsafe_allow_html=True)

    col_tb1, col_tb2 = st.columns(2)
    col_tb1.download_button(
        "Baixar Tabela Completa (CSV)",
        df.to_csv(index=False).encode("utf-8-sig"),
        file_name="consulta_farmazids.csv",
        mime="text/csv"
    )
    col_tb2.download_button(
        "Baixar Tabela Exibida em PNG",
        data=gerar_tabela_png(df_exibicao),
        file_name="tabela_farmazids.png",
        mime="image/png"
    )

    info = analisar(df)
    if info:
        st.markdown("<div class='rot'>Visualização Gráfica</div>", unsafe_allow_html=True)
        try:
            grafico(info)
        except Exception:
            pass


def pagina_consulta():
    topo()
    titulo("Consulta aos dados", "Faça uma pergunta em linguagem natural sobre os dados da Farmazids.")
    
    with st.form("form_consulta", border=True):
        c1, c2, c3 = st.columns([5, 1.4, 0.8], vertical_alignment="bottom")
        pergunta = c1.text_input("Sua pergunta", key="consulta_pergunta", placeholder="Digite sua pergunta sobre os dados")
        
        enviar = c2.form_submit_button("Perguntar", type="primary", **ESTICAR_FORM)
        c3.form_submit_button("×", help="Limpar texto da busca", on_click=limpar_busca, **ESTICAR_FORM)

    if enviar:
        pergunta = pergunta.strip()
        if not pergunta:
            st.warning("Digite uma pergunta para consultar.")
        else:
            try:
                with st.spinner("Consultando dados da Farmazids..."):
                    saida = consultar(pergunta)
            except Exception as e:
                st.error(erro_amigavel(e))
            else:
                quando = datetime.now().isoformat(timespec="seconds")
                resposta, linhas = saida.get("resposta"), saida.get("linhas") or []
                salvar_pergunta(st.session_state.usuario, pergunta, resposta, linhas, quando)
                
                with conexao() as con:
                    p_last = con.execute("SELECT id FROM perguntas WHERE usuario=? ORDER BY id DESC LIMIT 1", (st.session_state.usuario,)).fetchone()
                    new_id = p_last["id"] if p_last else None
                
                st.session_state.resultado = {"id": new_id, "pergunta": pergunta, "resposta": resposta, "linhas": linhas, "quando": quando}
                st.rerun()

    if st.session_state.get("resultado"):
        mostrar_resultado(st.session_state.resultado)
    else:
        st.markdown(
            "<div class='vazio'><div class='h2'>Faça sua primeira pergunta</div>"
            "<div class='dica'>Seja específico: diga o que quer saber e sobre qual produto, categoria ou período.</div>"
            "<div class='dica'>Peça comparações ou evolução ao longo do tempo para gerar também o gráfico.</div>"
            "<div class='dica'>Suas consultas recentes ficam no menu lateral para reabrir quando quiser.</div></div>",
            unsafe_allow_html=True,
        )


def pagina_historico():
    topo()
    titulo("Histórico de Consultas", "Veja todas as suas perguntas anteriores e o resumo das respostas fornecidas.")
    
    perguntas = listar_perguntas(st.session_state.usuario)
    if not perguntas:
        st.markdown("<div class='vazio'><div class='h2'>Nenhuma consulta realizada ainda.</div>"
                    "<div class='dica'>Suas perguntas e respostas salvas aparecerão listadas aqui.</div></div>", unsafe_allow_html=True)
        return

    for p in perguntas:
        dt_str = p["criada_em"]
        try:
            dt_fmt = datetime.fromisoformat(dt_str).strftime("%d/%m/%Y às %H:%M")
        except Exception:
            dt_fmt = dt_str

        resp_resumo = limpar_resposta(p["resposta"]) if p["resposta"] else "Consulta sem resposta textual gerada."

        st.markdown(
            f"<div class='hist-card'>"
            f"<div class='hist-pergunta'>{esc(p['pergunta'])}</div>"
            f"<div class='hist-data'>Realizada em {dt_fmt}</div>"
            f"<div class='hist-resposta'><b>Resposta resumida:</b><br>{esc(resp_resumo)}</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        c_abrir, c_del = st.columns([3, 1])
        c_abrir.button("Abrir consulta completa", key=f"abrir_hist_{p['id']}", on_click=abrir_pergunta, args=(p["id"],), use_container_width=True)
        c_del.button("Excluir", key=f"del_hist_{p['id']}", on_click=deletar_pergunta_callback, args=(p["id"],), use_container_width=True)


def pagina_perfil():
    topo()
    titulo("Perfil", "Gerencie sua foto de perfil, nome completo e segurança da conta.")
    aviso()
    esq, dir_ = st.columns([2, 3], gap="large")
    with esq:
        foto = st.session_state.get("foto")
        total = total_perguntas(st.session_state.usuario)
        
        if foto:
            img_perfil = f"<img class='perfil-avatar-lg' src='data:image/png;base64,{foto}'>"
        elif EMBLEMA.exists():
            img_perfil = f"<img class='perfil-avatar-lg' src='data:image/png;base64,{img_b64(EMBLEMA)}'>"
        else:
            img_perfil = f"<div class='avatar-txt' style='width:96px;height:96px;font-size:2.5rem;margin:0 auto;'>{st.session_state.nome[:1].upper()}</div>"

        st.markdown(
            f"<div class='perfil-card'>{img_perfil}"
            f"<div class='perfil-nome'>{esc(st.session_state.nome)}</div>"
            f"<div class='perfil-user'>@{esc(st.session_state.usuario)}</div>"
            f"<div class='perfil-stat'><b>{total} </b>consulta{'s' if total != 1 else ''} realizada{'s' if total != 1 else ''}</div></div>",
            unsafe_allow_html=True,
        )
        
        st.markdown("<div class='rot'>Foto do Perfil</div>", unsafe_allow_html=True)
        nova_foto = st.file_uploader("Escolha uma imagem (PNG ou JPG)", type=["png", "jpg", "jpeg"])
        if nova_foto is not None:
            foto_bytes = nova_foto.read()
            foto_b64 = base64.b64encode(foto_bytes).decode("utf-8")
            salvar_foto(st.session_state.usuario, foto_b64)
            st.session_state.foto = foto_b64
            st.success("Foto atualizada com sucesso!")
            st.rerun()

        if foto:
            if st.button("Remover foto de perfil", key="b_rem_foto", **ESTICAR):
                remover_foto(st.session_state.usuario)
                st.session_state.foto = None
                st.success("Foto de perfil removida com sucesso!")
                st.rerun()

        st.markdown("---")
        st.markdown("<div class='btn-sair-icone'>", unsafe_allow_html=True)
        st.button("Sair da conta", key="b_sair", on_click=solicitar_sair, **ESTICAR)
        st.markdown("</div>", unsafe_allow_html=True)

    with dir_:
        with st.form("form_nome", border=True):
            st.markdown("<div class='h2'>Alterar nome completo</div><div class='mudo' style='margin-top:.2rem'>"
                        "Atualize o nome de exibição no seu perfil.</div>", unsafe_allow_html=True)
            novo_nome = st.text_input("Novo nome completo", value=st.session_state.nome, placeholder="Digite o seu novo nome completo")
            ok_nome = st.form_submit_button("Salvar nome", type="primary", **ESTICAR_FORM)

        if ok_nome:
            novo_nome_limpo = novo_nome.strip()
            if not novo_nome_limpo:
                st.error("O nome não pode ficar em branco.")
            else:
                atualizar_nome(st.session_state.usuario, novo_nome_limpo)
                st.session_state.nome = novo_nome_limpo
                st.session_state.aviso = ("success", "Nome alterado com sucesso.")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("form_senha", border=True):
            st.markdown("<div class='h2'>Redefinir senha</div><div class='mudo' style='margin-top:.2rem'>"
                        "Informe a senha atual e escolha uma nova.</div>", unsafe_allow_html=True)
            atual = st.text_input("Senha atual", key="senha_atual", type="password", placeholder="Digite sua senha atual")
            c1, c2 = st.columns(2)
            nova = c1.text_input("Nova senha", key="nova_senha", type="password", placeholder="Mínimo de 6 caracteres")
            conf = c2.text_input("Confirmar nova senha", key="nova_conf", type="password", placeholder="Repita a nova senha")
            ok_senha = st.form_submit_button("Salvar nova senha", type="primary", **ESTICAR_FORM)

        if ok_senha:
            nome, _ = autenticar(st.session_state.usuario, atual)
            if not nome:
                st.error("A senha atual está incorreta.")
            elif len(nova) < 6:
                st.error("A nova senha precisa ter pelo menos 6 caracteres.")
            elif nova != conf:
                st.error("As senhas novas não conferem.")
            else:
                trocar_senha(st.session_state.usuario, nova)
                st.session_state.aviso = ("success", "Senha alterada com sucesso.")
                st.rerun()


PAGINAS = {
    "login": pagina_login,
    "cadastro": pagina_cadastro,
    "consulta": pagina_consulta,
    "historico": pagina_historico,
    "perfil": pagina_perfil
}


def main():
    st.set_page_config(
        page_title="Farmazids", 
        page_icon=str(EMBLEMA) if EMBLEMA.exists() else "🌿",
        layout="wide", 
        initial_sidebar_state="expanded"
    )
    iniciar_db()
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("pagina", "login")
    st.session_state.setdefault("menu_aberto", True)
    
    if "usuario" not in st.session_state and st.session_state.pagina not in ("login", "cadastro"):
        ir("login")
    if st.session_state.pagina in ("consulta", "historico", "perfil") and st.session_state.get("menu_aberto"):
        menu_lateral()
        
    PAGINAS[st.session_state.pagina]()


if __name__ == "__main__":
    main()