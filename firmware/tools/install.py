#!/usr/bin/env python3
"""Copia todos os arquivos do relógio para o ESP32 via USB, com um
comando só — sem precisar arrastar arquivo por arquivo no Thonny.

Roda no computador (não no ESP32). Requisito único: `pip install
mpremote` (funciona em Windows, Mac e Linux).

Uso:
    python3 tools/install.py                 # tenta achar a porta sozinho
    python3 tools/install.py COM5             # Windows, porta especifica
    python3 tools/install.py /dev/ttyUSB0     # Linux
    python3 tools/install.py --list           # so lista as portas disponiveis

Feche o Thonny (ou qualquer outro programa com a porta serial aberta)
antes de rodar — só um programa por vez consegue falar com o ESP32.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from release_files import RELEASE_FILES

FIRMWARE_DIR = Path(__file__).resolve().parent.parent


def _mpremote_available():
    try:
        subprocess.run(
            [sys.executable, "-m", "mpremote", "version"],
            capture_output=True, timeout=10,
        )
        return True
    except Exception:
        return False


def list_ports():
    subprocess.run([sys.executable, "-m", "mpremote", "connect", "list"])


def install(port):
    missing = [f for f in RELEASE_FILES if not (FIRMWARE_DIR / f).exists()]
    if missing:
        print("ERRO: arquivos faltando em firmware/:", ", ".join(missing))
        sys.exit(1)

    # Uma unica conexao mpremote, encadeando "fs cp" pra cada arquivo com "+"
    # (sintaxe de encadeamento de comandos do mpremote) e terminando com um
    # soft-reset, pra o relogio comecar a rodar sozinho assim que a copia
    # acabar - sem precisar apertar o botao RESET manualmente.
    cmd = [sys.executable, "-m", "mpremote", "connect", port]
    for name in RELEASE_FILES:
        cmd += ["fs", "cp", str(FIRMWARE_DIR / name), f":{name}", "+"]
    cmd += ["soft-reset"]

    print(f"Copiando {len(RELEASE_FILES)} arquivos para o ESP32 ({port})...")
    for name in RELEASE_FILES:
        print("  -", name)

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print()
        print("Nao deu certo. Confira:")
        print("  - o ESP32 esta ligado e conectado por USB?")
        print("  - a porta esta certa? (rode com --list pra ver as opcoes)")
        print("  - o Thonny (ou outro programa) nao esta com a porta aberta?")
        sys.exit(result.returncode)

    print()
    print("Pronto! O relogio reiniciou e ja deve estar rodando sozinho.")


def main():
    args = sys.argv[1:]
    if not _mpremote_available():
        print("mpremote nao encontrado. Instale com:")
        print("  pip install mpremote")
        sys.exit(1)

    if "--list" in args or "-l" in args:
        list_ports()
        return

    port = next((a for a in args if not a.startswith("-")), "auto")
    install(port)


if __name__ == "__main__":
    main()
