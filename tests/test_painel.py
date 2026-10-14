"""Testes do painel de acompanhamento (issue #1). Rodar: .venv/bin/python -m pytest tests -q"""
import os
import sys
import tempfile
import time

TMP = tempfile.mkdtemp(prefix="descarregar-teste-")
os.environ["DATA_DIR"] = os.path.join(TMP, "data")
os.environ["FOTOS_DIR"] = os.path.join(TMP, "fotos")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import core, drive, painel  # noqa: E402
from app.core import E  # noqa: E402
from app.main import app  # noqa: E402

# sem "with": o startup (rede UDP, monitor do cartao, git fetch) nao roda nos testes
local = TestClient(app)
celular = TestClient(app, client=("192.168.0.77", 40000))   # outro aparelho da rede local


@pytest.fixture(autouse=True)
def estado_limpo(monkeypatch):
    E.network_mode = "lider"
    E.auxiliar_stations.clear()
    E.lider_detectado = None
    E.transfer = {"estado": "idle", "progresso": 0, "total": 0, "feitos": 0, "msg": ""}
    core.ativar_servir(None)
    painel.limpar_cache()
    monkeypatch.setattr(painel.platform, "node", lambda: "PC-IGREJA")
    yield
    painel.limpar_cache()


def criar_servir(nome="Culto Teste", vols=("Samuel", "Ana", "Bia")):
    r = local.post("/api/servir", json={"nome": f"{nome} {time.time_ns()}", "voluntarios": list(vols),
                                        "pastas_predefinidas": ["Louvor"]})
    assert r.status_code == 200, r.text
    return r.json()


def cartao(n):
    pasta = tempfile.mkdtemp(dir=TMP, prefix="cartao-")
    os.makedirs(os.path.join(pasta, "DCIM", "100CANON"))
    for i in range(n):
        with open(os.path.join(pasta, "DCIM", "100CANON", f"IMG_{i:04d}.JPG"), "wb") as f:
            f.write(b"\xff\xd8\xff\xd9")
    return pasta


def descarregar(fotografo, n, categoria="Louvor"):
    assert local.post("/api/origem", json={"path": cartao(n)}).status_code == 200
    assert local.post("/api/atividade", json={"acao": "ocupar"}).status_code == 200
    r = local.post("/api/transferencia/iniciar", json={
        "fotografo": fotografo, "destino_base": E.destino_base, "pastas": ["."], "categoria": categoria})
    assert r.status_code == 200, r.text
    for _ in range(100):
        if E.transfer["estado"] != "rodando":
            break
        time.sleep(0.05)
    assert E.transfer["estado"] == "concluido", E.transfer
    painel.limpar_cache()


def dados():
    painel.limpar_cache()
    r = celular.get("/painel/dados")
    assert r.status_code == 200
    return r.json()


def test_celular_acessa_so_o_painel():
    assert celular.get("/painel").status_code == 200
    assert "Painel do Servir" in celular.get("/painel").text
    assert celular.get("/painel/dados").status_code == 200
    assert celular.get("/atividade").status_code == 200
    # o resto da interface continua so na propria maquina
    assert celular.get("/api/state").status_code == 403
    assert celular.post("/api/atividade", json={"acao": "liberar"}).status_code == 403
    assert celular.get("/api/painel/qr.svg").status_code == 403


def test_sem_servir_ativo():
    assert dados() == {"modo": "lider", "servir": None}


def test_qr_code_aponta_para_o_painel():
    criar_servir()
    info = local.get("/api/painel/info").json()
    assert info["urls"][0] == f"http://{info['ips'][0]}:{E.local_port}/painel"
    r = local.get("/api/painel/qr.svg", params={"ip": info["ips"][0]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in r.content
    # ip invalido cai no ip principal em vez de gerar um QR qualquer
    assert local.get("/api/painel/qr.svg", params={"ip": "<script>"}).status_code == 200


def test_status_livre_ocupado_e_tempo():
    criar_servir()
    d = dados()
    assert d["estacoes"][0]["papel"] == "lider" and d["estacoes"][0]["atividade"]["estado"] == "livre"
    assert d["agora"] == [] and d["gerais"]["pcs_livres"] == 1

    local.post("/api/atividade", json={"acao": "ocupar"})            # escolheu as fotos do cartao
    local.post("/api/atividade", json={"acao": "ocupar", "voluntario": "Samuel"})
    E.atividade["inicio_ts"] -= 65                                   # comecou ha 1 min 05 s
    d = dados()
    agora = d["agora"][0]
    assert agora["voluntario"] == "Samuel" and agora["papel"] == "lider" and agora["estacao"] == "PC-IGREJA"
    assert 65 <= agora["segundos"] < 70
    assert d["gerais"]["pcs_ocupados"] == 1 and d["gerais"]["pcs_livres"] == 0
    assert d["faltam"][0] == {"voluntario": "Samuel", "descarregando_agora": True}

    # o tempo nao zera quando so muda o voluntario escolhido
    local.post("/api/atividade", json={"acao": "ocupar", "voluntario": "Ana"})
    assert dados()["agora"][0]["segundos"] >= 65

    local.post("/api/atividade", json={"acao": "liberar"})
    assert dados()["agora"] == []


def test_ja_descarregou_e_quem_falta():
    sv = criar_servir()
    descarregar("Samuel", 5)
    d = dados()
    # depois da copia o PC continua ocupado (revisao/envio) ate o "Novo Descarregamento"
    assert d["agora"][0]["fase"] == "concluido" and d["agora"][0]["voluntario"] == "Samuel"
    assert local.post("/api/transferencia/nova").status_code == 200
    descarregar("samuel", 3, categoria="Raiz (Nenhuma)")   # mesma pessoa, outra caixa e outra categoria
    local.post("/api/transferencia/nova")

    d = dados()
    assert d["servir"]["id"] == sv["id"]
    assert d["agora"] == []
    assert [(v["voluntario"], v["fotos"], v["vezes"]) for v in d["ja_descarregaram"]] == [("Samuel", 8, 2)]
    assert d["ja_descarregaram"][0]["categorias"] == {"Louvor": 5}
    assert [f["voluntario"] for f in d["faltam"]] == ["Ana", "Bia"]
    g = d["gerais"]
    assert (g["total_fotos"], g["ja_descarregaram"], g["faltam"], g["voluntarios"]) == (8, 1, 2, 3)


def test_progresso_da_copia_aparece():
    criar_servir()
    E.atividade = {"estado": "ocupado", "fase": "copiando", "voluntario": "Bia", "inicio_ts": time.time()}
    E.transfer.update(feitos=40, total=100)
    a = dados()["agora"][0]
    assert (a["fase"], a["feitos"], a["total"]) == ("copiando", 40, 100)


class Resp:
    def __init__(self, codigo, corpo=None):
        self.status_code, self._corpo = codigo, corpo

    def json(self):
        return self._corpo


def test_junta_os_pcs_auxiliares(monkeypatch):
    sv = criar_servir()
    descarregar("Samuel", 2)
    local.post("/api/transferencia/nova")
    E.auxiliar_stations.update({
        "10.0.0.2": {"nome": "PC-AUX-1", "port": 50007, "last_seen": time.time()},
        "10.0.0.3": {"nome": "PC-AUX-2", "port": 50007, "last_seen": time.time()},
        "10.0.0.4": {"nome": "PC-DESKTOP", "port": 50007, "last_seen": time.time()},
        "10.0.0.5": {"nome": "PC-OUTRO-SERVIR", "port": 50007, "last_seen": time.time()},
    })
    respostas = {
        "10.0.0.2": Resp(200, {"servir_id": sv["id"], "atividade": {
            "estado": "ocupado", "fase": "copiando", "voluntario": "Ana", "segundos": 30, "feitos": 1, "total": 9},
            "descarregados": [{"voluntario": "Samuel", "categoria": "Louvor", "fotos": 4, "vezes": 1, "ultimo": ""},
                              {"voluntario": "Bia", "categoria": None, "fotos": 7, "vezes": 1, "ultimo": ""}]}),
        "10.0.0.4": Resp(404),
        "10.0.0.5": Resp(200, {"servir_id": "outro", "atividade": {"estado": "livre"},
                               "descarregados": [{"voluntario": "Ana", "fotos": 99, "vezes": 1}]}),
    }

    def get(url, timeout):
        ip = url.split("//")[1].split(":")[0]
        if ip not in respostas:
            raise painel.requests.ConnectionError("sem rede")
        return respostas[ip]
    monkeypatch.setattr(painel.requests, "get", get)

    d = dados()
    est = {e["nome"]: e for e in d["estacoes"]}
    assert est["PC-AUX-1"]["online"] and est["PC-AUX-1"]["atividade"]["estado"] == "ocupado"
    assert not est["PC-AUX-2"]["online"]
    assert est["PC-DESKTOP"]["online"] and est["PC-DESKTOP"]["sem_suporte"]
    assert d["agora"] == [{"estacao": "PC-AUX-1", "papel": "auxiliar", "voluntario": "Ana", "fase": "copiando",
                           "segundos": 30, "feitos": 1, "total": 9}]
    fotos = {v["voluntario"]: v["fotos"] for v in d["ja_descarregaram"]}
    assert fotos == {"Samuel": 6, "Bia": 7}            # o auxiliar de outro Servir nao entra na conta
    samuel = next(v for v in d["ja_descarregaram"] if v["voluntario"] == "Samuel")
    assert sorted(samuel["estacoes"]) == ["PC-AUX-1", "PC-IGREJA"]
    assert d["faltam"] == [{"voluntario": "Ana", "descarregando_agora": True}]
    g = d["gerais"]
    assert (g["pcs"], g["pcs_ocupados"], g["pcs_livres"], g["pcs_offline"], g["total_fotos"]) == (5, 1, 2, 1, 13)


def test_estacao_auxiliar_indica_o_lider():
    criar_servir()
    E.network_mode = "auxiliar"
    E.lider_detectado = {"ip": "10.0.0.1", "port": 50007, "nome_evento": "X", "evento_id": "1"}
    d = dados()
    assert d["modo"] == "auxiliar" and d["lider"]["ip"] == "10.0.0.1"


def test_atividade_do_auxiliar_para_o_lider():
    sv = criar_servir()
    descarregar("Bia", 3)
    a = celular.get("/atividade").json()
    assert a["servir_id"] == sv["id"] and a["nome"] == "PC-IGREJA"
    assert a["atividade"]["estado"] == "ocupado" and a["atividade"]["voluntario"] == "Bia"
    assert "inicio_ts" not in a["atividade"]
    assert a["descarregados"] == [{"voluntario": "Bia", "categoria": "Louvor", "fotos": 3, "vezes": 1,
                                   "ultimo": a["descarregados"][0]["ultimo"]}]


def test_finalizar_ou_trocar_servir_libera_o_pc():
    criar_servir()
    local.post("/api/atividade", json={"acao": "ocupar", "voluntario": "Ana"})
    local.post("/api/avulso")                      # botao "Início"
    assert E.atividade == {"estado": "livre"}


def test_enviar_ao_drive_libera_o_pc(monkeypatch):
    criar_servir()
    descarregar("Samuel", 2)
    assert dados()["agora"][0]["voluntario"] == "Samuel"
    monkeypatch.setattr(drive, "iniciar_upload", lambda link, fot: {"id": 1, "total": 2, "ignoradas": 0})
    assert local.post("/api/upload/iniciar", json={"link": ""}).status_code == 200
    d = dados()
    assert d["agora"] == [] and d["estacoes"][0]["atividade"]["estado"] == "livre"


def test_envio_com_erro_nao_libera_o_pc(monkeypatch):
    criar_servir()
    descarregar("Samuel", 2)

    def falha(link, fot):
        raise RuntimeError("Você não está logado no Google.")
    monkeypatch.setattr(drive, "iniciar_upload", falha)
    assert local.post("/api/upload/iniciar", json={"link": ""}).status_code == 400
    assert dados()["agora"][0]["voluntario"] == "Samuel"


def test_envios_ao_drive_de_todos_os_pcs(monkeypatch):
    sv = criar_servir()
    E.uploads[:] = [
        {"id": 1, "fotografo": "Rafael Soler", "total": 41, "feitos": 41, "progresso": 1, "erros": 0,
         "estado": "concluido", "destino": "a pasta 'A3'", "atuais": [], "servir_id": sv["id"],
         "msg": "41 de 41 fotos enviadas para a pasta 'A3'."},
        {"id": 2, "fotografo": "Velho", "total": 1, "feitos": 1, "progresso": 1, "erros": 0, "estado": "concluido",
         "destino": "x", "atuais": [], "servir_id": "servir-de-ontem", "msg": ""},
    ]
    E.auxiliar_stations["10.0.0.2"] = {"nome": "PC-AUX-1", "port": 50007, "last_seen": time.time()}
    job_aux = {"id": 7, "fotografo": "Ana", "total": 10, "feitos": 3, "progresso": 0.3, "erros": 0,
               "estado": "rodando", "destino": "a pasta 'Louvor'", "atuais": ["Ana_004.JPG"], "servir_id": sv["id"],
               "msg": "Enviando 3/10..."}
    monkeypatch.setattr(painel.requests, "get", lambda url, timeout: Resp(200, {
        "servir_id": sv["id"], "atividade": {"estado": "livre"}, "descarregados": [], "uploads": [job_aux]}))
    try:
        ups = dados()["uploads"]
    finally:
        E.uploads.clear()
    assert [(u["fotografo"], u["estacao"], u["papel"], u["estado"]) for u in ups] == [
        ("Rafael Soler", "PC-IGREJA", "lider", "concluido"), ("Ana", "PC-AUX-1", "auxiliar", "rodando")]
    assert ups[1]["atuais"] == ["Ana_004.JPG"] and ups[0]["msg"].startswith("41 de 41")
