# -*- coding: utf-8 -*-
"""
SIGO -- Pesquisa de Formandos por NIF
Deploy: Streamlit Cloud (https://streamlit.io/cloud)
"""

from __future__ import annotations

import io
import os
import re
import threading
import csv

import streamlit as st
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from sigo.modules.formandos import SEL_PESQ, Formando
from sigo.config import CREDENTIALS, LOGIN_URL, SELECTORS

# ── Configuração da página ────────────────────────────────────────────────────

st.set_page_config(
    page_title="SIGO · Pesquisa de Formandos",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ─────────────────────────────────────────────────────────

st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #003876; }
  [data-testid="stSidebar"] * { color: #fff !important; }
  [data-testid="stSidebar"] .stTextInput input { color: #000 !important; }
  .sigo-header { color: #003876; font-weight: 700; }
  .status-ok  { color: #28a745; font-weight: 600; }
  .status-err { color: #dc3545; font-weight: 600; }
  div[data-testid="metric-container"] { background: #f8f9fa; border-radius: .5rem; padding: .5rem; }
</style>
""", unsafe_allow_html=True)

# ── Password ──────────────────────────────────────────────────────────────────

def _check_password() -> bool:
    """Bloqueia o acesso sem password correcta. Lê de st.secrets ou variável de ambiente."""
    app_pw = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", ""))
    if not app_pw:
        return True  # sem password configurada, acesso livre

    if st.session_state.get("autenticado"):
        return True

    st.sidebar.markdown("## 🔒 Acesso Restrito")
    pw = st.sidebar.text_input("Password", type="password", key="input_pw")
    if st.sidebar.button("Entrar"):
        if pw == app_pw:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.sidebar.error("Password incorrecta.")
    return False

# ── Sessão SIGO (partilhada por todos os utilizadores) ───────────────────────

_sigo_lock = threading.Lock()

@st.cache_resource(show_spinner="A iniciar sessão SIGO...")
def _init_sigo() -> dict:
    """
    Lança um browser Chromium e autentica no SIGO.
    Executado uma única vez; partilhado por todas as sessões Streamlit.
    """
    # Credenciais carregadas em runtime (secrets já disponíveis aqui)
    sigo_user = st.secrets.get("SIGO_USER", os.getenv("SIGO_USER", ""))
    sigo_pass = st.secrets.get("SIGO_PASS", os.getenv("SIGO_PASS", ""))

    if not sigo_user or not sigo_pass:
        return {"pw": None, "browser": None, "context": None, "page": None,
                "ok": False, "msg": "Credenciais SIGO não configuradas (definir SIGO_USER e SIGO_PASS nos Secrets)"}

    pw = sync_playwright().start()

    # Em Streamlit Cloud usa o Chromium do sistema (packages.txt).
    # Localmente usa o Playwright bundled.
    chromium_path = next(
        (p for p in ["/usr/bin/chromium", "/usr/bin/chromium-browser"] if os.path.exists(p)),
        None
    )
    launch_kwargs: dict = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process",
        ],
    }
    if chromium_path:
        launch_kwargs["executable_path"] = chromium_path

    browser: Browser = pw.chromium.launch(**launch_kwargs)
    context: BrowserContext = browser.new_context()
    context.set_default_timeout(60_000)   # 60s — cloud pode ser lento
    page: Page = context.new_page()

    try:
        page.goto(LOGIN_URL, timeout=60_000)
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.fill(SELECTORS["username"], sigo_user)
        page.fill(SELECTORS["password"], sigo_pass)
        page.click(SELECTORS["submit_button"])
        page.wait_for_url("**/Inicio.jsp", timeout=30_000)
        ok = True
        msg = "Sessão SIGO activa"
    except Exception as exc:
        ok = False
        msg = f"Falha no login: {exc}"

    return {"pw": pw, "browser": browser, "context": context, "page": page,
            "ok": ok, "msg": msg}


def _pesquisar_nif(nif: str) -> list[Formando]:
    """
    Pesquisa o NIF no SIGO e devolve lista de Formando.
    Usa lock para serializar acessos ao browser.
    """
    sigo = _init_sigo()
    page: Page = sigo["page"]

    URL = "https://www.sigo.pt/alunos/GestaoAlunos.jsp"
    JS_LER = """
    (() => {
        const rows = Array.from(document.querySelectorAll('#form1\\:table1 tbody tr'));
        return rows.map(r => {
            const cells = Array.from(r.querySelectorAll('td'));
            if (cells.length < 5) return null;
            return {
                n_sigo:          cells[0]?.innerText?.trim() ?? '',
                nif:             cells[1]?.innerText?.trim() ?? '',
                nome:            cells[2]?.innerText?.trim() ?? '',
                n_identificacao: cells[3]?.innerText?.trim() ?? '',
                data_nascimento: cells[4]?.innerText?.trim() ?? '',
            };
        }).filter(Boolean);
    })()
    """

    with _sigo_lock:
        if URL not in page.url:
            page.goto(URL)
            page.wait_for_load_state("networkidle")

        # Limpar campos
        for sel in [SEL_PESQ["n_sigo"], SEL_PESQ["nome"],
                    SEL_PESQ["n_identificacao"], SEL_PESQ["nif"],
                    SEL_PESQ["data_nascimento"]]:
            page.fill(sel, "")

        page.fill(SEL_PESQ["nif"], nif)
        page.click(SEL_PESQ["lnk_pesquisar"])
        page.wait_for_load_state("networkidle")

        raw = page.evaluate(JS_LER)

    return [Formando(**r) for r in raw]


def _re_login():
    """Limpa a cache e força nova sessão SIGO."""
    _init_sigo.clear()
    st.rerun()


# ── Interface ─────────────────────────────────────────────────────────────────

if not _check_password():
    st.stop()

# Sidebar
with st.sidebar:
    st.markdown("## 🎓 SIGO")
    st.markdown("**Pesquisa de Formandos**")
    st.divider()

    sigo = _init_sigo()
    if sigo["ok"]:
        st.markdown(f'<p class="status-ok">● {sigo["msg"]}</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="status-err">● {sigo["msg"]}</p>', unsafe_allow_html=True)
        if st.button("🔄 Re-ligar"):
            _re_login()
            st.rerun()

    st.divider()
    if st.button("🗑️ Limpar histórico"):
        st.session_state["historico"] = []
        st.rerun()

# Inicializar histórico
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# Cabeçalho
st.markdown('<h2 class="sigo-header">Pesquisa de Formandos por NIF</h2>', unsafe_allow_html=True)

# Estatísticas
historico: list[dict] = st.session_state["historico"]
total = len(historico)
encontrados = sum(1 for h in historico if h["encontrado"])

if total > 0:
    c1, c2, c3 = st.columns(3)
    c1.metric("Pesquisas", total)
    c2.metric("Encontrados", encontrados)
    c3.metric("Não encontrados", total - encontrados)
    st.divider()

# Formulário de pesquisa
with st.form("form_pesquisa", clear_on_submit=True):
    col_inp, col_btn = st.columns([3, 1])
    nif_input = col_inp.text_input(
        "NIF", placeholder="000000000",
        max_chars=9, label_visibility="collapsed",
        help="9 dígitos numéricos"
    )
    submeter = col_btn.form_submit_button("🔍 Pesquisar", use_container_width=True)

if submeter:
    nif = nif_input.strip().replace(" ", "")

    if not re.fullmatch(r"\d{9}", nif):
        st.error("NIF inválido — deve ter exactamente 9 dígitos numéricos.")
    elif not sigo["ok"]:
        st.error(f"SIGO indisponível: {sigo['msg']}")
    else:
        with st.spinner("A pesquisar no SIGO..."):
            try:
                resultados = _pesquisar_nif(nif)
            except Exception as exc:
                # Tentar re-login
                try:
                    _re_login()
                    resultados = _pesquisar_nif(nif)
                except Exception:
                    st.error(f"Erro ao pesquisar: {exc}")
                    st.stop()

        if resultados:
            for f in resultados:
                st.session_state["historico"].append({
                    "nif_pesq": nif,
                    "encontrado": True,
                    "nome": f.nome,
                    "n_sigo": f.n_sigo,
                })
            st.success(f"✅ Encontrado: **{resultados[0].nome}** — SIGO `{resultados[0].n_sigo}`")
        else:
            st.session_state["historico"].append({
                "nif_pesq": nif,
                "encontrado": False,
                "nome": "",
                "n_sigo": "",
            })
            st.warning(f"Nenhum formando encontrado com NIF **{nif}**.")

        st.rerun()

# Tabela de resultados
if historico:
    st.subheader("Resultados")

    # Preparar dados para tabela
    import pandas as pd
    df = pd.DataFrame([
        {
            "NIF": h["nif_pesq"],
            "Estado": "✅ Registado" if h["encontrado"] else "❌ Não encontrado",
            "Nome": h["nome"],
            "Nº SIGO": h["n_sigo"],
        }
        for h in historico
    ])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Export CSV
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["NIF", "Estado", "Nome", "Nº SIGO"])
    for h in historico:
        writer.writerow([
            h["nif_pesq"],
            "Registado" if h["encontrado"] else "Não encontrado",
            h["nome"],
            h["n_sigo"],
        ])

    st.download_button(
        label="⬇️ Exportar CSV",
        data="\ufeff" + buf.getvalue(),  # BOM UTF-8 para Excel
        file_name="sigo_formandos.csv",
        mime="text/csv",
    )
