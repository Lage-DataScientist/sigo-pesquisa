"""Autenticação na plataforma SIGO."""

from playwright.async_api import Page

from sigo.config import LOGIN_URL, SELECTORS, CREDENTIALS

# URL que indica sessão activa
_HOME_URL = "https://www.sigo.pt/Inicio.jsp"


async def is_logged_in(page: Page) -> bool:
    """Verifica se já existe uma sessão activa."""
    return _HOME_URL in page.url


async def login(page: Page, username: str | None = None, password: str | None = None) -> bool:
    """
    Navega para a página de login e autentica o utilizador.
    Se já estiver autenticado, não faz nada e devolve True.
    """
    if await is_logged_in(page):
        return True

    user = username or CREDENTIALS["username"]
    pwd  = password or CREDENTIALS["password"]

    await page.goto(LOGIN_URL)
    await page.wait_for_load_state("networkidle")

    # Preenche utilizador e senha
    await page.fill(SELECTORS["username"], user)
    await page.fill(SELECTORS["password"], pwd)

    # Clica no botão submit (testado e confirmado)
    await page.click(SELECTORS["submit_button"])
    await page.wait_for_url("**/Inicio.jsp", timeout=15_000)

    return await is_logged_in(page)


async def logout(page: Page) -> None:
    """Termina a sessão navegando para o logout."""
    await page.goto(LOGIN_URL)
    await page.wait_for_load_state("networkidle")
