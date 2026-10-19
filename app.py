import base64
import hashlib
import html
import inspect
import json
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()  # Carrega as variáveis do ficheiro .env para o sistema

import altair as alt
import boto3
import pandas as pd
import streamlit as st

# --- AJUSTE AQUI ---
STATE_MACHINE_ARN = "arn:aws:states:us-east-2:906513713169:stateMachine:farmazids-t1-equipe-06-bedrockV2"
REGIAO = "us-east-2"
# -------------------

BASE = Path(__file__).parent
DB = BASE / "farmazids.db"
LOGO = BASE / "logo.png"          # logo "FARMAZIDS MEDICINA ORIENTAL" (original, sem alterações)
EMBLEMA = BASE / "emblema.png"    # emblema redondo (original, sem alterações)
USUARIO_OK = re.compile(r"^[a-z0-9_.-]{3,30}$")
RECENTES = 3          # quantas consultas aparecem em "Consultas recentes"
MAX_LINHAS = 200      # linhas exibidas na tabela da tela (o CSV leva todas)

# Paleta do projeto
ROXO, DOURADO, CINZA, FUNDO, LILAS = "#42205A", "#C9AD7A", "#C9D0DA", "#FBF9F4", "#D8C3EE"


def _esticar(fn):
    """Largura total do componente, em qualquer versão do Streamlit."""
    return {"width": "stretch"} if "width" in inspect.signature(fn).parameters else {"use_container_width": True}


ESTICAR = _esticar(st.button)
ESTICAR_FORM = _esticar(st.form_submit_button)
ESTICAR_ALT = _esticar(st.altair_chart)

# ---------------------------------------------------------------- estilo
PRIM = [
    '.stButton button[kind="primary"]',
    '[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]',
    '[data-testid="stBaseButton-primary"]',
    '[data-testid="stBaseButton-primaryFormSubmit"]',
]
CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Poppins:wght@400;500;600&display=swap');
:root { --roxo:#42205A; --dourado:#C9AD7A; --cinza:#C9D0DA; --fundo:#FBF9F4; --lilas:#D8C3EE;
        --texto:#2B2B2B; --mudo:rgba(66,32,90,.66); --borda:rgba(201,208,218,.85); }
.stApp { background:var(--fundo); color:var(--texto); }
.stApp, .stApp p, .stApp label, .stApp input, .stApp button, .stApp li, .stApp td, .stApp th, .stApp textarea { font-family:'Poppins',sans-serif; }
[data-testid="stToolbar"], [data-testid="stDecoration"], footer, [data-testid="InputInstructions"] { display:none !important; }
[data-testid="stHeader"] { background:transparent; }
.block-container { max-width:1180px; padding-top:2rem; padding-bottom:3rem; }

/* tipografia */
.h1 { font-family:'Cinzel',serif; font-weight:800; font-size:2rem; line-height:1.2; color:var(--roxo); margin:0; }
.h1::after { content:""; display:block; width:44px; height:3px; border-radius:2px; background:var(--dourado); margin-top:.7rem; }
.h2 { font-family:'Cinzel',serif; font-weight:700; font-size:1.25rem; color:var(--roxo); margin:0 0 .2rem; }
.mudo { color:var(--mudo); font-size:.95rem; line-height:1.6; margin:.7rem 0 1.4rem; }
.rot { color:var(--mudo); font-size:.82rem; font-weight:600; margin:1.6rem 0 .45rem; }
.pergunta { font-family:'Cinzel',serif; font-weight:700; font-size:1.35rem; line-height:1.35; color:var(--roxo); margin:1.8rem 0 .6rem; }
.chip { display:inline-block; background:rgba(216,195,238,.5); color:var(--roxo); border-radius:999px; padding:.2rem .85rem; font-size:.8rem; font-weight:500; margin:0 .4rem .3rem 0; }
.st-key-resposta { background:#fff; border:1px solid var(--borda); border-left:4px solid var(--dourado); border-radius:12px; padding:1.1rem 1.4rem; box-shadow:0 1px 3px rgba(66,32,90,.05); }
.st-key-resposta p, .st-key-resposta li { line-height:1.7; font-size:1rem; }
.st-key-resposta h1, .st-key-resposta h2, .st-key-resposta h3, .st-key-resposta h4 { font-family:'Cinzel',serif; font-size:1.05rem; color:var(--roxo); margin:.2rem 0 .5rem; padding:0; }
.st-key-resposta pre { background:var(--fundo); border-radius:8px; }
.vazio { background:#fff; border:1px dashed var(--cinza); border-radius:16px; padding:2rem 2.2rem; margin-top:1.6rem; }
.vazio .h2 { margin-bottom:.6rem; }
.dica { color:var(--texto); font-size:.95rem; line-height:1.6; padding-left:1.3rem; position:relative; margin:.5rem 0; }
.dica::before { content:""; position:absolute; left:0; top:.62em; width:.5rem; height:.5rem; border-radius:50%; background:var(--dourado); }
.troca { color:var(--mudo); font-size:.9rem; text-align:center; margin:1.2rem 0 .5rem; }

/* campos */
[data-testid="stWidgetLabel"] p { color:var(--roxo); font-size:.85rem; font-weight:500; }
div[data-baseweb="input"], div[data-baseweb="base-input"] { background:#fff !important; }
div[data-baseweb="input"] { background:#fff !important; border:1.5px solid var( --cinza) !important; border-radius:12px; box-shadow:none; }
div[data-baseweb="input"]:focus-within { border-color:var(--roxo) !important; box-shadow:0 0 0 3px rgba(216,195,238,.7); }
[data-testid="stTextInput"] input {
    height:3rem; font-size:.98rem; padding-left:1rem;
    background:#fff !important;
    color:#2B2B2B !important;
    -webkit-text-fill-color:#2B2B2B !important;
    caret-color:#42205A;
}
[data-testid="stTextInput"] input::placeholder { color:#8a8f98 !important; -webkit-text-fill-color:#8a8f98 !important; opacity:1; }
[data-testid="stTextInput"] input:-webkit-autofill,
[data-testid="stTextInput"] input:-webkit-autofill:hover,
[data-testid="stTextInput"] input:-webkit-autofill:focus {
    -webkit-box-shadow:0 0 0 1000px #fff inset !important;
    -webkit-text-fill-color:#2B2B2B !important;
    caret-color:#42205A;
    transition:background-color 9999s ease-in-out 0s;
}
/* botão do olho (revelar senha): fundo branco, ícone roxo */
[data-testid="stTextInputRootElement"] > div,
[data-testid="stTextInputRootElement"] button {
    background:#fff !important;
    background-color:#fff !important;
    border:none !important;
    box-shadow:none !important;
}
[data-testid="stTextInputRootElement"] button { border-radius:0 12px 12px 0; }
[data-testid="stTextInputRootElement"] button:hover { background:rgba(216,195,238,.35) !important; }
[data-testid="stTextInputRootElement"] button,
[data-testid="stTextInputRootElement"] button * {
    color:#42205A !important;
}
/* contêiner do campo: branco, e botão do olho na altura toda */
[data-testid="stTextInputRootElement"],
[data-testid="stTextInputRootElement"] div[data-baseweb="base-input"] {
    background:#fff !important;
    background-color:#fff !important;
}
[data-testid="stTextInputRootElement"] > div {
    align-self:stretch;
    display:flex;
    align-items:stretch;
}
[data-testid="stTextInputRootElement"] button {
    height:100% !important;
    min-height:0;
}
[data-testid="stForm"] { background:#fff; border:1px solid var(--borda); border-radius:16px; padding:1.4rem 1.5rem; box-shadow:0 1px 3px rgba(66,32,90,.05), 0 8px 24px rgba(66,32,90,.05); }

/* botões: secundário (contorno) e primário (roxo) */
.stButton button, [data-testid="stFormSubmitButton"] button, [data-testid="stDownloadButton"] button { border-radius:12px; height:3rem; border:1.5px solid var(--roxo); background:#fff; transition:background .15s; }
.stButton button p, [data-testid="stFormSubmitButton"] button p, [data-testid="stDownloadButton"] button p { color:var(--roxo); font-weight:600; font-size:.95rem; }
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover, [data-testid="stDownloadButton"] button:hover { background:rgba(216,195,238,.45); border-color:var(--roxo); }
{{PRIM}} { background:var(--roxo) !important; border-color:var(--roxo) !important; }
{{PRIM_P}} { color:var(--dourado) !important; }
{{PRIM_H}} { background:#55306f !important; }
.st-key-menu button { width:3rem; padding:0; }
.st-key-menu button p { font-size:1.3rem; line-height:1; }
.st-key-voltar button { border:none; background:transparent; height:auto; justify-content:flex-start; padding:.3rem 0; }

/* abas */
[data-baseweb="tab-list"] { gap:1.4rem; }
button[data-baseweb="tab"] { padding:.6rem 0; height:auto; background:transparent; }
button[data-baseweb="tab"] p { font-weight:600; color:var(--mudo); font-size:.95rem; }
button[data-baseweb="tab"][aria-selected="true"] p { color:var(--roxo); }
[data-baseweb="tab-highlight"] { background:var(--roxo); height:3px; }
[data-baseweb="tab-border"] { background:var(--borda); }

/* tabela */
.tabela-wrap { overflow:auto; max-height:520px; background:#fff; border:1px solid var(--borda); border-radius:12px; margin:.8rem 0 1rem; box-shadow:0 1px 3px rgba(66,32,90,.05); }
.tabela { width:100%; border-collapse:separate; border-spacing:0; font-size:.88rem; }
.tabela th { position:sticky; top:0; z-index:1; background:var(--roxo); color:var(--dourado); text-align:left; font-weight:600; padding:.8rem 1.1rem; white-space:nowrap; }
.tabela td { padding:.7rem 1.1rem; border-bottom:1px solid rgba(201,208,218,.5); color:var(--texto); }
.tabela tbody tr:nth-child(even) td { background:var(--fundo); }
.tabela tbody tr:hover td { background:rgba(216,195,238,.35); }
.tabela tbody tr:last-child td { border-bottom:none; }
.tabela .num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.nota { color:var(--mudo); font-size:.82rem; margin:-.4rem 0 .8rem; }
.legenda { background:rgba(216,195,238,.28); border-left:3px solid var(--dourado); border-radius:8px; padding:.8rem 1.1rem; margin:.4rem 0 1rem; color:var(--texto); font-size:.93rem; line-height:1.65; }
.legenda b { color:var(--roxo); }

/* painel de marca (login e cadastro) */
.painel { background:var(--roxo); border-radius:20px; padding:2.6rem 2.4rem; min-height:640px; display:flex; flex-direction:column; justify-content:center; gap:1.7rem; }
.painel-logo { background:var(--fundo); border-radius:14px; border-bottom:4px solid var(--dourado); padding:1.2rem 1.5rem; max-width:340px; text-align:center; }
.painel-t { font-family:'Cinzel',serif; font-weight:700; font-size:1.8rem; line-height:1.3; color:#fff; }
.painel-p { color:var(--lilas); font-size:1rem; line-height:1.7; max-width:38ch; }
.painel-i { color:#fff; font-size:.95rem; padding-left:1.4rem; position:relative; margin:.55rem 0; }
.painel-i::before { content:""; position:absolute; left:0; top:.6em; width:.55rem; height:.55rem; border-radius:50%; background:var(--dourado); }
.logo { max-width:100%; height:auto; display:block; margin:0 auto; }
.logo-txt { font-family:'Cinzel',serif; font-weight:800; font-size:1.6rem; color:var(--roxo); }
.form-topo { padding-top:3.2rem; }

/* topo e perfil */
.usuario { display:flex; align-items:center; justify-content:flex-end; gap:.7rem; color:var(--roxo); font-weight:500; font-size:.92rem; }
.avatar { width:2.4rem; height:2.4rem; border-radius:50%; background:var(--roxo); color:var(--dourado); display:inline-flex; align-items:center; justify-content:center; font-family:'Cinzel',serif; font-weight:700; }
.perfil { background:#fff; border:1px solid var(--borda); border-radius:16px; padding:2rem 1.6rem; text-align:center; margin-bottom:1rem; box-shadow:0 1px 3px rgba(66,32,90,.05), 0 8px 24px rgba(66,32,90,.05); }
.perfil img { width:96px; height:96px; }
.perfil-nome { font-family:'Cinzel',serif; font-weight:700; font-size:1.4rem; color:var(--roxo); margin-top:.8rem; }
.perfil-user { color:var(--mudo); font-size:.9rem; }
.perfil-stat { margin-top:1.3rem; padding-top:1.1rem; border-top:1px solid var(--borda); color:var(--texto); font-size:.92rem; }
.perfil-stat b { color:var(--roxo); font-size:1.3rem; display:block; }

/* menu lateral: aberto pelo botão de menu; os controles nativos ficam escondidos */
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"], [data-testid="stSidebarHeader"] { display:none !important; }
section[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--borda); width:300px !important; min-width:300px !important; max-width:300px !important; }
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top:1.5rem; }
[data-testid="stSidebar"] .stButton button[kind="secondary"], [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] { border:none; background:transparent; height:auto; padding:.6rem .8rem; justify-content:flex-start; }
[data-testid="stSidebar"] .stButton button[kind="secondary"] p, [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p { font-weight:500; text-align:left; }
[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover, [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover { background:rgba(216,195,238,.45); }
.side-logo { padding:0 .3rem 1.2rem; border-bottom:1px solid var(--borda); margin-bottom:1.2rem; }
.side-titulo { color:var(--mudo); font-size:.82rem; font-weight:600; padding:0 .8rem; margin:1.4rem 0 .3rem; }
.side-vazio { color:var(--mudo); font-size:.88rem; padding:0 .8rem; }
.side-linha { border:0; border-top:1px solid var(--borda); margin:1.2rem 0 .8rem; }

@media (max-width: 800px) { .painel { min-height:auto; } .form-topo { padding-top:1rem; } }
</style>"""
CSS = (
    CSS.replace("{{PRIM}}", ",".join(PRIM))
    .replace("{{PRIM_P}}", ",".join(s + " p" for s in PRIM))
    .replace("{{PRIM_H}}", ",".join(s + ":hover" for s in PRIM))
)


# ---------------------------------------------------------------- banco de dados (SQLite local)
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
                salt BLOB NOT NULL, hash BLOB NOT NULL);
            CREATE TABLE IF NOT EXISTS perguntas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL,
                pergunta TEXT NOT NULL, resposta TEXT, linhas TEXT, sql TEXT,
                criada_em TEXT NOT NULL);
            """
        )


def gerar_hash(senha, salt):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, 200_000)


def criar_usuario(nome, usuario, senha):
    salt = secrets.token_bytes(16)
    try:
        with conexao() as con:
            con.execute("INSERT INTO usuarios VALUES (?,?,?,?)", (usuario, nome, salt, gerar_hash(senha, salt)))
        return True
    except sqlite3.IntegrityError:
        return False


def autenticar(usuario, senha):
    with conexao() as con:
        u = con.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
    if u and secrets.compare_digest(gerar_hash(senha, u["salt"]), u["hash"]):
        return u["nome"]
    return None


def trocar_senha(usuario, senha):
    salt = secrets.token_bytes(16)
    with conexao() as con:
        con.execute("UPDATE usuarios SET salt=?, hash=? WHERE usuario=?", (salt, gerar_hash(senha, salt), usuario))


def salvar_pergunta(usuario, pergunta, resposta, linhas, quando):
    with conexao() as con:
        con.execute(
            "INSERT INTO perguntas (usuario, pergunta, resposta, linhas, criada_em) VALUES (?,?,?,?,?)",
            (usuario, pergunta, resposta, json.dumps(linhas, ensure_ascii=False), quando),
        )


def listar_perguntas(usuario, limite=RECENTES):
    with conexao() as con:
        return con.execute(
            "SELECT id, pergunta FROM perguntas WHERE usuario=? ORDER BY id DESC LIMIT ?", (usuario, limite)
        ).fetchall()


def total_perguntas(usuario):
    with conexao() as con:
        return con.execute("SELECT COUNT(*) FROM perguntas WHERE usuario=?", (usuario,)).fetchone()[0]


# ---------------------------------------------------------------- chamada à state machine
@st.cache_resource
def cliente_sfn():
    # No Streamlit Cloud as credenciais vêm de "Secrets"; no computador, do `aws configure`.
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
    if "credentials" in t:
        return "As credenciais da AWS não estão configuradas. Adicione-as em Settings → Secrets do app."
    if "accessdenied" in t or "not authorized" in t:
        return "A conta da AWS não tem permissão para executar esta consulta."
    return "Não foi possível concluir a consulta. Tente novamente em instantes."


# ---------------------------------------------------------------- tabela e gráfico a partir dos dados
HINT_ID = re.compile(r"(^|_)(id|cod|codigo|código|gtin|ean|cnpj|cpf|cep|fone|telefone|sku|ncm)(_|$)", re.I)
HINT_ORDEM = re.compile(r"^(ano|year|mes|mês|month|dia|semana|trimestre)$", re.I)


def esc(texto):
    """Escapa HTML e o '$' (que o markdown do Streamlit trataria como fórmula)."""
    return html.escape(str(texto)).replace("$", "&#36;")


def rotulo_col(c):
    s = str(c).replace("_", " ").strip()
    return s[:1].upper() + s[1:]


BLOCOS = re.compile(r"[█▓▒░▇▆▅▄▃▂▁■]")
GRAFICO_TEXTO = re.compile(r"(?:^[ \t]*[#*\s]*Gr[áa]fico[^\n]*\n+)?^[ \t]*```[^\n]*\n(.*?)^[ \t]*```[ \t]*\n?", re.M | re.S)


def limpar_resposta(texto):
    """Tira da resposta o que o app já mostra melhor: o título "Resposta" e gráficos feitos de texto (█)."""
    texto = GRAFICO_TEXTO.sub(lambda m: "" if BLOCOS.search(m.group(1)) else m.group(0), str(texto))
    texto = re.sub(r"^\s*#{1,6}\s*Resposta\s*:?\s*\n", "", texto, flags=re.I)
    return texto.replace("$", "\\$").strip()    # "$" viraria fórmula no markdown


def numerica(s):
    """A coluna convertida em número, ou None se ela não for numérica (ou for um código)."""
    if s.dtype == bool or s.dropna().empty:
        return None
    if s.dtype == object or str(s.dtype).startswith("str"):
        if s.dropna().astype(str).str.match(r"^0\d").any():   # "007": código, não quantidade
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
        if (v % 1 == 0).all() and v.min() >= 1e11:           # GTIN, CNPJ etc.
            continue
        out[c] = n
    return out


def como_data(s):
    txt = s.astype(str).str.strip()
    if txt.str.match(r"^\d{4}-\d{2}(-\d{2})?").all():
        d = pd.to_datetime(txt.str[:10], errors="coerce")          # sem format="mixed"
    elif txt.str.match(r"^\d{2}/\d{2}/\d{4}").all():
        d = pd.to_datetime(txt, errors="coerce", dayfirst=True)
    else:
        return None
    return d if d.notna().all() else None


ADITIVA = re.compile(r"(quant|qtd|total|venda|valor|unidade|receita|faturamento|soma)", re.I)


def _dimensao(c, s, ja_numerica):
    """Como a coluna serve de eixo: 'tempo', 'ordem' (ano, mês...) ou 'cat'; None se não serve."""
    if ja_numerica:
        return ("ordem", s) if HINT_ORDEM.match(str(c)) else (None, None)
    data = como_data(s)
    if data is not None:
        return "tempo", data
    if HINT_ID.search(str(c)):
        return None, None
    return "cat", s.astype(str)


def analisar(df):
    """Diz se a resposta pede um gráfico. Devolve None se não fizer sentido.

    Para cada par (coluna de categorias ou período, coluna de números) usa só as linhas em que os
    dois existem, o que cobre respostas "mistas" (uma linha de resumo + várias de histórico).
    Se a categoria se repete, soma os valores, mas só de medidas que se somam (quantidade, total,
    valor...). Exige de 2 a 60 pontos (até 30 para categorias em texto). Códigos como GTIN não entram.
    """
    if len(df) < 2:
        return None
    nums = colunas_numericas(df)
    for c in df.columns:
        series = {}
        for m in nums:
            if m == c:
                continue
            sub = pd.DataFrame({"cat": nums[c] if c in nums else df[c], "val": nums[m]}).dropna()
            if len(sub) < 2:
                continue
            tipo, cat = _dimensao(c, sub["cat"], c in nums)
            if tipo is None:
                continue
            sub["cat"] = cat
            agregado = not sub["cat"].is_unique
            if agregado:
                if not ADITIVA.search(str(m)):
                    continue
                sub = sub.groupby("cat", as_index=False, sort=False)["val"].sum()
            if not (2 <= len(sub) <= 60) or (tipo == "cat" and len(sub) > 30):
                continue
            series[m] = {"df": sub, "tipo": tipo, "agregado": agregado}
        if series:
            return {"dim": c, "series": series}
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
            colunas.append(["—" if (x is None or x == "" or (isinstance(x, float) and x != x)) else str(x)
                            for x in recorte[c]])
    cab = "".join(f"<th class='{'num' if c in nums else ''}'>{esc(rotulo_col(c))}</th>" for c in df.columns)
    corpo = "".join(
        "<tr>" + "".join(
            f"<td class='{'num' if c in nums else ''}'>{esc(v)}</td>" for c, v in zip(df.columns, linha)
        ) + "</tr>"
        for linha in zip(*colunas)
    )
    return f"<div class='tabela-wrap'><table class='tabela'><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table></div>"

def legenda_grafico(d, tipo, dim, medida):
    """Texto 'este gráfico representa...' montado a partir dos dados exibidos."""
    inteiro = (d["val"] % 1 == 0).all()
    f = lambda x: fmt_num(x, inteiro)
    nome = rotulo_col(medida).lower()
    n = len(d)
    maior = d.loc[d["val"].idxmax()]
    menor = d.loc[d["val"].idxmin()]
    media = d["val"].mean()
    b = lambda x: f"<b>{esc(x)}</b>"

    if tipo in ("tempo", "ordem"):
        ini, fim = d.iloc[0], d.iloc[-1]
        txt = f"Este gráfico mostra a evolução de {b(nome)} em {n} períodos, de {b(ini['rot'])} a {b(fim['rot'])}. "
        txt += f"O maior valor foi em {b(maior['rot'])} ({f(maior['val'])}) e o menor em {b(menor['rot'])} ({f(menor['val'])}). "
        if ini["val"]:
            var = (fim["val"] - ini["val"]) / abs(ini["val"]) * 100
            if abs(var) < 3:
                txt += "No conjunto, o comportamento é estável"
            else:
                txt += f"Do primeiro ao último período, houve {'alta' if var > 0 else 'queda'} de {abs(var):.1f}%".replace(".", ",")
            txt += f", com média de {f(media)} por período."
        else:
            txt += f"A média foi de {f(media)} por período."
    else:
        ordem = d.sort_values("val", ascending=False)
        txt = (f"Este gráfico compara {b(nome)} entre {n} {esc(rotulo_col(dim).lower())}s. "
               f"{b(maior['rot'])} lidera com {f(maior['val'])}, e {b(menor['rot'])} aparece por último com {f(menor['val'])}. ")
        if ADITIVA.search(str(medida)) and d["val"].sum() > 0:
            share = ordem["val"].head(3).sum() / d["val"].sum() * 100
            if n > 3:
                txt += f"Os 3 primeiros concentram {share:.0f}% do total.".replace(".", ",")
    return f"<div class='legenda'>{txt}</div>"

def grafico(info):
    dim, series = info["dim"], info["series"]
    medidas = list(series)
    c1, c2 = st.columns([3, 2])
    medida = c1.selectbox("Valor exibido", medidas, format_func=rotulo_col) if len(medidas) > 1 else medidas[0]
    d, tipo = series[medida]["df"].copy(), series[medida]["tipo"]
    formas = ["Linhas", "Barras"] if tipo in ("tempo", "ordem") else ["Barras"]
    forma = c2.radio("Tipo de gráfico", formas, horizontal=True) if len(formas) > 1 else formas[0]
    if series[medida]["agregado"]:
        st.markdown(f"<div class='nota'>Valores somados por {esc(rotulo_col(dim).lower())}.</div>", unsafe_allow_html=True)

    if tipo == "cat":
        d = d.sort_values("val", ascending=False)
    else:
        d = d.sort_values("cat")
    t_cat, t_val = rotulo_col(dim), rotulo_col(medida)
    if tipo == "tempo":
        so_mes = (d["cat"].dt.day == 1).all()
        d["rot"] = d["cat"].dt.strftime("%m/%Y" if so_mes else "%d/%m/%Y")
    else:
        d["rot"] = d["cat"].astype(str)
    tip = [alt.Tooltip("rot:N", title=t_cat), alt.Tooltip("val:Q", title=t_val, format=",.2~f")]
    eixo_y = alt.Axis(grid=True, gridColor=CINZA, gridOpacity=0.6, domain=False, ticks=False)

    if forma == "Linhas":
        x = alt.X("cat:T", title=None, axis=alt.Axis(grid=False, labelAngle=0, format="%m/%Y" if so_mes else "%d/%m")) \
            if tipo == "tempo" else alt.X("rot:O", title=None, axis=alt.Axis(grid=False, labelAngle=0))
        graf = alt.Chart(d).mark_line(
            color=ROXO, strokeWidth=2.5, point=alt.OverlayMarkDef(color=DOURADO, stroke=ROXO, filled=True, size=70)
        ).encode(x=x, y=alt.Y("val:Q", title=t_val, axis=eixo_y), tooltip=tip).properties(height=360)
    elif tipo == "cat" and (len(d) > 8 or d["rot"].str.len().max() > 16):
        graf = alt.Chart(d).mark_bar(color=ROXO, cornerRadiusEnd=4, size=18).encode(
            y=alt.Y("rot:N", sort=list(d["rot"]), title=None, axis=alt.Axis(labelLimit=280, domain=False, ticks=False)),
            x=alt.X("val:Q", title=t_val, axis=alt.Axis(grid=True, gridColor=CINZA, gridOpacity=0.6, domain=False, ticks=False)),
            tooltip=tip,
        ).properties(height=max(220, 32 * len(d)))
    else:
        graf = alt.Chart(d).mark_bar(color=ROXO, cornerRadiusEnd=4).encode(
            x=alt.X("rot:N", sort=list(d["rot"]), title=None, axis=alt.Axis(labelAngle=0, labelLimit=140, grid=False, domain=False, ticks=False)),
            y=alt.Y("val:Q", title=t_val, axis=eixo_y),
            tooltip=tip,
        ).properties(height=360)

    graf = graf.configure(font="Poppins", background="transparent").configure_view(stroke=None).configure_axis(
        labelColor="#5E4A70", titleColor=ROXO, labelFontSize=12, titleFontSize=12, titleFontWeight=600
    )
    st.altair_chart(graf, theme=None, **ESTICAR_ALT)
    st.markdown(legenda_grafico(d, tipo, dim, medida), unsafe_allow_html=True)


# ---------------------------------------------------------------- navegação e estado
def ir(pagina):
    st.session_state.pagina = pagina


def alternar_menu():
    st.session_state.menu_aberto = not st.session_state.get("menu_aberto", True)


def sair():
    for k in ("usuario", "nome", "resultado"):
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
            "pergunta": p["pergunta"], "resposta": p["resposta"],
            "linhas": json.loads(p["linhas"] or "[]"), "quando": p["criada_em"],
        }
        ir("consulta")


# ---------------------------------------------------------------- componentes visuais
@lru_cache(maxsize=None)
def img_b64(caminho):
    return base64.b64encode(Path(caminho).read_bytes()).decode()


def logo_html(largura=240):
    if LOGO.exists():
        return (f"<img class='logo' alt='Farmazids Medicina Oriental' style='width:{largura}px' "
                f"src='data:image/png;base64,{img_b64(LOGO)}'>")
    return "<div class='logo-txt'>FARMAZIDS</div>"


def titulo(texto, subtitulo=""):
    st.markdown(f"<div class='h1'>{esc(texto)}</div><div class='mudo'>{esc(subtitulo)}</div>", unsafe_allow_html=True)


def aviso():
    msg = st.session_state.pop("aviso", None)
    if msg:
        getattr(st, msg[0])(msg[1])


def painel_marca():
    st.markdown(
        f"<div class='painel'><div class='painel-logo'>{logo_html(300)}</div>"
        "<div class='painel-t'>Consulta inteligente aos dados da Farmazids</div>"
        "<div class='painel-p'>Pergunte em linguagem natural e receba a resposta, a tabela e, "
        "quando fizer sentido, um gráfico.</div>"
        "<div><div class='painel-i'>Perguntas em linguagem natural</div>"
        "<div class='painel-i'>Tabelas prontas para baixar em CSV</div>"
        "<div class='painel-i'>Gráficos gerados automaticamente</div>"
        "<div class='painel-i'>Suas últimas consultas sempre à mão</div></div></div>",
        unsafe_allow_html=True,
    )


def tela_dividida():
    """Painel de marca à esquerda; devolve a coluna do formulário."""
    esq, dir_ = st.columns([1, 1], gap="large")
    with esq:
        painel_marca()
    return dir_


def topo():
    aberto = st.session_state.get("menu_aberto", True)
    c1, c2, c3 = st.columns([1, 4, 4], vertical_alignment="center")
    with c1:
        if not aberto:
            st.button("☰", key="menu", on_click=alternar_menu)
    with c2:
        if not aberto:
            st.markdown(logo_html(210), unsafe_allow_html=True)
    with c3:
        nome = st.session_state.nome
        st.markdown(f"<div class='usuario'>{esc(nome)}<span class='avatar'>{esc(nome[:1].upper())}</span></div>",
                    unsafe_allow_html=True)


def menu_lateral():
    """Só é chamado com o menu aberto; sem chamada, o Streamlit não desenha a barra lateral."""
    with st.sidebar:
        st.markdown(f"<div class='side-logo'>{logo_html(220)}</div>", unsafe_allow_html=True)
        st.button("Nova consulta", key="nova", type="primary", on_click=nova_consulta, **ESTICAR)
        st.markdown("<div class='side-titulo'>Consultas recentes</div>", unsafe_allow_html=True)
        perguntas = listar_perguntas(st.session_state.usuario)
        if not perguntas:
            st.markdown("<div class='side-vazio'>Suas perguntas aparecerão aqui.</div>", unsafe_allow_html=True)
        for p in perguntas:
            texto = p["pergunta"] if len(p["pergunta"]) <= 30 else p["pergunta"][:29] + "…"
            st.button(texto, key=f"hist_{p['id']}", on_click=abrir_pergunta, args=(p["id"],), **ESTICAR)
        st.markdown("<hr class='side-linha'>", unsafe_allow_html=True)
        st.button("Perfil", key="perfil", on_click=ir, args=("perfil",), **ESTICAR)
        st.button("Sair", key="sair", on_click=sair, **ESTICAR)
        st.button("Ocultar menu", key="ocultar", on_click=alternar_menu, **ESTICAR)


# ---------------------------------------------------------------- páginas
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
        nome = autenticar(usuario, senha)
        if nome:
            st.session_state.update(usuario=usuario, nome=nome, resultado=None, menu_aberto=True)
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
    info = analisar(df)
    if info:
        st.markdown("<div class='rot'>Gráfico</div>", unsafe_allow_html=True)
        try:
            grafico(info)
        except Exception as e:
            st.warning("Não foi possível montar o gráfico.")
            st.exception(e)          # temporário: mostra o erro real
    else:
        with st.expander("Por que não há gráfico? (diagnóstico)"):
            st.write(df.dtypes.astype(str))   # temporário

    st.markdown("<div class='rot'>Tabela</div>", unsafe_allow_html=True)
    st.markdown(tabela_html(df), unsafe_allow_html=True)
    if len(df) > MAX_LINHAS:
        st.markdown(f"<div class='nota'>Exibindo {MAX_LINHAS} de {len(df)} linhas. Baixe o CSV para ver todas.</div>",
                    unsafe_allow_html=True)
    st.download_button("Baixar CSV", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name="consulta.csv", mime="text/csv")


def pagina_consulta():
    topo()
    titulo("Consulta aos dados", "Faça uma pergunta em linguagem natural sobre os dados da Farmazids.")
    with st.form("form_consulta", border=True):
        c1, c2 = st.columns([5, 1.3], vertical_alignment="bottom")
        pergunta = c1.text_input("Sua pergunta", key="consulta_pergunta", placeholder="Digite sua pergunta sobre os dados")
        enviar = c2.form_submit_button("Perguntar", type="primary", **ESTICAR_FORM)

    if enviar:
        pergunta = pergunta.strip()
        if not pergunta:
            st.warning("Digite uma pergunta para consultar.")
        else:
            try:
                with st.spinner("Analisando os dados..."):
                    saida = consultar(pergunta)
            except Exception as e:
                st.error(erro_amigavel(e))
                with st.expander("Detalhes técnicos"):
                    st.code(str(e))
            else:
                quando = datetime.now().isoformat(timespec="seconds")
                resposta, linhas = saida.get("resposta"), saida.get("linhas") or []
                salvar_pergunta(st.session_state.usuario, pergunta, resposta, linhas, quando)
                st.session_state.resultado = {"pergunta": pergunta, "resposta": resposta, "linhas": linhas, "quando": quando}
                st.rerun()  # atualiza as consultas recentes no menu

    if st.session_state.get("resultado"):
        mostrar_resultado(st.session_state.resultado)
    else:
        st.markdown(
            "<div class='vazio'><div class='h2'>Faça sua primeira pergunta</div>"
            "<div class='dica'>Seja específico: diga o que quer saber e sobre qual produto, categoria ou período.</div>"
            "<div class='dica'>Peça rankings, comparações ou evolução ao longo do tempo para receber também um gráfico.</div>"
            "<div class='dica'>Suas três consultas mais recentes ficam no menu, para reabrir quando quiser.</div></div>",
            unsafe_allow_html=True,
        )


def pagina_perfil():
    topo()
    titulo("Perfil", "Seus dados de acesso e segurança da conta.")
    aviso()
    esq, dir_ = st.columns([2, 3], gap="large")
    with esq:
        emb = (f"<img alt='Farmazids' src='data:image/png;base64,{img_b64(EMBLEMA)}'>" if EMBLEMA.exists() else "")
        total = total_perguntas(st.session_state.usuario)
        st.markdown(
            f"<div class='perfil'>{emb}<div class='perfil-nome'>{esc(st.session_state.nome)}</div>"
            f"<div class='perfil-user'>@{esc(st.session_state.usuario)}</div>"
            f"<div class='perfil-stat'><b>{total}</b>consulta{'s' if total != 1 else ''} realizada{'s' if total != 1 else ''}</div></div>",
            unsafe_allow_html=True,
        )
        st.button("Sair da conta", key="b_sair", on_click=sair, **ESTICAR)
    with dir_:
        with st.form("form_senha", border=True):
            st.markdown("<div class='h2'>Redefinir senha</div><div class='mudo' style='margin-top:.2rem'>"
                        "Informe a senha atual e escolha uma nova.</div>", unsafe_allow_html=True)
            atual = st.text_input("Senha atual", key="senha_atual", type="password", placeholder="Digite sua senha atual")
            c1, c2 = st.columns(2)
            nova = c1.text_input("Nova senha", key="nova_senha", type="password", placeholder="Mínimo de 6 caracteres")
            conf = c2.text_input("Confirmar nova senha", key="nova_conf", type="password", placeholder="Repita a nova senha")
            ok = st.form_submit_button("Salvar nova senha", type="primary", **ESTICAR_FORM)

        if ok:
            if not autenticar(st.session_state.usuario, atual):
                st.error("A senha atual está incorreta.")
            elif len(nova) < 6:
                st.error("A nova senha precisa ter pelo menos 6 caracteres.")
            elif nova != conf:
                st.error("As senhas novas não conferem.")
            else:
                trocar_senha(st.session_state.usuario, nova)
                st.session_state.aviso = ("success", "Senha alterada com sucesso.")
                st.rerun()


PAGINAS = {"login": pagina_login, "cadastro": pagina_cadastro, "consulta": pagina_consulta, "perfil": pagina_perfil}


def main():
    st.set_page_config(page_title="Farmazids", page_icon=str(EMBLEMA) if EMBLEMA.exists() else "🌿",
                       layout="wide", initial_sidebar_state="expanded")
    iniciar_db()
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("pagina", "login")
    st.session_state.setdefault("menu_aberto", True)
    if "usuario" not in st.session_state and st.session_state.pagina not in ("login", "cadastro"):
        ir("login")
    if st.session_state.pagina in ("consulta", "perfil") and st.session_state.get("menu_aberto"):
        menu_lateral()
    PAGINAS[st.session_state.pagina]()


main()
