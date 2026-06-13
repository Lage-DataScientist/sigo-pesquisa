"""Navegação dentro do portal SIGO após autenticação."""

from playwright.async_api import Page

# Menus descobertos na página Inicio.jsp
MENU = {
    "contactos":             "Contactos",
    "formadoras":            "Formadoras",
    "promotoras":            "Promotoras/Certificadoras",
    "parcerias":             "Parcerias",
    "modulos":               "Módulos",
    "cursos":                "Cursos",
    "pesquisar":             "Pesquisar",
    "equipa":                "Equipa",
    "acoes_formacao":        "Ações de Formação",
    "formandos_inscricoes":  "Formandos e Inscrições",
    "gestao_inscricoes":     "Gestão de Inscricões",
    "pedidos":               "Pedidos",
    "alertas":               "Alertas",
    "utilizadores":          "Utilizadores",
}


async def goto_menu(page: Page, menu_key: str) -> None:
    """Clica no item de menu correspondente à chave fornecida."""
    label = MENU.get(menu_key)
    if not label:
        raise ValueError(f"Menu desconhecido: '{menu_key}'. Opções: {list(MENU.keys())}")
    await page.get_by_role("link", name=label).first.click()
    await page.wait_for_load_state("networkidle")


async def get_alerts_count(page: Page) -> int:
    """Lê o número de alertas do link 'Alertas (N)'."""
    locator = page.get_by_role("link", name=lambda n: n.startswith("Alertas"))
    text = await locator.inner_text()
    # Formato: "Alertas (4)"
    if "(" in text and ")" in text:
        return int(text.split("(")[1].split(")")[0])
    return 0
