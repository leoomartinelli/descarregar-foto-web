"""Editor de fotos (motor do LightCraft). Rodar: .venv/bin/python -m pytest tests -q

Os testes que revelam fotos usam o lightcraft-cli de verdade (packaging/baixar_lightcraft.py); sem ele sao pulados."""
import io
import json
import os
import time

import test_painel  # noqa: F401  (configura DATA_DIR/FOTOS_DIR temporarios antes de importar o app)
from test_painel import TMP, criar_servir, estado_limpo, local  # noqa: F401 (fixture)

import numpy as np
import pytest
from PIL import Image

from app import core, editor, raw, stats
from app.core import E

motor = pytest.mark.skipif(not raw.disponivel(), reason="lightcraft-cli não instalado (packaging/baixar_lightcraft.py)")


def brilho(dados):
    return np.asarray(Image.open(io.BytesIO(dados)).convert("L"), float).mean()


def descarregar(n=2):
    criar_servir()
    pasta = os.path.join(TMP, f"cartao-editor-{time.time_ns()}", "DCIM", "100CANON")
    os.makedirs(pasta)
    for k in range(n):
        y, x = np.mgrid[0:1200, 0:1800]
        img = np.dstack([x / 1800 * 220, y / 1200 * 180 + 20, np.full_like(x, 90.0)]).astype("uint8")
        Image.fromarray(img).save(os.path.join(pasta, f"IMG_{k:04d}.JPG"), quality=92)
    local.post("/api/origem", json={"path": os.path.dirname(os.path.dirname(pasta))})
    r = local.post("/api/transferencia/iniciar", json={"fotografo": "Ana", "destino_base": E.destino_base,
                                                      "pastas": ["."], "categoria": "Louvor"})
    assert r.status_code == 200, r.text
    for _ in range(200):
        if E.transfer["estado"] != "rodando":
            break
        time.sleep(0.05)
    return list(E.arquivos_transferidos)


def esperar_salvar():
    for _ in range(300):
        if not editor.pendentes():
            return
        time.sleep(0.05)
    raise AssertionError("salvamento não terminou")


# ---------- sem o motor ----------

def test_ajustes_fora_da_faixa_e_controles_desconhecidos():
    aj = editor.limpar({"valores": {"light.exposure": 9, "light.contrast": -500, "hack.x": 1, "wb.temp": 1},
                        "wb": {"modo": "custom", "temp": 999999, "tint": -999}})
    assert aj["valores"] == {"light.exposure": 5.0, "light.contrast": -100}
    assert aj["wb"] == {"modo": "custom", "temp": 50000.0, "tint": -150.0}
    assert editor.limpar({"wb": {"modo": "qualquer"}})["wb"] == {"modo": "asShot"}
    # modo pronto leva os numeros (o LightCraft revela por eles); "Como fotografado" nao
    assert editor.limpar({"wb": {"modo": "tungsten", "temp": 3368, "tint": 2}})["wb"] == {
        "modo": "tungsten", "temp": 3368.0, "tint": 2.0}
    assert editor.limpar({"wb": {"modo": "asShot", "temp": 3000, "tint": 9}})["wb"] == {"modo": "asShot"}


def test_formato_do_lightcraft():
    s = editor.para_lightcraft({"valores": {"light.exposure": 0.5, "curve.darks": -10, "color.vibrance": 20},
                                "wb": {"modo": "custom", "temp": 4800, "tint": 5}})
    assert s == {"light": {"exposure": 0.5}, "curve": {"darks": -10.0}, "color": {"vibrance": 20.0},
                 "wb": {"mode": "custom", "temp": 4800.0, "tint": 5.0}}
    assert editor.para_lightcraft(editor.ajustes_padrao())["wb"] == {"mode": "asShot"}


def test_sem_ajuste_e_padrao():
    assert editor.e_padrao(editor.ajustes_padrao())
    assert not editor.e_padrao({"valores": {"light.exposure": 0.01}})
    assert not editor.e_padrao({"wb": {"modo": "auto"}})


def test_pastas_ocultas_nao_contam(tmp_path):
    (tmp_path / "Ana" / ".originais").mkdir(parents=True)
    (tmp_path / "Ana" / "Ana_001.jpg").write_bytes(b"x")
    (tmp_path / "Ana" / ".originais" / "Ana_009.jpg").write_bytes(b"x")
    assert core.maior_numero(str(tmp_path), "Ana") == 1
    assert core.tem_midia(str(tmp_path / "Ana"))
    (tmp_path / "Ana" / "Ana_001.jpg").unlink()
    assert not core.tem_midia(str(tmp_path / "Ana"))


# ---------- com o motor de verdade ----------

@motor
def test_previa_ao_vivo_com_ajustes():
    descarregar(1)
    base = local.get("/api/editor/0/previa", params={"aj": "{}", "lado": 600})
    assert base.status_code == 200 and base.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(base.content)).size) == 600
    clara = local.get("/api/editor/0/previa", params={"aj": '{"valores": {"light.exposure": 1.5}}', "lado": 600})
    assert brilho(clara.content) > brilho(base.content) + 15
    quente = local.get("/api/editor/0/previa", params={
        "aj": '{"wb": {"modo": "custom", "temp": 3000, "tint": 0}}', "lado": 600})
    assert quente.status_code == 200


@motor
def test_salvar_guarda_a_original_e_restaurar_volta():
    fotos = descarregar(2)
    original = open(fotos[0], "rb").read()
    aj = {"valores": {"light.exposure": 1.0, "color.saturation": 30}, "wb": {"modo": "asShot"}}
    assert local.post("/api/editor/0/salvar", json={"ajustes": aj}).json() == {"ok": True}
    esperar_salvar()
    editada = open(fotos[0], "rb").read()
    assert editada != original and Image.open(fotos[0]).size == (1800, 1200)     # tamanho cheio, mesmo nome
    guardada = os.path.join(os.path.dirname(fotos[0]), ".originais", os.path.basename(fotos[0]))
    assert open(guardada, "rb").read() == original
    assert E.arquivos_transferidos == fotos
    info = local.get("/api/editor/0").json()
    assert info["editada"] and info["ajustes"]["valores"]["light.exposure"] == 1.0
    assert [f["editada"] for f in local.get("/api/editor").json()["fotos"]] == [True, False]
    # estatisticas e numeracao nao contam a original guardada
    s = stats.obter_estatisticas_locais()
    assert sum(f["total_fotos"] for c in s for f in c["fotografos"]) == 2
    # editar de novo parte da ORIGINAL (nao acumula sobre a editada)
    previa_nova = local.get("/api/editor/0/previa", params={"aj": '{"valores": {"light.exposure": 1.0}}', "lado": 400})
    assert previa_nova.status_code == 200
    assert local.post("/api/editor/0/restaurar").json() == {"ok": True}
    assert open(fotos[0], "rb").read() == original and not os.path.exists(guardada)
    assert not local.get("/api/editor/0").json()["editada"]


@motor
def test_salvar_sem_ajuste_nao_regrava():
    fotos = descarregar(1)
    antes = os.stat(fotos[0]).st_mtime_ns, open(fotos[0], "rb").read()
    local.post("/api/editor/0/salvar", json={"ajustes": editor.ajustes_padrao()})
    esperar_salvar()
    assert (os.stat(fotos[0]).st_mtime_ns, open(fotos[0], "rb").read()) == antes
    assert not os.path.exists(os.path.join(os.path.dirname(fotos[0]), ".originais"))


@motor
def test_balanco_de_branco_e_conta_gotas():
    descarregar(1)
    cf = local.get("/api/editor/0").json()["como_fotografado"]
    assert cf == {"temp": 6500, "tint": 0}                  # JPEG: referencia neutra
    auto = local.post("/api/editor/0/balanco", json={"modo": "auto"}).json()
    assert auto["modo"] == "auto" and 2000 <= auto["temp"] <= 50000
    pick = local.post("/api/editor/0/balanco", json={"x": 0.1, "y": 0.9}).json()
    assert pick["modo"] == "custom"
    # Tungstenio deixa a foto mais azul de verdade (nao so o numero na tela)
    tung = local.post("/api/editor/0/balanco", json={"modo": "tungsten"}).json()
    def cor(wb):
        r = local.get("/api/editor/0/previa", params={"aj": json.dumps({"wb": wb}), "lado": 300})
        return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), float).mean((0, 1))
    normal, azul = cor({"modo": "asShot"}), cor({"modo": "tungsten", "temp": tung["temp"], "tint": tung["tint"]})
    assert azul[2] - azul[0] > normal[2] - normal[0] + 20


@motor
def test_envio_ao_drive_espera_salvar(monkeypatch):
    descarregar(1)
    monkeypatch.setattr(editor, "pendentes", lambda: 1)
    r = local.post("/api/upload/iniciar", json={"link": ""})
    assert r.status_code == 400 and "salvando" in r.json()["detail"]


@motor
def test_descartar_foto_editada_apaga_a_original_guardada():
    fotos = descarregar(2)
    local.post("/api/editor/1/salvar", json={"ajustes": {"valores": {"light.contrast": 40}}})
    esperar_salvar()
    guardada = os.path.join(os.path.dirname(fotos[1]), ".originais", os.path.basename(fotos[1]))
    assert os.path.exists(guardada)
    r = local.post("/api/revisor/finalizar", json={"descartar": [1]}).json()
    assert r["apagadas"] == 1 and not os.path.exists(guardada) and not os.path.exists(fotos[1])


@motor
def test_editar_raw_vira_jpeg_e_o_raw_fica_guardado(tmp_path):
    # RAW de verdade: o LightCraft gera DNGs de teste (lidos pelo conteudo, entao servem como .arw)
    import subprocess
    subprocess.run([raw.localizar_cli(), "synth-merge", "hdr", "-o", str(tmp_path / "s")], check=True, capture_output=True)
    pasta = tmp_path / "Ana"
    pasta.mkdir()
    foto = pasta / "Ana_001.arw"
    foto.write_bytes((tmp_path / "s" / "bracket-1.dng").read_bytes())
    original = foto.read_bytes()
    E.arquivos_transferidos = [str(foto)]
    assert brilho(local.get("/api/editor/0/previa", params={"aj": "{}", "lado": 400}).content) > 0   # previa do RAW
    editada = editor.salvar_agora(str(foto), {"valores": {"light.exposure": 0.5}})
    assert editada == str(pasta / "Ana_001.jpg") and E.arquivos_transferidos == [editada]
    assert Image.open(editada).format == "JPEG" and not foto.exists()
    assert (pasta / ".originais" / "Ana_001.arw").read_bytes() == original
    # editar de novo continua revelando a partir do RAW
    assert editor.original_de(editada) == str(pasta / ".originais" / "Ana_001.arw")
    assert editor.salvar_agora(editada, {"valores": {"light.exposure": -0.5}}) == editada
    assert editor.restaurar(editada) == str(foto) and foto.read_bytes() == original
    assert not (pasta / "Ana_001.jpg").exists() and E.arquivos_transferidos == [str(foto)]


# ---------- curva de pontos, copiar/colar, predefinicoes, zoom ----------

def test_curva_de_pontos_validada():
    aj = editor.limpar({"curva": {"master": [[1.2, 1], [0, -1], [0.5, 0.7], [0.5, 0.6]], "red": [[0, 0], [1, 1]],
                                  "hack": [[0, 1]]}})
    assert aj["curva"] == {"master": [[0.0, 0.0], [0.5, 0.6], [1.0, 1.0]]}          # ordenada, sem x repetido
    assert editor.e_padrao({"curva": {"master": [[0, 0], [0.5, 0.5], [1, 1]]}})      # linha reta = sem curva
    assert editor.para_lightcraft({"curva": {"blue": [[0, 0], [0.5, 0.4], [1, 1]]}})["curve"]["blue"] == \
        [[0.0, 0.0], [0.5, 0.4], [1.0, 1.0]]


def test_colar_so_os_grupos_escolhidos():
    base = {"valores": {"light.exposure": 1, "color.saturation": 10, "curve.darks": 5}, "wb": {"modo": "auto", "temp": 5000, "tint": 3}}
    copia = {"valores": {"light.exposure": -1, "color.saturation": 50, "curve.darks": -20}, "wb": {"modo": "asShot"},
             "curva": {"master": [[0, 0], [0.5, 0.6], [1, 1]]}}
    so_luz = editor.mesclar(base, copia, ["luz"])
    assert so_luz["valores"]["light.exposure"] == -1 and so_luz["valores"]["color.saturation"] == 10
    assert so_luz["wb"]["modo"] == "auto" and so_luz["curva"] == {}
    tudo = editor.mesclar(base, copia, ["luz", "curva", "cor"])
    assert tudo["wb"] == {"modo": "asShot"} and tudo["curva"]["master"][1] == [0.5, 0.6]
    assert tudo["valores"]["curve.darks"] == -20


def test_predefinicoes_com_nome():
    for p in editor.predefinicoes():
        editor.excluir_predefinicao(p["nome"])
    r = local.post("/api/editor-predefinicoes", json={"nome": "Louvor palco", "ajustes": {"valores": {"light.exposure": 0.7}}})
    assert [p["nome"] for p in r.json()["predefinicoes"]] == ["Louvor palco"]
    local.post("/api/editor-predefinicoes", json={"nome": "louvor PALCO", "ajustes": {"valores": {"light.exposure": 0.3}}})
    lista = local.get("/api/editor-predefinicoes").json()
    assert len(lista["predefinicoes"]) == 1 and lista["predefinicoes"][0]["ajustes"]["valores"]["light.exposure"] == 0.3
    assert local.post("/api/editor-predefinicoes", json={"nome": "  "}).status_code == 400
    assert local.delete("/api/editor-predefinicoes", params={"nome": "louvor PALCO"}).json()["predefinicoes"] == []


@motor
def test_curvas_prontas_do_lightcraft():
    nomes = [c["nome"] for c in local.get("/api/editor-predefinicoes").json()["curvas"]]
    assert nomes[:3] == ["Linear", "Contraste médio", "Contraste forte"]


@motor
def test_curva_de_pontos_muda_a_foto():
    descarregar(1)
    def media(aj):
        r = local.get("/api/editor/0/previa", params={"aj": json.dumps(aj), "lado": 300})
        return np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"), float).mean((0, 1))
    normal = media({})
    assert media({"curva": {"master": [[0, 0], [0.5, 0.75], [1, 1]]}}).mean() > normal.mean() + 15   # clareia
    vermelho = media({"curva": {"red": [[0, 0], [0.5, 0.75], [1, 1]]}})
    assert vermelho[0] > normal[0] + 15 and abs(vermelho[2] - normal[2]) < 5


@motor
def test_colar_em_varias_fotos():
    fotos = descarregar(3)
    copia = {"valores": {"light.exposure": 0.8, "color.saturation": 25}, "wb": {"modo": "asShot"}}
    r = local.post("/api/editor/aplicar", json={"indices": [1, 2], "ajustes": copia, "grupos": ["luz"]})
    assert r.json() == {"ok": True, "fotos": 2}
    esperar_salvar()
    info = local.get("/api/editor").json()["fotos"]
    assert [f["editada"] for f in info] == [False, True, True]
    aj = local.get("/api/editor/2").json()["ajustes"]["valores"]
    assert aj["light.exposure"] == 0.8 and aj["color.saturation"] == 0          # so o grupo Luz foi colado
    assert os.path.exists(os.path.join(os.path.dirname(fotos[1]), ".originais", os.path.basename(fotos[1])))


@motor
def test_zoom_do_editor_revela_em_tamanho_cheio():
    descarregar(1)
    r = local.get("/api/editor/0/previa", params={"aj": '{"valores": {"light.exposure": 0.5}}', "lado": 0})
    assert r.status_code == 200 and Image.open(io.BytesIO(r.content)).size == (1800, 1200)
