"""Testes da atualizacao automatica do programa instalado. Rodar: .venv/bin/python -m pytest tests -q"""
import hashlib
import os
import time

import test_painel  # noqa: F401  (configura DATA_DIR/FOTOS_DIR temporarios antes de importar o app)
from test_painel import Resp, criar_servir, estado_limpo, local  # noqa: F401 (fixture)

from app import atualizador, core, main, versao
from app.core import E

REL = {"tag_name": "v9.9.9", "html_url": "https://github.com/x/releases/tag/v9.9.9", "assets": [
    {"name": f"DescarregadorDeFotos-9.9.9{s}", "browser_download_url": f"https://x/{s}"} for s in
    ("-windows-instalador.exe", "-windows-portatil.zip", "-macos-apple-silicon.dmg", "-macos-intel.dmg",
     "-linux-amd64.deb", "-linux-amd64.tar.gz")] + [{"name": "SHA256SUMS.txt", "browser_download_url": "https://x/s"}]}


def test_escolhe_o_arquivo_de_cada_sistema():
    nome = lambda tipo, maq: (atualizador.escolher_arquivos(REL, tipo, maq)[0] or {}).get("name")  # noqa: E731
    assert nome("windows", "AMD64").endswith("-windows-instalador.exe")
    assert nome("macos", "arm64").endswith("-macos-apple-silicon.dmg")
    assert nome("macos", "x86_64").endswith("-macos-intel.dmg")
    assert nome("deb", "x86_64").endswith(".deb") and nome("targz", "x86_64").endswith(".tar.gz")
    assert nome("deb", "aarch64") is None                       # nao ha pacote Linux ARM
    assert atualizador.escolher_arquivos(REL, "windows", "AMD64")[1]["name"] == "SHA256SUMS.txt"


def test_so_atualiza_para_versao_maior(monkeypatch):
    monkeypatch.setattr(versao, "VERSAO", "1.0.3")
    for tag, esperado in (("v1.0.4", True), ("v1.0.3", False), ("v1.0.2", False), ("v1.1.0", True)):
        monkeypatch.setattr(atualizador.requests, "get", lambda *a, **k: Resp(200, {"tag_name": tag}))
        assert bool(atualizador.buscar_release()) is esperado, tag
    monkeypatch.setattr(atualizador.requests, "get", lambda *a, **k: Resp(403))   # limite da API do GitHub
    assert atualizador.buscar_release() is None


class Download:
    def __init__(self, dados):
        self.dados, self.text, self.status_code = dados, "", 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, n):
        yield self.dados


def test_baixa_e_confere_o_sha256(monkeypatch, tmp_path):
    monkeypatch.setattr(atualizador, "PASTA", str(tmp_path))
    conteudo = b"instalador de verdade"
    nome = "DescarregadorDeFotos-9.9.9-windows-instalador.exe"
    somas = Download(b"")
    somas.text = f"{hashlib.sha256(conteudo).hexdigest()}  {nome}\nabc  outro.dmg\n"
    monkeypatch.setattr(atualizador.requests, "get", lambda url, **k: somas if url.endswith("/s") else Download(conteudo))
    caminho = atualizador.baixar(REL, "windows")
    assert open(caminho, "rb").read() == conteudo
    # arquivo adulterado/corrompido no caminho: nao instala
    monkeypatch.setattr(atualizador.requests, "get", lambda url, **k: somas if url.endswith("/s") else Download(b"x"))
    try:
        atualizador.baixar(REL, "windows")
        raise AssertionError("deveria recusar")
    except RuntimeError as e:
        assert "SHA-256" in str(e)
    assert os.listdir(tmp_path) == []


def test_so_instala_com_o_pc_livre(monkeypatch):
    criar_servir()
    assert atualizador.motivo_ocupado() is None
    local.post("/api/atividade", json={"acao": "ocupar", "voluntario": "Ana"})
    assert "voluntário" in atualizador.motivo_ocupado()
    local.post("/api/atividade", json={"acao": "liberar"})
    E.uploads.append({"estado": "rodando"})
    try:
        assert "Drive" in atualizador.motivo_ocupado()
    finally:
        E.uploads.clear()
    # lider espera os auxiliares terminarem (eles pedem a numeracao ao lider)
    E.auxiliar_stations["10.0.0.2"] = {"nome": "AUX", "port": 50007}
    monkeypatch.setattr(test_painel.painel.requests, "get", lambda url, timeout: Resp(200, {
        "atividade": {"estado": "ocupado", "fase": "copiando", "voluntario": "Bia", "segundos": 5}}))
    test_painel.painel.limpar_cache()
    assert "outro PC" in atualizador.motivo_ocupado()


def test_volta_como_estava_depois_de_atualizar(monkeypatch):
    sv = criar_servir()
    E.auxiliar_stations["10.0.0.2"] = {"nome": "AUX", "port": 50007, "versao": "1.0.0"}
    atualizador.salvar_retomar()
    core.ativar_servir(None)
    E.auxiliar_stations.clear()
    monkeypatch.setattr(main.lan, "iniciar_servicos", lambda: None)
    monkeypatch.setattr(main.atualizador, "iniciar", lambda: None)
    monkeypatch.setattr(main.threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda s: None})())
    main.iniciar()
    assert E.active_servir["id"] == sv["id"] and "10.0.0.2" in E.auxiliar_stations
    assert not os.path.exists(atualizador.ARQ_RETOMAR)          # so retoma uma vez
    core.ativar_servir(None)
    main.iniciar()                                               # abrir normalmente nao retoma nada
    assert E.active_servir is None


def test_retomar_antigo_e_ignorado():
    core.gravar_json(atualizador.ARQ_RETOMAR, {"ts": time.time() - 3600, "servir": {"id": "x", "nome": "X"}})
    assert atualizador.ler_retomar() is None


def test_scripts_de_instalacao(monkeypatch):
    monkeypatch.setattr(atualizador.os.path, "realpath", lambda p: p)   # caminho de Mac, mesmo rodando no Windows
    monkeypatch.setattr(atualizador.sys, "executable", "/Applications/Descarregador de Fotos.app/Contents/MacOS/DescarregadorDeFotos")
    mac = atualizador._script_unix("macos", "/tmp/novo.dmg")
    assert "APP='/Applications/Descarregador de Fotos.app'" in mac and "--sem-navegador" in mac
    assert "mv \"$APP.velho\" \"$APP\"" in mac                  # falhou: volta a versao antiga
    win = atualizador._script_windows(r"C:\Users\João\Descarregador de Fotos\atualizacao\inst.exe",
                                      r"C:\Users\João\AppData\Local\Programs\Descarregador de Fotos\D.exe")
    assert "/VERYSILENT" in win and "/REABRIR=1" in win and "ExitCode -ne 0" in win
    assert '/LOG="C:' in win                                     # caminho com espacos vai entre aspas
    assert "João" in win


def test_estado_da_atualizacao_na_tela():
    assert local.get("/api/state").json()["atualizacao"]["estado"] in ("nenhuma", "baixando", "pronta", "erro", "manual")
