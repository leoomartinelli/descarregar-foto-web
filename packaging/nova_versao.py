"""Lanca uma nova versao com as regras do projeto. Uso:

    python packaging/nova_versao.py 1.2.0

Confere: numero no formato X.Y.Z e MAIOR que o atual; arvore do git limpa; branch main atualizada com o GitHub;
secao "## [1.2.0]" escrita no CHANGELOG.md. Depois grava o VERSION, faz o commit "release: v1.2.0" e cria a tag.
Falta so publicar: git push origin main v1.2.0  (o GitHub Actions compila e cria a release)."""
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from app.versao import tupla  # noqa: E402

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)


def parar(msg):
    print(f"ERRO: {msg}")
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        parar("informe a versão. Ex.: python packaging/nova_versao.py 1.2.0")
    nova = sys.argv[1].lstrip("vV")
    atual = open(os.path.join(RAIZ, "VERSION"), encoding="utf-8").read().strip()
    if not SEMVER.match(nova):
        parar(f"'{nova}' não está no formato MAIOR.MENOR.CORREÇÃO (ex.: 1.2.0).")
    if tupla(nova) <= tupla(atual):
        parar(f"a nova versão ({nova}) precisa ser maior que a atual ({atual}).")
    if git("status", "--porcelain").stdout.strip():
        parar("há alterações sem commit. Faça o commit (ou descarte) antes de lançar a versão.")
    if git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        parar("lance versões a partir da branch main.")
    git("fetch", "origin", "main", "--tags")
    if git("rev-parse", "HEAD").stdout != git("rev-parse", "origin/main").stdout:
        parar("a main local está diferente da do GitHub. Faça git pull / git push antes.")
    if git("rev-parse", "-q", "--verify", f"refs/tags/v{nova}").returncode == 0:
        parar(f"a tag v{nova} já existe.")
    changelog = open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read()
    if f"## [{nova}]" not in changelog:
        parar(f"escreva no CHANGELOG.md a seção '## [{nova}] - AAAA-MM-DD' com o que mudou, faça o commit "
              "e rode de novo.")

    with open(os.path.join(RAIZ, "VERSION"), "w", encoding="utf-8") as f:
        f.write(nova + "\n")
    for cmd in (("add", "VERSION"), ("commit", "-m", f"release: v{nova}"), ("tag", "-a", f"v{nova}", "-m", f"v{nova}")):
        r = git(*cmd)
        if r.returncode != 0:
            parar(f"git {' '.join(cmd)}: {r.stderr.strip()}")
    print(f"Versão {atual} -> {nova} pronta (commit + tag v{nova}).")
    print(f"Para publicar: git push origin main v{nova}")


if __name__ == "__main__":
    main()
