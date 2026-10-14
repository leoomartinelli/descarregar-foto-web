"""Conversao de RAW para JPEG com o motor do LightCraft (lightcraft-cli, MIT/Apache-2.0).

So mexe nas copias ja gravadas no PC: o arquivo do cartao nunca e lido aqui nem apagado."""
import os
import shutil
import subprocess

from PIL import Image

from . import core
from .versao import RECURSOS

NOME_CLI = "lightcraft-cli.exe" if os.name == "nt" else "lightcraft-cli"
QUALIDADE = 92          # mesma qualidade padrao da exportacao do LightCraft
TEMPO_MAXIMO = 300      # segundos por foto (uma foto de 60 MP leva ~10 s)


def localizar_cli():
    """Caminho do lightcraft-cli: variavel LIGHTCRAFT_CLI, o que vai junto do programa ou o do sistema."""
    candidatos = [os.environ.get("LIGHTCRAFT_CLI"),
                  os.path.join(RECURSOS, "lightcraft", NOME_CLI),
                  os.path.join(RECURSOS, "vendor", "lightcraft", NOME_CLI),
                  shutil.which("lightcraft-cli")]
    for c in candidatos:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def disponivel():
    return localizar_cli() is not None


def _jpeg_valido(caminho):
    try:
        if os.path.getsize(caminho) == 0:
            return False
        with Image.open(caminho) as img:
            img.verify()
        return True
    except Exception:
        return False


def converter(raw, destino):
    """Converte a copia `raw` (dentro de `destino`) em JPEG na resolucao total e apaga o RAW.

    Retorna o caminho do JPEG. Se algo falhar, o RAW fica onde esta e a excecao sobe."""
    raw, destino = os.path.abspath(raw), os.path.abspath(destino)
    if os.path.commonpath([raw, destino]) != destino:
        raise ValueError(f"{raw} esta fora da pasta de destino")
    if core.E.drive_path and os.path.commonpath([raw, os.path.abspath(core.E.drive_path)]) == \
            os.path.abspath(core.E.drive_path):
        raise ValueError(f"{raw} esta no cartao: nao converto nem apago nada la")
    cli = localizar_cli()
    if not cli:
        raise RuntimeError("Conversor de RAW (lightcraft-cli) nao encontrado.")

    base = os.path.splitext(raw)[0]
    jpg = base + ".jpg"
    c = 1
    while os.path.exists(jpg):
        jpg = f"{base}_{c}.jpg"
        c += 1
    parcial = jpg[:-4] + ".convertendo.jpg"   # so vira o nome final depois de conferido
    try:
        r = subprocess.run([cli, "render", raw, "-o", parcial, "--quality", str(QUALIDADE)],
                           capture_output=True, text=True, timeout=TEMPO_MAXIMO, **core.SEM_JANELA)
        if r.returncode != 0 or not _jpeg_valido(parcial):
            raise RuntimeError((r.stderr or r.stdout or "").strip()[-400:] or f"codigo {r.returncode}")
        st = os.stat(raw)
        os.utime(parcial, (st.st_atime, st.st_mtime))   # a numeracao e o revisor ordenam pela data
        os.replace(parcial, jpg)
    except BaseException:
        try:
            os.remove(parcial)
        except OSError:
            pass
        raise
    os.remove(raw)
    return jpg


def converter_todos(raws, destino, ao_avancar=None):
    """Converte um por vez (cada conversao usa ~1,3 GB de RAM e todos os nucleos).

    Retorna ({raw: jpg} dos convertidos, [raws que falharam])."""
    feitos, falhas = {}, []
    for i, raw in enumerate(raws):
        try:
            feitos[raw] = converter(raw, destino)
        except Exception as e:
            print(f"Erro ao converter {os.path.basename(raw)}: {e}")
            falhas.append(raw)
        if ao_avancar:
            ao_avancar(i + 1, len(raws))
    return feitos, falhas
