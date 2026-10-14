"""Testes do controle de versao. Rodar: .venv/bin/python -m pytest tests -q"""
import os

import test_painel  # noqa: F401  (configura DATA_DIR/FOTOS_DIR temporarios antes de importar o app)
from test_painel import Resp, celular, criar_servir, dados, estado_limpo, local  # noqa: F401 (fixture)

from app import main, painel, versao
from app.core import E

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_versao_vem_do_arquivo_version():
    assert versao.VERSAO == open(os.path.join(RAIZ, "VERSION")).read().strip()
    assert local.get("/api/versao").json() == {"app": "descarregador-fotos", "versao": versao.VERSAO,
                                               "empacotado": False}
    assert local.get("/api/state").json()["versao"] == versao.VERSAO


def test_changelog_tem_a_versao_atual():
    assert f"## [{versao.VERSAO}]" in open(os.path.join(RAIZ, "CHANGELOG.md"), encoding="utf-8").read()


def test_comparacao_de_versoes():
    assert versao.tupla("v1.10.0") > versao.tupla("1.9.9") > versao.tupla("1.9")
    assert versao.tupla("2.0.0-beta") == (2, 0, 0)
    assert versao.tupla("") == (0, 0, 0)


def test_aviso_de_release_nova(monkeypatch):
    import requests
    main.UPDATE.update(disponivel=False, msg="", url="")
    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp(200, {
        "tag_name": "v99.0.0", "html_url": "https://github.com/x/releases/tag/v99.0.0"}))
    main.verificar_release()
    assert main.UPDATE["disponivel"] and main.UPDATE["url"].endswith("v99.0.0")
    main.UPDATE.update(disponivel=False, msg="", url="")
    monkeypatch.setattr(requests, "get", lambda *a, **k: Resp(200, {"tag_name": f"v{versao.VERSAO}"}))
    main.verificar_release()
    assert not main.UPDATE["disponivel"]                    # mesma versao: sem aviso


def test_versao_de_cada_pc_no_painel(monkeypatch):
    sv = criar_servir()
    assert local.post("/register", json={"ip": "10.0.0.8", "nome": "PC-VELHO", "port": 50007,
                                         "versao": "0.9.0"}).status_code == 200
    local.post("/register", json={"ip": "10.0.0.9", "nome": "PC-DESKTOP", "port": 50007})   # app desktop
    monkeypatch.setattr(painel.requests, "get", lambda url, timeout: Resp(404))
    d = dados()
    v = {e["nome"]: e["versao"] for e in d["estacoes"]}
    assert v["PC-VELHO"] == "0.9.0" and v["PC-DESKTOP"] is None
    assert d["versao_lider"] == versao.VERSAO
    assert sorted(d["versoes_diferentes"]) == ["PC-DESKTOP", "PC-VELHO"]
    assert celular.get("/atividade").json()["versao"] == versao.VERSAO
    assert sv


def test_encerrar_so_na_propria_maquina(monkeypatch):
    chamado = []
    monkeypatch.setattr(main.threading, "Timer", lambda t, fn, args: type("T", (), {"start": lambda s: chamado.append(t)})())
    assert celular.post("/api/encerrar").status_code == 403
    assert local.post("/api/encerrar").json() == {"ok": True} and chamado == [0.5]


def test_programa_instalado_nao_chama_o_git(monkeypatch):
    # no Windows cada chamada ao git abria um terminal: a tela consulta /api/state a cada 3 segundos
    import subprocess
    chamadas = []
    monkeypatch.setattr(versao, "EMPACOTADO", True)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: chamadas.append(a) or 1 / 0)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: chamadas.append(a) or 1 / 0)
    for _ in range(3):
        main._cache_reinicio["t"] = 0          # forca a verificacao de "precisa reiniciar"
        assert local.get("/api/state").json()["precisa_reiniciar"] is False
    monkeypatch.setattr(main, "verificar_release", lambda: None)
    main.verificar_atualizacao()
    assert chamadas == []
