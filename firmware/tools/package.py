#!/usr/bin/env python3
"""Empacota os arquivos de firmware do relógio num .zip único e
versionado, pronto para guardar como backup ou instalar com install.py.

Roda no computador (não no ESP32). Uso:

    python3 tools/package.py

Gera firmware/dist/relogio-esp32-firmware-<data>.zip, com um MANIFEST.txt
dentro listando a versão de cada arquivo (a constante VERSION de cada
módulo — ver SPECS.md seção 8) e o commit do git, se disponível. Serve
pra saber depois, com certeza, o que exatamente foi gravado num pacote.
"""

import datetime
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from release_files import RELEASE_FILES

FIRMWARE_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = FIRMWARE_DIR / "dist"

_VERSION_RE = re.compile(r'^VERSION\s*=\s*["\'](.+?)["\']', re.MULTILINE)


def _read_version(path):
    text = path.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    return match.group(1) if match else "(sem VERSION)"


def _git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=FIRMWARE_DIR, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "desconhecido"
    except Exception:
        return "desconhecido"


def build_package():
    missing = [f for f in RELEASE_FILES if not (FIRMWARE_DIR / f).exists()]
    if missing:
        print("ERRO: arquivos faltando em firmware/:", ", ".join(missing))
        sys.exit(1)

    DIST_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = DIST_DIR / f"relogio-esp32-firmware-{stamp}.zip"

    manifest_lines = [
        "Relogio_Esp32_Ble - pacote de firmware",
        "",
        f"Gerado em: {stamp}",
        f"Commit git: {_git_commit()}",
        "",
        "Arquivos e versoes:",
    ]
    for name in RELEASE_FILES:
        manifest_lines.append(f"  {name}: {_read_version(FIRMWARE_DIR / name)}")
    manifest_lines += [
        "",
        "Para instalar no ESP32: python3 tools/install.py (ver firmware/README.md)",
    ]
    manifest_text = "\n".join(manifest_lines) + "\n"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in RELEASE_FILES:
            zf.write(FIRMWARE_DIR / name, arcname=name)
        zf.writestr("MANIFEST.txt", manifest_text)

    print("Pacote gerado:", zip_path)
    print()
    print(manifest_text)
    return zip_path


if __name__ == "__main__":
    build_package()
