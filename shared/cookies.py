"""Export cookies del browser profile a formato Netscape para yt-dlp."""

from pathlib import Path
from playwright.sync_api import sync_playwright


def export_cookies(config: dict, domain: str = "https://www.instagram.com") -> Path:
    """Exporta cookies del perfil persistente a archivo Netscape.

    Returns:
        Path al archivo de cookies generado.
    """
    profile_dir = config["browser"]["profile_dir"]
    cookies_file = Path(config["downloads"]["cookies_file"])

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(profile_dir, headless=True)
        cookies = ctx.cookies([domain])
        ctx.close()

    if not cookies:
        print(f"No se encontraron cookies para {domain}")
        return cookies_file

    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        dom = c.get("domain", "")
        flag = "TRUE" if dom.startswith(".") else "FALSE"
        path = c.get("path", "/")
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = int(c.get("expires", -1))
        name = c.get("name", "")
        value = c.get("value", "")
        lines.append(f"{dom}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}")

    cookies_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cookies_file, "w") as f:
        f.write("\n".join(lines))

    print(f"Exportadas {len(cookies)} cookies -> {cookies_file}")
    return cookies_file
