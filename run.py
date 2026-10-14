"""Inicia o servidor e abre o navegador. Uso: python run.py (ou o executavel gerado pelo PyInstaller).

No executavel nao ha terminal: a saida vai para ~/Descarregador de Fotos/descarregador.log. Clicar no icone com o
programa ja aberto apenas abre o navegador de novo (nao sobe um segundo servidor)."""
import json
import multiprocessing
import os
import sys
import threading
import time
import urllib.request
import webbrowser

from app.versao import EMPACOTADO, PASTA_USUARIO, RECURSOS, VERSAO

BASE = PASTA_USUARIO if EMPACOTADO else os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 50007))


def carregar_env():
    """.env simples (KEY=VALUE) sem sobrescrever variaveis existentes."""
    env = os.path.join(BASE, ".env")
    if os.path.exists(env):
        for linha in open(env, encoding="utf-8"):
            if "=" in linha and not linha.strip().startswith("#"):
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def log_em_arquivo():
    os.makedirs(BASE, exist_ok=True)
    caminho = os.path.join(BASE, "descarregador.log")
    try:
        if os.path.getsize(caminho) > 5 * 1024 * 1024:   # nao deixa o log crescer para sempre
            os.replace(caminho, caminho + ".1")
    except OSError:
        pass
    f = open(caminho, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = f
    print(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} · Descarregador de Fotos v{VERSAO} =====")


def ja_aberto(porta):
    """True se este programa ja esta rodando nesta maquina (na porta informada)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/versao", timeout=1.5) as r:
            return json.load(r).get("app") == "descarregador-fotos"
    except Exception:
        return False


def abrir_navegador_quando_pronto(porta):
    for _ in range(60):
        if ja_aberto(porta):
            break
        time.sleep(0.5)
    webbrowser.open(f"http://localhost:{porta}")


def autoteste():
    """Confere se tudo que foi empacotado carrega neste sistema (usado no GitHub Actions). Codigo de saida 0 = ok."""
    import io
    import traceback
    resultados = []

    def checar(nome, fn):
        try:
            resultados.append((nome, True, fn() or ""))
        except Exception:
            resultados.append((nome, False, traceback.format_exc(limit=3)))

    def drive():
        from googleapiclient.discovery import build
        build("drive", "v3", developerKey="autoteste", static_discovery=True)   # descricao da API empacotada

    def imagem():
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buf, "JPEG")
        Image.open(io.BytesIO(buf.getvalue())).load()

    def raw():
        import rawpy
        return f"libraw {rawpy.libraw_version}"

    def qr():
        from app import painel
        assert b"<svg" in painel.qr_svg("http://192.168.0.10:50007/painel")

    def cartao():
        import psutil
        return f"{len(psutil.disk_partitions())} particoes"

    def servidor():
        import socket
        import uvicorn
        from app.main import app
        with socket.socket() as s:          # porta livre qualquer: nao atrapalha um programa ja aberto
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]
        srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
        threading.Thread(target=srv.run, daemon=True).start()
        try:
            for _ in range(100):
                if srv.started:
                    break
                time.sleep(0.1)
            assert ja_aberto(porta), "servidor nao respondeu"
            for rota in ("/", "/painel", "/painel/dados", "/api/state"):
                with urllib.request.urlopen(f"http://127.0.0.1:{porta}{rota}", timeout=5) as r:
                    assert r.status == 200, rota
        finally:
            srv.should_exit = True

    def oauth():
        import google_auth_oauthlib.flow  # noqa: F401

    for nome, fn in (("versao", lambda: VERSAO), ("drive", drive), ("oauth", oauth), ("imagem", imagem), ("raw", raw),
                     ("qrcode", qr), ("cartao", cartao), ("servidor", servidor)):
        checar(nome, fn)
    texto = "\n".join(f"{'OK  ' if ok else 'FALHA'} {n} {info}" for n, ok, info in resultados)
    print(texto)
    os.makedirs(BASE, exist_ok=True)
    with open(os.path.join(BASE, "autoteste.txt"), "w", encoding="utf-8") as f:
        f.write(texto + "\n")
    return 0 if all(ok for _, ok, _ in resultados) else 1


def main():
    multiprocessing.freeze_support()
    # executavel sem janela (Windows/macOS): nao existe saida padrao e o uvicorn quebra ao consultar sys.stdout
    if sys.stdout is None or sys.stderr is None:
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if "--autoteste" in sys.argv:
        sys.exit(autoteste())
    if EMPACOTADO:
        log_em_arquivo()
    carregar_env()
    porta = int(os.environ.get("PORT", PORT))
    if ja_aberto(porta):
        if os.environ.get("NO_BROWSER") != "1":
            webbrowser.open(f"http://localhost:{porta}")
        return
    if not EMPACOTADO:
        for nome in ("HousinhoTitulo.txt", "HousinhoFoto.txt"):
            p = os.path.join(RECURSOS, nome)
            if os.path.exists(p):
                print(open(p, encoding="utf-8").read())
    print(f"Descarregador de Fotos v{VERSAO} · http://localhost:{porta}")
    if os.environ.get("NO_BROWSER") != "1":
        threading.Thread(target=abrir_navegador_quando_pronto, args=(porta,), daemon=True).start()

    import uvicorn
    from app.main import app   # importado depois do .env: WEBHOOK_URL, PORT etc. sao lidos na importacao
    uvicorn.run(app, host="0.0.0.0", port=porta, log_level="warning")


if __name__ == "__main__":
    main()
