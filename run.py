"""Inicia o servidor e abre o navegador. Uso: python run.py"""
import os
import threading
import time
import webbrowser

import uvicorn

PORT = int(os.environ.get("PORT", 50007))

if __name__ == "__main__":
    # carrega .env simples (KEY=VALUE) sem sobrescrever variaveis existentes
    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env):
        for linha in open(env, encoding="utf-8"):
            if "=" in linha and not linha.strip().startswith("#"):
                k, v = linha.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))
    PORT = int(os.environ.get("PORT", PORT))
    for nome in ("HousinhoTitulo.txt", "HousinhoFoto.txt"):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), nome)
        if os.path.exists(p):
            print(open(p, encoding="utf-8").read())
    if os.environ.get("NO_BROWSER") != "1":
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(f"http://localhost:{PORT}")), daemon=True).start()
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="warning")
