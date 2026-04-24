"""Playwright persistent browser context manager con login check."""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright, BrowserContext as PWContext, Page


class BrowserContext:
    """Context manager que lanza un Chromium persistente con sesión de Instagram."""

    def __init__(self, config: dict):
        self.config = config
        self._pw = None
        self._ctx = None

    def __enter__(self) -> tuple[PWContext, Page]:
        bcfg = self.config["browser"]
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            bcfg["profile_dir"],
            headless=bcfg.get("headless", False),
            args=["--disable-blink-features=AutomationControlled"],
            user_agent=bcfg["user_agent"],
            locale=bcfg.get("locale", "es-MX"),
            viewport=bcfg["viewport"],
        )
        page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self._ctx, page

    def __exit__(self, *exc):
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()


def ensure_logged_in(page: Page, platform_url: str = "https://www.instagram.com/"):
    """Verifica sesión activa. Si no hay, pide login manual al usuario."""
    page.goto(platform_url, wait_until="domcontentloaded")
    time.sleep(3)

    if "login" in page.url or page.locator('input[name="username"]').count() > 0:
        print("\n*** No hay sesion activa de Instagram ***")
        print("Logueate en el navegador que se acaba de abrir.")
        input(">>> Presiona ENTER cuando hayas iniciado sesion: ")
        page.goto(platform_url, wait_until="domcontentloaded")
        time.sleep(2)

        if "login" in page.url:
            raise RuntimeError("No se pudo verificar la sesion de Instagram")

    print("Sesion activa verificada.\n")


def is_login_redirect(page: Page) -> bool:
    """Chequea si la pagina actual redireccionó a login."""
    return "login" in page.url
