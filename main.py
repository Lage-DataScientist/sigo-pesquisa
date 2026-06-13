"""Ponto de entrada principal da integração SIGO."""

import asyncio

from sigo.modules.browser import browser_session
from sigo.modules.auth import login, is_logged_in
from sigo.modules.session import save_session, load_session
from sigo.modules.navigation import get_alerts_count


async def run():
    async with browser_session() as (browser, context, page):

        # Tenta restaurar sessão guardada
        restored = await load_session(context)

        if restored:
            await page.goto("https://www.sigo.pt/Inicio.jsp")
            await page.wait_for_load_state("networkidle")

        if not await is_logged_in(page):
            print("[login] A autenticar...")
            success = await login(page)
            if not success:
                print("[login] Falha na autenticação. Verifique as credenciais.")
                return
            print("[login] Autenticação bem-sucedida.")
            await save_session(context)
        else:
            print("[sessão] Sessão restaurada com sucesso.")

        print(f"[portal] URL: {page.url}")

        alertas = await get_alerts_count(page)
        print(f"[portal] Alertas pendentes: {alertas}")

        # --- Adicione aqui navegação/extracção ---
        # Exemplo: await goto_menu(page, "acoes_formacao")

        input("\nPrima Enter para fechar o browser...")


if __name__ == "__main__":
    asyncio.run(run())
