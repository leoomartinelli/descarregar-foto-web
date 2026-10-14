"""Versao do programa (fonte unica: arquivo VERSION na raiz) e caminhos de quando roda empacotado."""
import os
import sys

REPO = "leoomartinelli/descarregar-foto-web"
URL_RELEASES = f"https://github.com/{REPO}/releases"

# Empacotado pelo PyInstaller: os arquivos do programa ficam em sys._MEIPASS (somente leitura) e os dados do
# usuario numa pasta propria em casa, igual em Windows, macOS e Linux.
EMPACOTADO = bool(getattr(sys, "frozen", False))
RECURSOS = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTA_USUARIO = os.path.join(os.path.expanduser("~"), "Descarregador de Fotos")


def _ler_versao():
    try:
        with open(os.path.join(RECURSOS, "VERSION"), encoding="utf-8") as f:
            return f.read().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


VERSAO = _ler_versao()


def tupla(v):
    """'v1.2.3' -> (1, 2, 3); partes nao numericas viram 0 (para comparar versoes)."""
    partes = []
    for p in (v or "").strip().lstrip("vV").split("-")[0].split(".")[:3]:
        partes.append(int(p) if p.isdigit() else 0)
    return tuple(partes + [0] * (3 - len(partes)))
