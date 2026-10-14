"""Calcula a versao desta compilacao e se ela deve ser publicada (usado pelo GitHub Actions).

Regras (controle de versao):
- VERSION guarda MAIOR.MENOR.CORRECAO "base". Para lancar 1.1.0 ou 2.0.0, mude o VERSION (packaging/nova_versao.py)
  e escreva a secao no CHANGELOG.md; a proxima compilacao da main publica exatamente essa versao.
- Sem mudar o VERSION, cada push na main que mexe no programa publica a CORRECAO seguinte a ultima release
  (1.0.0 -> 1.0.1 -> 1.0.2...). Mudancas so em documentacao, testes ou no workflow nao geram versao.
- Pull requests compilam com o numero que a versao teria, mas nao publicam.

Uso: python packaging/calcular_versao.py [--publicavel]   (imprime versao=, anterior=, publicar=)"""
import os
import re
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from app.versao import tupla  # noqa: E402

# o que, se mudar, chega nos PCs (o resto nao muda o programa instalado)
CAMINHOS_DO_PROGRAMA = ["app", "run.py", "requirements.txt", "packaging/descarregador.spec", "packaging/windows",
                        "packaging/linux", "packaging/macos", "packaging/versao_windows.py", "VERSION",
                        "housinho.png", "housinho.ico"]


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()


def ultima_release():
    tags = [t.lstrip("v") for t in git("tag", "-l", "v*").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)]
    return max(tags, key=tupla) if tags else None


def proxima(base, anterior):
    if not anterior or tupla(base) > tupla(anterior):
        return base
    a = tupla(anterior)
    return f"{a[0]}.{a[1]}.{a[2] + 1}"


def mudou_o_programa(anterior):
    if not anterior:
        return True
    return bool(git("diff", "--name-only", f"v{anterior}", "HEAD", "--", *CAMINHOS_DO_PROGRAMA))


def main():
    base = open(os.path.join(RAIZ, "VERSION"), encoding="utf-8").read().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", base):
        sys.exit(f"::error::VERSION '{base}' não é MAIOR.MENOR.CORREÇÃO")
    anterior = ultima_release()
    if anterior and tupla(base) < tupla(anterior.rsplit(".", 1)[0] + ".0"):
        sys.exit(f"::error::VERSION ({base}) é menor que a última release (v{anterior})")
    versao = proxima(base, anterior)
    if versao == base and f"## [{base}]" not in open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read():
        sys.exit(f"::error::CHANGELOG.md sem a seção '## [{base}]' (versão escolhida no VERSION)")
    publicar = "--publicavel" in sys.argv and mudou_o_programa(anterior)
    print(f"versao={versao}\nanterior={anterior or ''}\npublicar={'true' if publicar else 'false'}")


if __name__ == "__main__":
    main()
