"""Muda a versao MAIOR ou MENOR. Uso:

    python packaging/nova_versao.py 1.1.0

As correcoes (1.0.1, 1.0.2...) sao automaticas: cada push na main que muda o programa publica a seguinte. Este
script e para quando voce quer marcar um passo maior (recurso novo = MENOR; mudanca que obriga todos os PCs a
atualizarem juntos = MAIOR). Confere: formato X.Y.0, maior que a ultima versao publicada, arvore do git limpa, main
sem estar atras do GitHub e secao "## [1.1.0]" no CHANGELOG.md. Grava o VERSION e faz o commit; depois e so
`git push` (o recurso novo e a versao juntos): o GitHub Actions compila, publica e os PCs se atualizam."""
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
    if not SEMVER.match(nova) or not nova.endswith(".0"):
        parar(f"'{nova}' precisa ser MAIOR.MENOR.0 (ex.: 1.2.0). As correções são numeradas sozinhas.")
    git("fetch", "origin", "main", "--tags")
    tags = [t.lstrip("v") for t in git("tag", "-l", "v*").stdout.split() if SEMVER.match(t.lstrip("v"))]
    publicada = max(tags, key=tupla) if tags else atual
    if tupla(nova) <= tupla(max(atual, publicada, key=tupla)):
        parar(f"a nova versão ({nova}) precisa ser maior que a atual (v{max(atual, publicada, key=tupla)}).")
    if git("status", "--porcelain").stdout.strip():
        parar("há alterações sem commit. Faça o commit (ou descarte) antes de lançar a versão.")
    if git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        parar("lance versões a partir da branch main.")
    # pode ter commits ainda nao enviados (o recurso novo vai junto com a versao); so nao pode estar atras do GitHub
    if git("merge-base", "--is-ancestor", "origin/main", "HEAD").returncode != 0:
        parar("a main do GitHub tem commits que você não tem. Faça git pull antes.")
    changelog = open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read()
    if f"## [{nova}]" not in changelog:
        parar(f"escreva no CHANGELOG.md a seção '## [{nova}] - AAAA-MM-DD' com o que mudou, faça o commit "
              "e rode de novo.")

    with open(os.path.join(RAIZ, "VERSION"), "w", encoding="utf-8") as f:
        f.write(nova + "\n")
    for cmd in (("add", "VERSION"), ("commit", "-m", f"release: v{nova}")):
        r = git(*cmd)
        if r.returncode != 0:
            parar(f"git {' '.join(cmd)}: {r.stderr.strip()}")
    print(f"Versão {atual} -> {nova} pronta (commit feito).")
    print("Para publicar: git push   (o GitHub Actions compila, publica e os PCs se atualizam sozinhos)")


if __name__ == "__main__":
    main()
