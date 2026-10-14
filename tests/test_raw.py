"""Conversao de RAW para JPEG ao descarregar. Rodar: .venv/bin/python -m pytest tests -q"""
import os
import subprocess
import sys
import tempfile
import time

TMP = tempfile.mkdtemp(prefix="descarregar-teste-")
os.environ.setdefault("DATA_DIR", os.path.join(TMP, "data"))
os.environ.setdefault("FOTOS_DIR", os.path.join(TMP, "fotos"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app import core, raw, transfer  # noqa: E402
from app.core import E  # noqa: E402


def lightcraft_falso(falhar=()):
    """Substitui subprocess.run: 'revela' o RAW gravando um JPEG de verdade no -o pedido."""
    def run(cmd, **kw):
        _, acao, origem, _, saida = cmd[:5]
        assert acao == "render"
        if os.path.basename(origem) in falhar:
            return subprocess.CompletedProcess(cmd, 1, "", "decoder error")
        Image.new("RGB", (60, 40), "red").save(saida, "JPEG")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return run


@pytest.fixture
def cartao(tmp_path, monkeypatch):
    """Cartao falso com 2 RAW e 1 JPEG; conversor 'instalado'."""
    pasta = tmp_path / "cartao" / "DCIM" / "100CANON"
    pasta.mkdir(parents=True)
    for i, nome in enumerate(("IMG_1.CR3", "IMG_2.JPG", "IMG_3.ARW")):
        (pasta / nome).write_bytes(b"conteudo original " + nome.encode())
        os.utime(pasta / nome, (1_700_000_000 + i, 1_700_000_000 + i))
    transfer.definir_origem(str(tmp_path / "cartao"))
    core.ativar_servir(None)
    E.transfer = {"estado": "idle", "progresso": 0, "total": 0, "feitos": 0, "msg": ""}
    monkeypatch.setattr(raw, "localizar_cli", lambda: "lightcraft-cli")
    monkeypatch.setattr(raw.subprocess, "run", lightcraft_falso())
    yield tmp_path
    E.drive_path = ""


def conteudo_do_cartao(tmp):
    pasta = tmp / "cartao" / "DCIM" / "100CANON"
    return {p.name: p.read_bytes() for p in pasta.iterdir() if p.name != core.MARKER_NAME}


def descarregar(tmp, converter_raw):
    antes = conteudo_do_cartao(tmp)
    r = transfer.iniciar("Ana", str(tmp / "pc"), ["."], "Raiz (Nenhuma)", False, "todas", converter_raw)
    for _ in range(200):
        if E.transfer["estado"] != "rodando":
            break
        time.sleep(0.05)
    assert E.transfer["estado"] == "concluido", E.transfer
    assert conteudo_do_cartao(tmp) == antes, "o cartao nao pode ser alterado"
    return r["destino"]


def test_plano_avisa_raw_e_que_pode_converter(cartao):
    p = transfer.planejar(["."])
    assert p["tem_raw"] and p["pode_converter_raw"]


def test_converte_raw_e_apaga_so_a_copia_do_pc(cartao):
    destino = descarregar(cartao, converter_raw=True)
    assert sorted(os.listdir(destino)) == ["Ana_001.jpg", "Ana_002.jpg", "Ana_003.jpg"]
    assert [os.path.basename(p) for p in E.arquivos_transferidos] == ["Ana_001.jpg", "Ana_002.jpg", "Ana_003.jpg"]
    # o JPEG convertido herda a data da foto (numeracao e revisor ordenam por ela)
    assert os.path.getmtime(os.path.join(destino, "Ana_003.jpg")) == pytest.approx(1_700_000_002)
    assert E.transfer["falhas_raw"] == 0


def test_sem_converter_mantem_raw(cartao):
    destino = descarregar(cartao, converter_raw=False)
    assert sorted(os.listdir(destino)) == ["Ana_001.cr3", "Ana_002.jpg", "Ana_003.arw"]


def test_falha_na_conversao_mantem_o_raw(cartao, monkeypatch):
    monkeypatch.setattr(raw.subprocess, "run", lightcraft_falso(falhar={"Ana_003.arw"}))
    destino = descarregar(cartao, converter_raw=True)
    assert sorted(os.listdir(destino)) == ["Ana_001.jpg", "Ana_002.jpg", "Ana_003.arw"]
    assert E.transfer["falhas_raw"] == 1
    assert "1 RAW não convertido" in E.transfer["msg"]


def test_nunca_converte_nem_apaga_no_cartao(cartao):
    no_cartao = str(cartao / "cartao" / "DCIM" / "100CANON" / "IMG_1.CR3")
    with pytest.raises(ValueError):
        raw.converter(no_cartao, str(cartao / "cartao"))
    with pytest.raises(ValueError):
        raw.converter(no_cartao, str(cartao / "pc"))
    assert os.path.exists(no_cartao)


def test_sem_conversor_recusa_converter(cartao, monkeypatch):
    monkeypatch.setattr(raw, "localizar_cli", lambda: None)
    assert transfer.planejar(["."])["pode_converter_raw"] is False
    with pytest.raises(RuntimeError):
        transfer.iniciar("Ana", str(cartao / "pc"), ["."], "Raiz (Nenhuma)", False, "todas", True)
