"""Teste do protocolo de rede Lider/Auxiliar contra um programa JA ABERTO (o executavel compilado).

Este script faz o papel de um PC auxiliar de outro sistema operacional: usa so HTTP/UDP, como um Windows, Mac ou
Linux faria na rede da igreja. Roda no GitHub Actions em cada sistema. Uso:
    python packaging/teste_rede.py [porta]
Codigo de saida 0 = tudo certo."""
import json
import socket
import sys
import time
import urllib.request

PORTA = int(sys.argv[1]) if len(sys.argv) > 1 else 50007
BASE = f"http://127.0.0.1:{PORTA}"
UDP = 50008
falhas = []


def req(metodo, rota, corpo=None, esperado=200):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(BASE + rota, data=dados, method=metodo,
                               headers={"Content-Type": "application/json"} if dados else {})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            codigo, texto = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        codigo, texto = e.code, e.read()
    if codigo != esperado:
        raise AssertionError(f"{metodo} {rota}: esperado {esperado}, veio {codigo}: {texto[:200]!r}")
    try:
        return json.loads(texto)
    except ValueError:
        return texto.decode("utf-8", "replace")   # paginas HTML e o SVG do QR code


def passo(nome, fn):
    try:
        info = fn()
        print(f"OK    {nome}{' · ' + str(info) if info else ''}")
    except Exception as e:
        falhas.append(nome)
        print(f"FALHA {nome}: {e}")


for _ in range(60):
    try:
        versao = req("GET", "/api/versao")
        break
    except Exception:
        time.sleep(1)
else:
    print("FALHA programa nao respondeu")
    sys.exit(1)
print(f"Programa v{versao['versao']} (empacotado={versao['empacotado']}) em {BASE}")

# escuta o anuncio UDP do lider antes de ativar o Servir
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except (AttributeError, OSError):
    pass
sock.bind(("", UDP))
sock.settimeout(1.0)

S = {}
passo("modo lider", lambda: req("POST", "/api/rede/modo", {"modo": "lider"}))
passo("criar e ativar Servir", lambda: S.update(sv=req("POST", "/api/servir", {
    "nome": f"Teste Rede {int(time.time())}", "voluntarios": ["Ana", "Bruno"], "pastas_predefinidas": ["Louvor"]})))


def anuncio_udp():
    fim = time.time() + 12
    while time.time() < fim:
        try:
            msg = sock.recvfrom(1024)[0].decode()
        except socket.timeout:
            continue
        if msg.startswith("SERVIR_LEADER:") and msg.split(":")[4] == S["sv"]["id"]:
            return msg
    raise AssertionError("nenhum anuncio SERVIR_LEADER recebido em 12 s")


passo("anuncio UDP do lider (porta 50008)", anuncio_udp)
passo("auxiliar se registra (/register)", lambda: req("POST", "/register", {
    "ip": "127.0.0.1", "nome": "AUX-TESTE", "port": 9, "versao": versao["versao"]}))
passo("auxiliar baixa o Servir (/preset)", lambda: req("GET", "/preset")["id"] == S["sv"]["id"] or 1 / 0)


def numeracao():
    # a chave usa "/" em todos os sistemas (o auxiliar Windows converte "\" antes de mandar)
    corpo = {"chave": f"Louvor {time.strftime('%Y-%m-%d')}/Ana", "fotografo": "Ana", "quantidade": 10}
    a = req("POST", "/numeracao", corpo)["inicio"]
    b = req("POST", "/numeracao", corpo)["inicio"]
    assert (a, b) == (1, 11), (a, b)
    req("POST", "/numeracao", {**corpo, "chave": "../fora"}, esperado=400)
    return f"faixas {a} e {b}"


passo("numeracao unica entre PCs (/numeracao)", numeracao)
passo("estatisticas (/stats)", lambda: isinstance(req("GET", "/stats")["categorias"], list) or 1 / 0)
passo("status do PC (/atividade)", lambda: req("GET", "/atividade")["versao"] == versao["versao"] or 1 / 0)


def painel():
    d = req("GET", "/painel/dados")
    nomes = {e["nome"]: e for e in d["estacoes"]}
    assert d["servir"]["id"] == S["sv"]["id"]
    assert "AUX-TESTE" in nomes and not nomes["AUX-TESTE"]["online"]   # porta 9: auxiliar desligado
    assert [f["voluntario"] for f in d["faltam"]] == ["Ana", "Bruno"]
    assert "<svg" in req("GET", "/api/painel/qr.svg")
    return f"{len(d['estacoes'])} PCs"


passo("painel do celular (/painel/dados)", painel)
passo("pagina do painel (/painel)", lambda: "Painel do Servir" in req("GET", "/painel") or 1 / 0)
passo("lider finaliza auxiliar (/finalize)", lambda: req("POST", "/finalize"))
passo("Servir desativado", lambda: req("GET", "/api/state")["active_servir"] is None or 1 / 0)
sock.close()

print(f"\n{'TUDO CERTO' if not falhas else 'FALHAS: ' + ', '.join(falhas)}")
sys.exit(1 if falhas else 0)
