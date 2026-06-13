"""Gestão da sessão autenticada — guardar e restaurar cookies."""

import json
from pathlib import Path
from playwright.async_api import BrowserContext

SESSION_FILE = Path("sigo_session.json")


async def save_session(context: BrowserContext) -> None:
    """Guarda os cookies da sessão actual em disco."""
    storage = await context.storage_state()
    SESSION_FILE.write_text(json.dumps(storage, indent=2), encoding="utf-8")


async def load_session(context: BrowserContext) -> bool:
    """Restaura cookies de uma sessão guardada. Devolve True se existir ficheiro."""
    if not SESSION_FILE.exists():
        return False
    state = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    await context.add_cookies(state.get("cookies", []))
    return True


def clear_session() -> None:
    """Remove o ficheiro de sessão guardado."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
