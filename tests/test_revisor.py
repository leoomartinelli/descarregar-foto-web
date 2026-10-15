"""Testes da tela de selecao (imagens e zoom). Rodar: .venv/bin/python -m pytest tests -q"""
import io
import os
import time

import test_painel  # noqa: F401  (configura DATA_DIR/FOTOS_DIR temporarios antes de importar o app)
from test_painel import TMP, criar_servir, estado_limpo, local  # noqa: F401 (fixture)

from PIL import Image

from app.core import E


def cartao_com_fotos(tamanho=(4000, 3000)):
    pasta = os.path.join(TMP, f"cartao-zoom-{time.time_ns()}", "DCIM", "100CANON")
    os.makedirs(pasta)
    for k in range(2):
        Image.new("RGB", tamanho, (40 * k, 90, 160)).save(os.path.join(pasta, f"IMG_{k:04d}.JPG"), quality=90)
    return os.path.dirname(os.path.dirname(pasta))


def descarregar_fotos():
    criar_servir()
    local.post("/api/origem", json={"path": cartao_com_fotos()})
    r = local.post("/api/transferencia/iniciar", json={"fotografo": "Ana", "destino_base": E.destino_base,
                                                      "pastas": ["."], "categoria": "Louvor"})
    assert r.status_code == 200, r.text
    for _ in range(200):
        if E.transfer["estado"] != "rodando":
            break
        time.sleep(0.05)
    assert len(local.get("/api/revisor").json()["arquivos"]) == 2


def test_zoom_recebe_a_foto_original_sem_recompactar():
    descarregar_fotos()
    r = local.get("/api/revisor/imagem/0", params={"lado": 0})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.content == open(E.arquivos_transferidos[0], "rb").read()      # o proprio arquivo: qualidade maxima
    assert Image.open(io.BytesIO(r.content)).size == (4000, 3000)


def test_tela_inteira_continua_leve():
    descarregar_fotos()
    r = local.get("/api/revisor/imagem/0")
    assert max(Image.open(io.BytesIO(r.content)).size) == 1600
    # tamanhos absurdos continuam limitados; so lado=0 pede o original
    assert max(Image.open(io.BytesIO(local.get("/api/revisor/imagem/0", params={"lado": 99999}).content)).size) == 4000


def test_original_e_reduzida_tem_etags_diferentes():
    descarregar_fotos()
    a = local.get("/api/revisor/imagem/1").headers["etag"]
    b = local.get("/api/revisor/imagem/1", params={"lado": 0}).headers["etag"]
    assert a != b
    assert local.get("/api/revisor/imagem/1", params={"lado": 0}, headers={"if-none-match": b}).status_code == 304
