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

import boto3
import pandas as pd
import streamlit as st

# --- AJUSTE AQUI ---
STATE_MACHINE_ARN = "arn:aws:states:us-east-2:906513713169:stateMachine:farmazids-t1-equipe-06-bedrockV2"
REGIAO = "us-east-2"
# -------------------

BASE = Path(__file__).parent
DB = BASE / "farmazids.db"
LOGO = BASE / "logo.png"          # logo "FARMAZIDS MEDICINA ORIENTAL"
EMBLEMA = BASE / "emblema.png"    # emblema redondo
USUARIO_OK = re.compile(r"^[a-z0-9_.-]{3,30}$")


def _esticar(fn):
    """Faz o botão ocupar toda a largura, em qualquer versão do Streamlit."""
    return {"width": "stretch"} if "width" in inspect.signature(fn).parameters else {"use_container_width": True}


ESTICAR = _esticar(st.button)
ESTICAR_FORM = _esticar(st.form_submit_button)

CSS = """<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700;800&family=Poppins:wght@400;500&display=swap');
:root { --roxo:#42205A; --dourado:#C9AD7A; --cinza:#C9D0DA; --fundo:#FBF9F4; --lilas:#D8C3EE; }
.stApp { background:var(--fundo); color:#2b2b2b; }
[data-testid="stToolbar"] { display:none; }
[data-testid="stDecoration"], footer { display:none; }
[data-testid="stHeader"] { background:transparent; }
.block-container { max-width:980px; padding-top:1.5rem; }

/* textos */
.titulo { font-family:'Cinzel',serif; font-weight:800; color:var(--roxo); text-align:center; font-size:2.3rem; margin:.4rem 0 1.4rem; }
.rotulo { font-family:'Cinzel',serif; font-weight:700; color:var(--roxo); font-size:1.35rem; margin:.9rem 0 .3rem; }
.sub { font-family:'Cinzel',serif; font-weight:700; color:var(--roxo); font-size:1.2rem; margin:1.2rem 0 .3rem; }
.linha { border:0; border-top:3px solid var(--roxo); margin:.6rem 1rem 1rem; opacity:1; }
.nao-cadastrou { text-align:right; font-family:'Poppins',sans-serif; color:var(--dourado); margin:.8rem 0 .5rem; }
.campo-nome { background:var(--cinza); border-radius:999px; padding:.85rem 2rem; font-family:'Cinzel',serif; font-weight:700; font-size:1.4rem; color:var(--roxo); margin-bottom:2rem; }

/* logos */
.logo-img { text-align:center; }
.logo-img img { width:100%; max-width:520px; height:auto; }
.emb { display:flex; align-items:center; }
.emb-dir { justify-content:flex-end; }
.emb-esq { justify-content:flex-start; }
.emb img { width:72px; height:72px; }
.logo-txt { text-align:center; line-height:1.1; }
.logo-a { font-family:'Cinzel',serif; font-weight:800; font-size:3rem; color:var(--roxo); }
.logo-b { font-family:'Cinzel',serif; font-weight:600; font-size:1.4rem; letter-spacing:.2em; color:var(--dourado); }

/* campos */
div[data-baseweb="input"] { background:var(--cinza); border:2px solid transparent !important; border-radius:999px; box-shadow:none; }
div[data-baseweb="input"]:focus-within { border-color:var(--roxo) !important; box-shadow:none; }
div[data-baseweb="base-input"] { background:transparent; }
[data-testid="stTextInput"] input { text-align:center; height:3.3rem; font-family:'Poppins',sans-serif; font-size:1.05rem; color:var(--roxo); }
[data-testid="stTextInput"] input::placeholder { color:#8a8f98; }

/* botões (pílula roxa) */
.stButton, [data-testid="stFormSubmitButton"] { width:100%; }
.stButton button, [data-testid="stFormSubmitButton"] button { width:100% !important; background:var(--roxo); border:none; border-radius:999px; height:3.3rem; }
.stButton button p, [data-testid="stFormSubmitButton"] button p { color:var(--dourado); font-family:'Cinzel',serif; font-weight:700; font-size:1.5rem; }
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover { background:#5a2d7a; }

/* botões redondos: voltar, menu e fechar */
.st-key-voltar button, .st-key-menu button, .st-key-fechar button { width:62px !important; height:62px; border-radius:50%; padding:0; }
.st-key-voltar button, .st-key-fechar button { background:var(--dourado); }
.st-key-menu button { background:var(--roxo); }
.st-key-voltar button p, .st-key-fechar button p { color:var(--roxo); font-size:2rem; line-height:1; }
.st-key-menu button p { color:var(--dourado); font-size:2rem; line-height:1; }
.st-key-voltar button:hover, .st-key-fechar button:hover { background:#d9be8e; }
.st-key-fechar { display:flex; justify-content:flex-end; }

/* menu lateral (aberto pelo botão de menu; os controles nativos ficam escondidos) */
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"], [data-testid="stSidebarHeader"] { display:none !important; }
section[data-testid="stSidebar"] { background:var(--roxo); width:340px !important; min-width:340px !important; max-width:340px !important; }
[data-testid="stSidebar"] .stButton button { background:transparent; height:auto; padding:.5rem 0; border-radius:8px; }
[data-testid="stSidebar"] .stButton button p { color:var(--lilas); font-size:1.25rem; text-align:center; }
[data-testid="stSidebar"] .stButton button:hover { background:rgba(255,255,255,.1); }
[data-testid="stSidebar"] .st-key-fechar button { background:var(--dourado); height:62px; padding:0; }
[data-testid="stSidebar"] .st-key-fechar button:hover { background:#d9be8e; }
[data-testid="stSidebar"] .st-key-fechar button p { color:var(--roxo); font-size:2rem; }
[data-testid="stSidebar"] .st-key-perfil button p, [data-testid="stSidebar"] .st-key-sair button p { color:var(--dourado); }
.side-titulo { font-family:'Cinzel',serif; font-weight:700; font-size:1.3rem; color:var(--dourado); text-align:center; margin:1rem 0; }
.side-vazio { color:var(--lilas); text-align:center; font-family:'Poppins',sans-serif; font-size:.9rem; }
.side-linha { border:0; border-top:2px solid var(--dourado); margin:1.2rem 1rem; opacity:1; }
</style>"""


# ---------- banco de dados (SQLite local) ----------
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


def salvar_pergunta(usuario, pergunta, saida):
    with conexao() as con:
        con.execute(
            "INSERT INTO perguntas (usuario, pergunta, resposta, linhas, sql, criada_em) VALUES (?,?,?,?,?,?)",
            (usuario, pergunta, saida.get("resposta"), json.dumps(saida.get("linhas", []), ensure_ascii=False),
             saida.get("sql"), datetime.now().isoformat(timespec="seconds")),
        )


def listar_perguntas(usuario, limite=15):
    with conexao() as con:
        return con.execute(
            "SELECT id, pergunta FROM perguntas WHERE usuario=? ORDER BY id DESC LIMIT ?", (usuario, limite)
        ).fetchall()


# ---------- chamada à state machine ----------
@st.cache_resource
def cliente_sfn():
    return boto3.client("stepfunctions", region_name=REGIAO)


def consultar(pergunta):
    r = cliente_sfn().start_sync_execution(
        stateMachineArn=STATE_MACHINE_ARN, input=json.dumps({"pergunta": pergunta})
    )
    if r["status"] != "SUCCEEDED":
        raise RuntimeError(r.get("cause") or r.get("error") or r["status"])
    return json.loads(r["output"])


# ---------- navegação e estado ----------
def ir(pagina):
    st.session_state.pagina = pagina
    st.session_state.menu_aberto = False


def alternar_menu():
    st.session_state.menu_aberto = not st.session_state.get("menu_aberto", False)


def sair():
    for k in ("usuario", "nome", "resultado"):
        st.session_state.pop(k, None)
    ir("login")


def abrir_pergunta(id_):
    with conexao() as con:
        p = con.execute(
            "SELECT * FROM perguntas WHERE id=? AND usuario=?", (id_, st.session_state.usuario)
        ).fetchone()
    if p:
        st.session_state.resultado = {
            "pergunta": p["pergunta"], "resposta": p["resposta"],
            "linhas": json.loads(p["linhas"] or "[]"), "sql": p["sql"],
        }


# ---------- componentes visuais ----------
def titulo(texto):
    st.markdown(f"<div class='titulo'>{texto}</div>", unsafe_allow_html=True)


def rotulo(texto):
    st.markdown(f"<div class='rotulo'>{texto}</div>", unsafe_allow_html=True)


def aviso():
    msg = st.session_state.pop("aviso", None)
    if msg:
        getattr(st, msg[0])(msg[1])


@lru_cache(maxsize=None)
def img_b64(caminho):
    return base64.b64encode(Path(caminho).read_bytes()).decode()


def logo():
    if LOGO.exists():
        st.markdown(f"<div class='logo-img'><img src='data:image/png;base64,{img_b64(LOGO)}'></div>",
                    unsafe_allow_html=True)
    else:
        st.markdown("<div class='logo-txt'><div class='logo-a'>FARMAZIDS</div>"
                    "<div class='logo-b'>MEDICINA ORIENTAL</div></div>", unsafe_allow_html=True)


def emblema(lado):
    if EMBLEMA.exists():
        st.markdown(f"<div class='emb emb-{lado}'><img src='data:image/png;base64,{img_b64(EMBLEMA)}'></div>",
                    unsafe_allow_html=True)


def cabecalho(esquerda="emblema", destino=None, linha=True):
    c1, c2, c3 = st.columns([1, 4, 1], vertical_alignment="center")
    with c1:
        if esquerda == "voltar":
            st.button("←", key="voltar", on_click=ir, args=(destino,))
        elif esquerda == "menu":
            st.button("☰", key="menu", on_click=alternar_menu)
        elif esquerda == "emblema":
            emblema("esq")
    with c2:
        logo()
    with c3:
        emblema("dir")
    if linha:
        st.markdown("<hr class='linha'>", unsafe_allow_html=True)


# ---------- páginas ----------
def pagina_login():
    cabecalho("emblema")
    titulo("ENTRAR")
    aviso()
    with st.form("form_login", border=False):
        rotulo("NOME DE USUÁRIO")
        usuario = st.text_input("usuario", key="login_usuario", placeholder="Digite seu nome de usuário",
                                label_visibility="collapsed")
        rotulo("SENHA")
        senha = st.text_input("senha", key="login_senha", type="password", placeholder="Digite sua senha",
                              label_visibility="collapsed")
        st.markdown("<div class='nao-cadastrou'>Não se cadastrou?</div>", unsafe_allow_html=True)
        c1, _, c2 = st.columns([5, 2, 5])
        entrar = c1.form_submit_button("ENTRAR", **ESTICAR_FORM)
        cadastrar = c2.form_submit_button("CADASTRAR", **ESTICAR_FORM)

    if cadastrar:
        ir("cadastro")
        st.rerun()
    if entrar:
        usuario = usuario.strip().lower()
        nome = autenticar(usuario, senha)
        if nome:
            st.session_state.update(usuario=usuario, nome=nome, resultado=None)
            ir("consulta")
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")


def pagina_cadastro():
    cabecalho("voltar", destino="login")
    titulo("CADASTRAR")
    with st.form("form_cadastro", border=False):
        rotulo("NOME")
        nome = st.text_input("nome", key="cad_nome", placeholder="Digite seu nome", label_visibility="collapsed")
        rotulo("NOME DE USUÁRIO")
        usuario = st.text_input("usuario", key="cad_usuario", placeholder="Escolha um nome de usuário",
                                label_visibility="collapsed")
        rotulo("SENHA")
        senha = st.text_input("senha", key="cad_senha", type="password", placeholder="Mínimo de 6 caracteres",
                              label_visibility="collapsed")
        rotulo("CONFIRMAR SENHA")
        conf = st.text_input("confirmar", key="cad_conf", type="password", placeholder="Confirme sua senha",
                             label_visibility="collapsed")
        st.write("")
        ok = st.columns([1, 2, 1])[1].form_submit_button("CADASTRAR", **ESTICAR_FORM)

    if ok:
        usuario = usuario.strip().lower()
        if not (nome.strip() and usuario and senha):
            st.error("Preencha todos os campos.")
        elif not USUARIO_OK.match(usuario):
            st.error("Usuário: 3 a 30 caracteres, só letras, números, ponto, hífen ou _.")
        elif len(senha) < 6:
            st.error("A senha precisa ter pelo menos 6 caracteres.")
        elif senha != conf:
            st.error("As senhas não conferem.")
        elif not criar_usuario(nome.strip(), usuario, senha):
            st.error("Esse nome de usuário já existe.")
        else:
            st.session_state.aviso = ("success", "Cadastro realizado! Faça login.")
            ir("login")
            st.rerun()


def menu_lateral():
    """Só é chamado com o menu aberto; sem chamada, o Streamlit não desenha a barra lateral."""
    with st.sidebar:
        st.button("←", key="fechar", on_click=alternar_menu)
        st.markdown("<div class='side-titulo'>Perguntas Anteriores</div>", unsafe_allow_html=True)
        perguntas = listar_perguntas(st.session_state.usuario)
        if not perguntas:
            st.markdown("<div class='side-vazio'>Nenhuma pergunta ainda.</div>", unsafe_allow_html=True)
        for p in perguntas:
            texto = p["pergunta"] if len(p["pergunta"]) <= 28 else p["pergunta"][:27] + "…"
            st.button(texto, key=f"hist_{p['id']}", on_click=abrir_pergunta, args=(p["id"],), **ESTICAR)
        st.markdown("<hr class='side-linha'>", unsafe_allow_html=True)
        st.button("Perfil", key="perfil", on_click=ir, args=("perfil",), **ESTICAR)
        st.markdown("<hr class='side-linha'>", unsafe_allow_html=True)
        st.button("Sair", key="sair", on_click=sair, **ESTICAR)


def mostrar_resultado(res):
    st.markdown("<hr class='linha'>", unsafe_allow_html=True)
    st.markdown("<div class='sub'>PERGUNTA</div>", unsafe_allow_html=True)
    st.write(res["pergunta"])
    st.markdown("<div class='sub'>RESPOSTA</div>", unsafe_allow_html=True)
    st.write(res["resposta"])
    if res["linhas"]:
        st.markdown("<div class='sub'>TABELA</div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(res["linhas"]))
    if res["sql"]:
        st.markdown("<div class='sub'>SQL</div>", unsafe_allow_html=True)
        st.code(res["sql"], language="sql")


def pagina_consulta():
    aberto = st.session_state.get("menu_aberto", False)
    if aberto:
        menu_lateral()
    cabecalho("nenhum" if aberto else "menu", linha=False)
    titulo("Consulta aos dados")
    with st.form("form_consulta", border=False):
        pergunta = st.text_input("pergunta", key="consulta_pergunta", placeholder="Qual a sua pergunta?",
                                 label_visibility="collapsed")
        enviar = st.columns([1, 1, 1])[1].form_submit_button("PERGUNTAR", **ESTICAR_FORM)

    if enviar and pergunta.strip():
        pergunta = pergunta.strip()
        try:
            with st.spinner("Consultando..."):
                saida = consultar(pergunta)
            salvar_pergunta(st.session_state.usuario, pergunta, saida)
            st.session_state.resultado = {
                "pergunta": pergunta, "resposta": saida.get("resposta"),
                "linhas": saida.get("linhas", []), "sql": saida.get("sql"),
            }
            st.rerun()  # atualiza a lista de perguntas anteriores no menu
        except Exception as e:
            st.error(f"Não foi possível consultar: {e}")

    if st.session_state.get("resultado"):
        mostrar_resultado(st.session_state.resultado)
    else:
        st.markdown("<hr class='linha'>", unsafe_allow_html=True)


def pagina_perfil():
    cabecalho("voltar", destino="consulta")
    titulo("SEU PERFIL")
    aviso()
    rotulo("Nome:")
    st.markdown(f"<div class='campo-nome'>{html.escape(st.session_state.nome)}</div>", unsafe_allow_html=True)
    c1, _, c2 = st.columns([5, 1, 5])
    c1.button("REDEFINIR SENHA", key="b_redefinir", on_click=ir, args=("senha",), **ESTICAR)
    c2.button("SAIR", key="b_sair", on_click=sair, **ESTICAR)


def pagina_senha():
    cabecalho("voltar", destino="perfil")
    titulo("REDEFINIR SENHA")
    with st.form("form_senha", border=False):
        rotulo("NOVA SENHA")
        nova = st.text_input("nova", key="nova_senha", type="password", placeholder="Digite sua nova senha",
                             label_visibility="collapsed")
        rotulo("CONFIRMAR SENHA")
        conf = st.text_input("confirmar", key="nova_conf", type="password", placeholder="Confirme sua nova senha",
                             label_visibility="collapsed")
        st.write("")
        ok = st.columns([1, 2, 1])[1].form_submit_button("REDEFINIR SENHA", **ESTICAR_FORM)

    if ok:
        if len(nova) < 6:
            st.error("A senha precisa ter pelo menos 6 caracteres.")
        elif nova != conf:
            st.error("As senhas não conferem.")
        else:
            trocar_senha(st.session_state.usuario, nova)
            st.session_state.aviso = ("success", "Senha redefinida com sucesso.")
            ir("perfil")
            st.rerun()


PAGINAS = {
    "login": pagina_login, "cadastro": pagina_cadastro, "consulta": pagina_consulta,
    "perfil": pagina_perfil, "senha": pagina_senha,
}


def main():
    st.set_page_config(page_title="Farmazids", page_icon=str(EMBLEMA) if EMBLEMA.exists() else "🌿",
                       layout="wide", initial_sidebar_state="expanded")
    iniciar_db()
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("pagina", "login")
    if "usuario" not in st.session_state and st.session_state.pagina not in ("login", "cadastro"):
        ir("login")
    PAGINAS[st.session_state.pagina]()


main()
