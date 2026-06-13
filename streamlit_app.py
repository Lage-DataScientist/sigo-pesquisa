# -*- coding: utf-8 -*-
"""
SIGO -- Pesquisa de Formandos por NIF
Deploy: Streamlit Cloud (https://streamlit.io/cloud)
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import threading
import csv

import streamlit as st
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from sigo.modules.formandos import SEL_PESQ, Formando
from sigo.config import LOGIN_URL, SELECTORS

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Reset global */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer, header { visibility: hidden; }

/* Fundo */
.stApp { background: #f0f4f8; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1f45 0%, #1a3a6b 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.08);
}
[data-testid="stSidebar"] * { color: #e8edf5 !important; }
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: #fff !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.15) !important; }
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: #fff !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all .2s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.22) !important;
}

/* ── Área principal ── */
.main .block-container { padding: 2rem 2.5rem 3rem !important; max-width: 1100px; }

/* ── Métricas ── */
div[data-testid="metric-container"] {
    background: #fff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    padding: 1.2rem 1.5rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
div[data-testid="metric-container"] label { color: #64748b !important; font-size: .8rem !important; font-weight: 600 !important; text-transform: uppercase; letter-spacing: .05em; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #0f172a !important; font-size: 2rem !important; font-weight: 700 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #e2e8f0;
    border-radius: 12px;
    padding: 4px;
    gap: 2px;
    border-bottom: none !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px !important;
    padding: 8px 22px !important;
    font-weight: 600 !important;
    font-size: .88rem !important;
    color: #475569 !important;
    border: none !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: #fff !important;
    color: #1a3a6b !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #cbd5e1 !important;
    border-radius: 14px !important;
    background: #fff !important;
    padding: 1rem !important;
    transition: border-color .2s !important;
}
[data-testid="stFileUploader"]:hover { border-color: #1a3a6b !important; }

/* ── Botões principais ── */
.stButton > button, .stFormSubmitButton > button {
    background: linear-gradient(135deg, #1a3a6b 0%, #2563eb 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: .9rem !important;
    padding: .6rem 1.4rem !important;
    box-shadow: 0 2px 8px rgba(26,58,107,0.25) !important;
    transition: all .2s !important;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
    box-shadow: 0 4px 16px rgba(26,58,107,0.35) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:disabled { background: #94a3b8 !important; box-shadow: none !important; transform: none !important; }

/* ── Download button ── */
[data-testid="stDownloadButton"] > button {
    background: #fff !important;
    color: #1a3a6b !important;
    border: 2px solid #1a3a6b !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    box-shadow: none !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: #f0f4f8 !important;
    box-shadow: 0 2px 8px rgba(26,58,107,0.15) !important;
}

/* ── Text area e selectbox ── */
.stTextArea textarea, .stSelectbox select, [data-baseweb="select"] {
    border-radius: 10px !important;
    border: 1.5px solid #cbd5e1 !important;
    background: #fff !important;
}
.stTextArea textarea:focus { border-color: #1a3a6b !important; box-shadow: 0 0 0 3px rgba(26,58,107,0.12) !important; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border-radius: 14px !important; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }

/* ── Alertas ── */
[data-testid="stAlert"] { border-radius: 10px !important; }

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div { background: linear-gradient(90deg, #1a3a6b, #2563eb) !important; border-radius: 99px; }

/* ── Badges de estado ── */
.badge-ok  { display:inline-block; background:#dcfce7; color:#166534; padding:2px 10px; border-radius:99px; font-size:.82rem; font-weight:600; }
.badge-err { display:inline-block; background:#fee2e2; color:#991b1b; padding:2px 10px; border-radius:99px; font-size:.82rem; font-weight:600; }
.badge-conn{ display:inline-block; padding:4px 12px; border-radius:99px; font-size:.82rem; font-weight:600; }
.badge-conn.ok  { background:rgba(22,163,74,.2); color:#bbf7d0; }
.badge-conn.err { background:rgba(239,68,68,.2); color:#fca5a5; }
</style>
""", unsafe_allow_html=True)

# ── Password ──────────────────────────────────────────────────────────────────

def _check_password() -> bool:
    app_pw = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", ""))
    if not app_pw:
        return True
    if st.session_state.get("autenticado"):
        return True
    st.sidebar.markdown("""
        <div style="text-align:center; padding: 1.5rem 0 1rem;">
            <div style="font-size:2.5rem;">🔒</div>
            <div style="font-size:1.1rem; font-weight:700; color:#fff; margin-top:.5rem;">Acesso Restrito</div>
            <div style="font-size:.82rem; color:rgba(255,255,255,.6); margin-top:.3rem;">Introduza a password para continuar</div>
        </div>
    """, unsafe_allow_html=True)
    pw = st.sidebar.text_input("Password", type="password", key="input_pw", label_visibility="collapsed", placeholder="Password…")
    if st.sidebar.button("Entrar", use_container_width=True):
        if pw == app_pw:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.sidebar.error("Password incorrecta.")
    return False

# ── Event loop persistente para o Playwright async API ───────────────────────
# O Playwright async API precisa de um event loop asyncio persistente.
# Criamos uma thread dedicada que corre esse loop indefinidamente.
# Todas as operações Playwright são coroutines submetidas a esse loop via
# asyncio.run_coroutine_threadsafe(), que é thread-safe.

class _LoopThread:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._t = threading.Thread(
            target=self._run, daemon=True, name="pw-loop"
        )
        self._t.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def submit(self, coro, timeout: int = 120):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

@st.cache_resource
def _loop_thread() -> _LoopThread:
    return _LoopThread()

def _pw(coro, timeout: int = 120):
    """Submete uma coroutine ao loop Playwright e devolve o resultado."""
    return _loop_thread().submit(coro, timeout=timeout)

# ── Sessão SIGO ───────────────────────────────────────────────────────────────

def _get_credentials() -> tuple[str, str]:
    try:
        user = st.secrets.get("SIGO_USER", "") or os.getenv("SIGO_USER", "")
        pwd  = st.secrets.get("SIGO_PASS", "") or os.getenv("SIGO_PASS", "")
    except Exception:
        user = os.getenv("SIGO_USER", "")
        pwd  = os.getenv("SIGO_PASS", "")
    return user, pwd

@st.cache_resource(show_spinner="A iniciar sessão SIGO...")
def _init_sigo(sigo_user: str, sigo_pass: str) -> dict:
    if not sigo_user or not sigo_pass:
        return {"pw": None, "browser": None, "context": None, "page": None,
                "ok": False, "msg": "Credenciais SIGO não configuradas (definir SIGO_USER e SIGO_PASS nos Secrets)",
                "jsessionid": ""}

    async def _do() -> dict:
        chromium_path = next(
            (p for p in ["/usr/bin/chromium", "/usr/bin/chromium-browser"] if os.path.exists(p)),
            None
        )
        launch_kwargs: dict = {
            "headless": True,
            "args": [
                "--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
                "--disable-gpu", "--single-process",
                "--disable-extensions", "--disable-plugins",
                "--disable-background-networking", "--disable-breakpad",
                "--disable-default-apps", "--disable-sync", "--disable-translate",
                "--no-first-run", "--no-default-browser-check",
                "--safebrowsing-disable-auto-update", "--password-store=basic",
            ],
        }
        if chromium_path:
            launch_kwargs["executable_path"] = chromium_path

        pw = await async_playwright().start()
        browser: Browser = await pw.chromium.launch(**launch_kwargs)
        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        context.set_default_timeout(60_000)
        page: Page = await context.new_page()

        try:
            await page.goto(LOGIN_URL, timeout=60_000)
            await page.wait_for_selector(SELECTORS["username"], state="visible", timeout=30_000)
            await page.fill(SELECTORS["username"], sigo_user)
            await page.fill(SELECTORS["password"], sigo_pass)
            async with page.expect_navigation(wait_until="networkidle", timeout=60_000):
                await page.evaluate("document.querySelector('#form1\\\\:btLogin').click()")
            logged_in = (
                await page.locator("text=Bem-vindos").count() > 0
                or "Inicio" in page.url
                or await page.locator(SELECTORS["submit_button"]).count() == 0
            )
            if logged_in:
                ok, msg = True, "Sessão SIGO activa"
                _m = re.search(r';jsessionid=([^?#&]+)', page.url)
                jsessionid = _m.group(1) if _m else ""
            else:
                ok, msg, jsessionid = False, "Login falhou — verifique as credenciais SIGO nos Secrets", ""
        except Exception as exc:
            ok, msg, jsessionid = False, f"Falha no login: {exc}", ""

        return {"pw": pw, "browser": browser, "context": context, "page": page,
                "ok": ok, "msg": msg, "jsessionid": jsessionid}

    return _pw(_do())


def _pesquisar_nif(nif: str) -> list[Formando]:
    sigo = _init_sigo(*_get_credentials())
    if not sigo["ok"]:
        raise RuntimeError(sigo["msg"])

    page: Page       = sigo["page"]
    jsessionid: str  = sigo.get("jsessionid", "")
    URL = "https://www.sigo.pt/alunos/GestaoAlunos.jsp"
    JS_LER = """
    (() => {
        const rows = Array.from(document.querySelectorAll('#form1\\\\:table1 tbody tr'));
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

    async def _do() -> list:
        if URL not in page.url:
            dest = f"{URL};jsessionid={jsessionid}" if jsessionid else URL
            await page.goto(dest)
            await page.wait_for_load_state("networkidle")

        for sel in [SEL_PESQ["n_sigo"], SEL_PESQ["nome"],
                    SEL_PESQ["n_identificacao"], SEL_PESQ["nif"],
                    SEL_PESQ["data_nascimento"]]:
            await page.fill(sel, "")

        await page.fill(SEL_PESQ["nif"], nif)
        async with page.expect_navigation(wait_until="networkidle", timeout=60_000):
            await page.evaluate("document.querySelector('#form1\\\\:ihFiltrar').click()")
        return await page.evaluate(JS_LER)

    raw = _pw(_do())
    return [Formando(**r) for r in raw]


def _re_login():
    _init_sigo.clear()
    st.rerun()


# ── Interface ─────────────────────────────────────────────────────────────────

if not _check_password():
    st.stop()

# Sidebar
with st.sidebar:
    st.markdown("""
        <div style="padding: 1.5rem 0 .5rem; text-align:center;">
            <div style="font-size:2.8rem; line-height:1;">🎓</div>
            <div style="font-size:1.4rem; font-weight:800; color:#fff; margin-top:.6rem; letter-spacing:-.01em;">SIGO</div>
            <div style="font-size:.78rem; color:rgba(255,255,255,.55); margin-top:.2rem; text-transform:uppercase; letter-spacing:.08em;">Pesquisa de Formandos</div>
        </div>
    """, unsafe_allow_html=True)
    st.divider()

    sigo = _init_sigo(*_get_credentials())
    if sigo["ok"]:
        st.markdown('<span class="badge-conn ok">⬤ &nbsp;Sessão activa</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-conn err">⬤ &nbsp;Sessão inactiva</span>', unsafe_allow_html=True)
        st.caption(sigo["msg"])
        if st.button("🔄 Re-ligar", use_container_width=True):
            _re_login()

    st.divider()
    if st.button("🗑️ Limpar resultados", use_container_width=True):
        st.session_state["historico"] = []
        st.rerun()

    st.markdown("""
        <div style="position:absolute; bottom:1.5rem; left:0; right:0; text-align:center;
                    font-size:.72rem; color:rgba(255,255,255,.3);">
            Gomes & Canoso, Lda.
        </div>
    """, unsafe_allow_html=True)

# Inicializar histórico
if "historico" not in st.session_state:
    st.session_state["historico"] = []

# ── Cabeçalho principal ───────────────────────────────────────────────────────
st.markdown("""
<div style="background: linear-gradient(135deg, #0b1f45 0%, #1a3a6b 55%, #2563eb 100%);
            border-radius: 18px; padding: 2rem 2.5rem; margin-bottom: 2rem;
            display: flex; align-items: center; gap: 1.5rem;">
    <div style="background:rgba(255,255,255,0.12); border-radius:14px; padding:1rem; font-size:2.2rem; line-height:1;">🎓</div>
    <div>
        <div style="color:rgba(255,255,255,.6); font-size:.78rem; text-transform:uppercase; letter-spacing:.1em; font-weight:600; margin-bottom:.3rem;">Sistema de Informação</div>
        <div style="color:#fff; font-size:1.6rem; font-weight:800; letter-spacing:-.02em; line-height:1.1;">Pesquisa de Formandos</div>
        <div style="color:rgba(255,255,255,.55); font-size:.85rem; margin-top:.4rem;">Consulte o registo de formandos por NIF</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Estatísticas ──────────────────────────────────────────────────────────────
historico: list[dict] = st.session_state["historico"]
total = len(historico)
encontrados = sum(1 for h in historico if h["encontrado"])

if total > 0:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total pesquisados", total)
    c2.metric("Registados no SIGO", encontrados)
    c3.metric("Não encontrados", total - encontrados)
    st.markdown("<div style='margin-bottom:1rem'></div>", unsafe_allow_html=True)

# Formulário de pesquisa
import pandas as pd

tab_excel, tab_manual = st.tabs(["📂 Carregar Excel", "⌨️ Inserir manualmente"])

with tab_excel:
    ficheiro = st.file_uploader(
        "Ficheiro Excel com NIFs",
        type=["xlsx", "xls"],
        help="O ficheiro deve ter uma coluna com NIFs de 9 dígitos.",
    )
    col_sel, col_btn2 = st.columns([2, 1])
    coluna_nif = None
    df_excel = None

    if ficheiro:
        try:
            df_excel = pd.read_excel(ficheiro, dtype=str)
            # Auto-detectar coluna NIF: primeira coluna onde ≥50% dos valores são 9 dígitos
            def _score_nif(col):
                vals = df_excel[col].dropna().str.strip().str.replace(r"\s", "", regex=True)
                return vals.str.fullmatch(r"\d{9}").mean()
            scores = {c: _score_nif(c) for c in df_excel.columns}
            melhor = max(scores, key=scores.get)
            default_idx = list(df_excel.columns).index(melhor) if scores[melhor] > 0 else 0
            coluna_nif = col_sel.selectbox(
                "Coluna com NIFs",
                options=list(df_excel.columns),
                index=default_idx,
            )
            col_sel.caption(f"{len(df_excel)} linhas carregadas · coluna detectada: **{melhor}**")
        except Exception as exc:
            st.error(f"Erro ao ler Excel: {exc}")

    pesquisar_excel = col_btn2.button(
        "🔍 Pesquisar Excel", disabled=(df_excel is None), use_container_width=True
    )

with tab_manual:
    with st.form("form_manual", clear_on_submit=True):
        nif_input = st.text_area(
            "NIFs (um por linha)",
            placeholder="231272839\n123456789\n987654321",
            height=160,
            help="Insira um NIF por linha.",
        )
        pesquisar_manual = st.form_submit_button("🔍 Pesquisar", use_container_width=True)


def _extrair_nifs_excel(df: pd.DataFrame, coluna: str) -> tuple[list[str], list[str]]:
    vals = df[coluna].dropna().astype(str).str.strip().str.replace(r"\s", "", regex=True)
    validos   = [v for v in vals if re.fullmatch(r"\d{9}", v)]
    invalidos = [v for v in vals if v and not re.fullmatch(r"\d{9}", v)]
    return validos, invalidos


def _pesquisar_lista(nifs: list[str]) -> None:
    if not sigo["ok"]:
        st.error(f"SIGO indisponível: {sigo['msg']}")
        return
    vistos: set[str] = set()
    nifs_unicos = [n for n in nifs if not (n in vistos or vistos.add(n))]
    progresso = st.progress(0, text=f"A pesquisar 0 / {len(nifs_unicos)}…")
    erros: list[str] = []
    for i, nif in enumerate(nifs_unicos):
        progresso.progress((i + 1) / len(nifs_unicos),
                           text=f"A pesquisar {i + 1} / {len(nifs_unicos)} — NIF {nif}")
        try:
            resultados = _pesquisar_nif(nif)
        except Exception as exc:
            erros.append(f"{nif}: {exc}")
            continue
        if resultados:
            for f in resultados:
                st.session_state["historico"].append({
                    "nif_pesq": nif, "encontrado": True,
                    "nome": f.nome, "n_sigo": f.n_sigo,
                })
        else:
            st.session_state["historico"].append({
                "nif_pesq": nif, "encontrado": False, "nome": "", "n_sigo": "",
            })
    progresso.empty()
    if erros:
        st.warning("Erros durante a pesquisa:\n" + "\n".join(erros))
    st.rerun()


if pesquisar_excel and df_excel is not None and coluna_nif:
    validos, invalidos = _extrair_nifs_excel(df_excel, coluna_nif)
    if invalidos:
        st.warning(f"Ignorados {len(invalidos)} valores sem 9 dígitos: {', '.join(invalidos[:10])}" +
                   (" …" if len(invalidos) > 10 else ""))
    if not validos:
        st.error("Nenhum NIF válido encontrado na coluna seleccionada.")
    else:
        _pesquisar_lista(validos)

if pesquisar_manual:
    linhas = [l.strip().replace(" ", "") for l in nif_input.splitlines() if l.strip()]
    invalidos = [n for n in linhas if not re.fullmatch(r"\d{9}", n)]
    if not linhas:
        st.error("Insira pelo menos um NIF.")
    elif invalidos:
        st.error(f"NIFs inválidos: {', '.join(invalidos)}")
    else:
        _pesquisar_lista(linhas)

# ── Tabela de resultados ──────────────────────────────────────────────────────
if historico:
    st.markdown("""
        <div style="display:flex; align-items:center; gap:.7rem; margin-bottom:1rem;">
            <div style="font-size:1.1rem; font-weight:700; color:#0f172a;">Resultados</div>
        </div>
    """, unsafe_allow_html=True)

    # Construir HTML da tabela
    linhas_html = ""
    for h in historico:
        badge = ('<span class="badge-ok">Registado</span>' if h["encontrado"]
                 else '<span class="badge-err">Não encontrado</span>')
        linhas_html += f"""
        <tr>
            <td style="font-family:monospace; font-size:.88rem; color:#334155;">{h['nif_pesq']}</td>
            <td>{badge}</td>
            <td style="font-weight:500; color:#0f172a;">{h['nome'] or '—'}</td>
            <td style="font-family:monospace; font-size:.88rem; color:#2563eb; font-weight:600;">{h['n_sigo'] or '—'}</td>
        </tr>"""

    st.markdown(f"""
    <div style="background:#fff; border-radius:16px; border:1px solid #e2e8f0;
                box-shadow:0 1px 4px rgba(0,0,0,0.06); overflow:hidden; margin-bottom:1.2rem;">
        <table style="width:100%; border-collapse:collapse; font-size:.9rem;">
            <thead>
                <tr style="background:#f8fafc; border-bottom:1.5px solid #e2e8f0;">
                    <th style="padding:.85rem 1.2rem; text-align:left; color:#64748b; font-size:.75rem;
                               text-transform:uppercase; letter-spacing:.06em; font-weight:600;">NIF</th>
                    <th style="padding:.85rem 1.2rem; text-align:left; color:#64748b; font-size:.75rem;
                               text-transform:uppercase; letter-spacing:.06em; font-weight:600;">Estado</th>
                    <th style="padding:.85rem 1.2rem; text-align:left; color:#64748b; font-size:.75rem;
                               text-transform:uppercase; letter-spacing:.06em; font-weight:600;">Nome</th>
                    <th style="padding:.85rem 1.2rem; text-align:left; color:#64748b; font-size:.75rem;
                               text-transform:uppercase; letter-spacing:.06em; font-weight:600;">Nº SIGO</th>
                </tr>
            </thead>
            <tbody>
                {''.join(f'<tr style="border-bottom:1px solid #f1f5f9;">{r}</tr>' for r in linhas_html.split('<tr>')[1:])}
            </tbody>
        </table>
    </div>
    """, unsafe_allow_html=True)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["NIF", "Estado", "Nome", "Nº SIGO"])
    for h in historico:
        writer.writerow([
            h["nif_pesq"],
            "Registado" if h["encontrado"] else "Não encontrado",
            h["nome"], h["n_sigo"],
        ])

    st.download_button(
        label="⬇️ Exportar CSV",
        data="﻿" + buf.getvalue(),
        file_name="sigo_formandos.csv",
        mime="text/csv",
    )
