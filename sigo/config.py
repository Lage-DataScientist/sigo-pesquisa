"""Configurações centrais do programa SIGO."""

import os

BASE_URL = "https://www.sigo.pt"
LOGIN_URL = f"{BASE_URL}/Login.jsp"

# Credenciais lidas de variáveis de ambiente ou Streamlit secrets
def _get_credentials():
    try:
        import streamlit as st
        return {
            "username": st.secrets.get("SIGO_USER", os.getenv("SIGO_USER", "")),
            "password": st.secrets.get("SIGO_PASS", os.getenv("SIGO_PASS", "")),
        }
    except Exception:
        return {
            "username": os.getenv("SIGO_USER", ""),
            "password": os.getenv("SIGO_PASS", ""),
        }

CREDENTIALS = _get_credentials()

# Seletores da página de login (IDs com ':' precisam de escape em CSS)
SELECTORS = {
    "username":       "#form1\\:tfUtilizador",
    "password":       "#form1\\:pfSenha",
    "submit_button":  "#form1\\:btLogin",
    "enter_link":     "#form1\\:ihEntrar",
}

BROWSER_OPTIONS = {
    "headless": False,   # True para execução sem janela
    "slow_mo": 50,       # ms entre acções (útil para depuração)
    "timeout": 30_000,   # timeout global em ms
}
