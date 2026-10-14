"""Baixa o lightcraft-cli (conversor de RAW para JPEG) do sistema atual para vendor/lightcraft/.

O PyInstaller leva essa pasta junto do programa; rodando pelo codigo-fonte, app/raw.py tambem a encontra.
Uso (na raiz do projeto): python packaging/baixar_lightcraft.py
LightCraft: https://github.com/storytold/lightcraft (MIT ou Apache-2.0; licencas copiadas junto)."""
import hashlib
import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

VERSAO = "0.8.0"
URL = f"https://github.com/storytold/lightcraft/releases/download/v{VERSAO}/"
# (arquivo da release, sha256 do SHA256SUMS.txt da release, caminho do executavel dentro do pacote)
PACOTES = {
    "linux": (f"lightcraft-{VERSAO}-linux-x86_64.tar.gz",
              "9fe0ecc69b7f1f3a35a1c630429b3c52fdb4419ba208b5579b4501b938f518d1",
              f"lightcraft-{VERSAO}-linux-x86_64/bin/lightcraft-cli"),
    "windows": (f"lightcraft-{VERSAO}-windows-x64-portable.zip",
                "57f3e65fccd33abf2f37d67532662ca55235287f5b41e5bb9bc057da4485caa9",
                f"lightcraft-{VERSAO}-windows-x64-portable/lightcraft-cli.exe"),
    "macos": (f"lightcraft-cli-{VERSAO}-macos-universal.zip",
              "e6734be20cb0cfc714d872b37a33c9c945c5a09f22f4c441c09facef8fcbbce0",
              f"lightcraft-cli-{VERSAO}-macos-universal/lightcraft-cli"),
}
LICENCAS = ("LICENSE-MIT", "LICENSE-APACHE", "NOTICE")
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DESTINO = os.path.join(RAIZ, "vendor", "lightcraft")


def _sistema():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _ler_membros(dados, nome_pacote, caminhos):
    """{caminho: bytes} de cada caminho pedido que existir no .zip/.tar.gz."""
    saida = {}
    if nome_pacote.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            for c in caminhos:
                if c in z.namelist():
                    saida[c] = z.read(c)
    else:
        with tarfile.open(fileobj=io.BytesIO(dados), mode="r:gz") as t:
            for c in caminhos:
                try:
                    saida[c] = t.extractfile(c).read()
                except (KeyError, AttributeError):
                    pass
    return saida


def main():
    sistema = _sistema()
    pacote, sha, exe = PACOTES[sistema]
    print(f"Baixando {pacote}...")
    with urllib.request.urlopen(URL + pacote, timeout=600) as r:
        dados = r.read()
    if hashlib.sha256(dados).hexdigest() != sha:
        sys.exit(f"SHA-256 de {pacote} nao confere: arquivo corrompido ou alterado")

    pasta = os.path.dirname(exe)
    if sistema == "linux":                 # no .tar.gz do Linux as licencas ficam em share/doc
        pasta = f"lightcraft-{VERSAO}-linux-x86_64/share/doc/lightcraft"
    membros = _ler_membros(dados, pacote, [exe] + [f"{pasta}/{n}" for n in LICENCAS])
    if exe not in membros:
        sys.exit(f"{exe} nao esta em {pacote}")

    shutil.rmtree(DESTINO, ignore_errors=True)
    os.makedirs(DESTINO)
    alvo = os.path.join(DESTINO, os.path.basename(exe))
    with open(alvo, "wb") as f:
        f.write(membros[exe])
    os.chmod(alvo, 0o755)
    for n in LICENCAS:
        conteudo = membros.get(f"{pasta}/{n}")
        if conteudo is None:
            sys.exit(f"{n} nao esta em {pacote}")
        with open(os.path.join(DESTINO, n), "wb") as f:
            f.write(conteudo)

    # Mac: o pacote e universal (Intel + Apple Silicon); fica so a parte deste Mac (metade do tamanho)
    if sistema == "macos":
        arq = "arm64" if platform.machine() == "arm64" else "x86_64"
        subprocess.run(["lipo", alvo, "-thin", arq, "-output", alvo + ".fino"], check=True)
        os.replace(alvo + ".fino", alvo)
        os.chmod(alvo, 0o755)

    saida = subprocess.run([alvo, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    print(f"OK: {saida} em {alvo}")


if __name__ == "__main__":
    main()
