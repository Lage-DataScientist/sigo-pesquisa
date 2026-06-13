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
    app_pw = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", ""))
    if not app_pw:
        return True
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
        await context.set_default_timeout(60_000)
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
    st.markdown("## 🎓 SIGO")
    st.markdown("**Pesquisa de Formandos**")
    st.divider()

    sigo = _init_sigo(*_get_credentials())
    if sigo["ok"]:
        st.markdown(f'<p class="status-ok">● {sigo["msg"]}</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="status-err">● {sigo["msg"]}</p>', unsafe_allow_html=True)
        if st.button("🔄 Re-ligar"):
            _re_login()

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
        data="﻿" + buf.getvalue(),
        file_name="sigo_formandos.csv",
        mime="text/csv",
    )
