"""Teste da atualizacao automatica, ponta a ponta, com o programa JA INSTALADO (roda no GitHub Actions).

Abre o programa instalado fingindo ser a versao 0.0.1 e aponta a busca de versoes para um servidor de releases falso
(local) com os arquivos recem-compilados. Confere que ele baixa, confere o SHA-256, se instala sozinho, reabre na
versao certa e volta com o Servir que estava ativo. Uso:
    python packaging/teste_atualizacao.py <executavel instalado> <pasta com os pacotes>
Codigo de saida 0 = tudo certo."""
import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

EXE, PASTA = sys.argv[1], os.path.abspath(sys.argv[2])
VERSAO = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION")).read().strip()
PORTA_FALSA, PORTA = 8765, int(os.environ.get("PORT", 50007))
liberado = threading.Event()   # so publica a "versao nova" depois que o Servir estiver ativo


class Releases(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/latest":
            if not liberado.is_set():
                return self.send_error(404)
            arquivos = sorted(os.listdir(PASTA))
            corpo = json.dumps({"tag_name": f"v{VERSAO}", "html_url": "http://127.0.0.1/release", "assets": [
                {"name": n, "browser_download_url": f"http://127.0.0.1:{PORTA_FALSA}/arquivos/{n}"} for n in arquivos]})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return self.wfile.write(corpo.encode())
        if self.path.startswith("/arquivos/"):
            caminho = os.path.join(PASTA, os.path.basename(self.path))
            if os.path.isfile(caminho):
                self.send_response(200)
                self.send_header("Content-Length", str(os.path.getsize(caminho)))
                self.end_headers()
                with open(caminho, "rb") as f:
                    while bloco := f.read(1 << 20):
                        self.wfile.write(bloco)
                return
        self.send_error(404)


def api(metodo, rota, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORTA}{rota}", data=dados, method=metodo,
                                 headers={"Content-Type": "application/json"} if dados else {})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


def esperar(cond, segundos, msg):
    fim = time.time() + segundos
    while time.time() < fim:
        try:
            v = cond()
            if v:
                return v
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit(f"FALHA: {msg}")


# SHA256SUMS.txt como na release de verdade
with open(os.path.join(PASTA, "SHA256SUMS.txt"), "w") as f:
    for n in sorted(os.listdir(PASTA)):
        if n != "SHA256SUMS.txt":
            f.write(f"{hashlib.sha256(open(os.path.join(PASTA, n), 'rb').read()).hexdigest()}  {n}\n")
print(open(os.path.join(PASTA, "SHA256SUMS.txt")).read())

srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORTA_FALSA), Releases)
threading.Thread(target=srv.serve_forever, daemon=True).start()

env = dict(os.environ, NO_BROWSER="1", DESCARREGADOR_FINGIR_VERSAO="0.0.1",
           DESCARREGADOR_API_RELEASES=f"http://127.0.0.1:{PORTA_FALSA}/latest", DESCARREGADOR_INTERVALO_BUSCA="3")
subprocess.Popen([EXE], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
esperar(lambda: api("GET", "/api/versao")["versao"] == "0.0.1", 60, "o programa (fingindo v0.0.1) não abriu")
print("OK    programa aberto como v0.0.1")

# a pasta de dados (login do Google, Dias de Servir, historico) nao pode ser tocada pela atualizacao
DADOS = os.path.join(os.path.expanduser("~"), "Descarregador de Fotos", "data")
MARCA = os.path.join(DADOS, "teste_login_google.txt")
with open(MARCA, "w") as f:
    f.write("token salvo antes da atualizacao")
sv = api("POST", "/api/servir", {"nome": f"Servir Atualizacao {int(time.time())}", "voluntarios": ["Ana"]})
api("POST", "/register", {"ip": "10.9.9.9", "nome": "PC-AUX-TESTE", "port": 9, "versao": "0.0.1"})
print(f"OK    Servir ativo antes da atualização: {sv['id']}")
liberado.set()

esperar(lambda: api("GET", "/api/state")["atualizacao"]["estado"] in ("pronta", "instalando"), 120,
        "não baixou a versão nova")
print("OK    versão nova baixada e conferida (SHA-256)")
nova = esperar(lambda: api("GET", "/api/versao")["versao"] == VERSAO and api("GET", "/api/state"), 240,
               f"o programa não voltou na v{VERSAO}")
print(f"OK    reabriu sozinho na v{VERSAO}")
assert (nova["active_servir"] or {}).get("id") == sv["id"], f"Servir não foi retomado: {nova['active_servir']}"
print("OK    voltou com o mesmo Servir ativo")
assert any(a["nome"] == "PC-AUX-TESTE" for a in nova["rede"]["auxiliares"]), "PCs auxiliares não foram retomados"
print("OK    voltou com os PCs auxiliares conectados")
assert nova["atualizacao"]["estado"] == "nenhuma", nova["atualizacao"]
assert open(MARCA).read() == "token salvo antes da atualizacao", "a pasta de dados foi alterada"
assert any(d["id"] == sv["id"] for d in api("GET", "/api/servir")), "Dias de Servir perdidos"
os.remove(MARCA)
print("OK    pasta de dados intacta (login do Google, Dias de Servir)")
api("POST", "/api/encerrar")
print("\nTUDO CERTO")
