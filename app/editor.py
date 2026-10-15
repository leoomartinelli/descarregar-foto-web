"""Edicao de fotos (Luz, Curva e Cor) com o motor do LightCraft (lightcraft-cli, o mesmo da conversao de RAW).

- Previa ao vivo: o lightcraft-cli revela uma copia reduzida da foto (JPEG) ou o proprio RAW com os ajustes; o que
  aparece na tela e o mesmo motor da foto final.
- Salvar: revela a foto em tamanho cheio no lugar dela (RAW vira JPEG). A original vai para a pasta oculta
  `.originais` ao lado, com os ajustes em `<foto editada>.ajustes.json`: da para continuar editando ou restaurar.
- Os salvamentos rodam em segundo plano, um por vez; o envio ao Drive espera terminarem.
Foto sem nenhum ajuste nunca e regravada."""
import hashlib
import json
import os
import queue
import subprocess
import tempfile
import threading

from PIL import Image

from . import core, raw
from .core import E

PASTA_ORIGINAIS = ".originais"
QUALIDADE = 92
LADO_COPIA = 2048            # copia reduzida usada nas previas de JPEG (previa em ~0,2 s)
TEMPO_MAXIMO = 300

# id do LightCraft: (secao, rotulo, minimo, maximo, padrao, passo). Rotulos como no Lightroom em portugues.
CONTROLES = {
    "light.exposure": ("luz", "Exposição", -5.0, 5.0, 0.0, 0.01),
    "light.contrast": ("luz", "Contraste", -100, 100, 0, 1),
    "light.highlights": ("luz", "Realces", -100, 100, 0, 1),
    "light.shadows": ("luz", "Sombras", -100, 100, 0, 1),
    "light.whites": ("luz", "Brancos", -100, 100, 0, 1),
    "light.blacks": ("luz", "Pretos", -100, 100, 0, 1),
    "curve.highlights": ("curva", "Realces", -100, 100, 0, 1),
    "curve.lights": ("curva", "Claros", -100, 100, 0, 1),
    "curve.darks": ("curva", "Escuros", -100, 100, 0, 1),
    "curve.shadows": ("curva", "Sombras", -100, 100, 0, 1),
    "wb.temp": ("cor", "Temperatura", 2000, 50000, None, 50),
    "wb.tint": ("cor", "Matiz", -150, 150, None, 1),
    "color.vibrance": ("cor", "Vibratilidade", -100, 100, 0, 1),
    "color.saturation": ("cor", "Saturação", -100, 100, 0, 1),
}
MODOS_WB = {"asShot": "Como fotografado", "auto": "Automático", "daylight": "Luz do dia", "cloudy": "Nublado",
            "shade": "Sombra", "tungsten": "Tungstênio", "fluorescent": "Fluorescente", "flash": "Flash",
            "custom": "Personalizado"}

_lock_render = threading.Semaphore(2)     # previas: no maximo duas ao mesmo tempo
_lock_cache = threading.Lock()
_como_fotografado = {}                    # original -> {"temp", "tint"}
_fila = queue.Queue()
SALVANDO = {}                             # caminho atual da foto -> "salvando" | "erro: ..."
_worker = None


# ---------- ajustes ----------

CANAIS_CURVA = ("master", "red", "green", "blue")     # curva de pontos: RGB e cada cor
GRUPOS = {"luz": "Luz", "curva": "Curva de tons", "cor": "Cor (inclui equilíbrio de branco)"}   # para copiar/colar


def ajustes_padrao():
    return {"valores": {c: v[4] for c, v in CONTROLES.items() if v[4] is not None}, "wb": {"modo": "asShot"},
            "curva": {}}


def _pontos(pts):
    """Pontos da curva (0..1), ordenados por x, sem x repetido; linha reta (sem efeito) vira lista vazia."""
    saida = {}
    for p in (pts or [])[:16]:
        try:
            x, y = min(1.0, max(0.0, float(p[0]))), min(1.0, max(0.0, float(p[1])))
        except (TypeError, ValueError, IndexError):
            continue
        saida[round(x, 4)] = round(y, 4)
    pts = sorted(saida.items())
    if len(pts) < 2 or all(abs(x - y) < 1e-4 for x, y in pts):
        return []
    return [list(p) for p in pts]


def limpar(aj):
    """Ajustes vindos da tela: so os controles conhecidos, dentro da faixa."""
    aj = aj or {}
    valores = {}
    for c, v in (aj.get("valores") or {}).items():
        if c in CONTROLES and c not in ("wb.temp", "wb.tint"):
            _, _, mn, mx, _, _ = CONTROLES[c]
            valores[c] = min(mx, max(mn, float(v)))
    wb = aj.get("wb") or {}
    modo = wb.get("modo") if wb.get("modo") in MODOS_WB else "asShot"
    curva = {c: _pontos((aj.get("curva") or {}).get(c)) for c in CANAIS_CURVA}
    saida = {"valores": valores, "wb": {"modo": modo}, "curva": {c: p for c, p in curva.items() if p}}
    # os modos prontos (Tungstenio, Nublado...) tambem levam temperatura e matiz: o LightCraft revela pelos numeros,
    # o modo e so o nome. "Como fotografado" usa os da propria foto.
    if modo != "asShot" and wb.get("temp") is not None:
        saida["wb"]["temp"] = min(50000.0, max(2000.0, float(wb["temp"])))
        saida["wb"]["tint"] = min(150.0, max(-150.0, float(wb.get("tint") or 0)))
    elif modo == "custom":
        saida["wb"].update(temp=5500.0, tint=0.0)
    return saida


def e_padrao(aj):
    aj = limpar(aj)
    return aj["wb"]["modo"] == "asShot" and not aj["curva"] and \
        all(abs(v - CONTROLES[c][4]) < 1e-9 for c, v in aj["valores"].items())


def para_lightcraft(aj):
    """Ajustes -> JSON parcial de DevelopSettings do LightCraft (render --settings)."""
    aj = limpar(aj)
    s = {"light": {}, "curve": {}, "color": {}}
    for c, v in aj["valores"].items():
        secao, campo = c.split(".")
        s[secao][campo] = v
    s["curve"].update(aj["curva"])                      # curva de pontos: {"master": [[x, y], ...], ...}
    s["wb"] = {"mode": aj["wb"]["modo"]}
    if "temp" in aj["wb"]:
        s["wb"].update(temp=aj["wb"]["temp"], tint=aj["wb"]["tint"])
    return s


# ---------- onde ficam a original e os ajustes ----------

def _pasta_originais(foto):
    return os.path.join(os.path.dirname(foto), PASTA_ORIGINAIS)


def _arquivo_ajustes(foto):
    return os.path.join(_pasta_originais(foto), os.path.basename(foto) + ".ajustes.json")


def registro(foto):
    """{"original": nome, "ajustes": {...}} se a foto foi editada; senao None."""
    try:
        with open(_arquivo_ajustes(foto), encoding="utf-8") as f:
            d = json.load(f)
        if os.path.isfile(os.path.join(_pasta_originais(foto), d["original"])):
            return d
    except (OSError, ValueError, KeyError):
        pass
    return None


def original_de(foto):
    """Arquivo original (o guardado em .originais, se a foto ja foi editada)."""
    reg = registro(foto)
    return os.path.join(_pasta_originais(foto), reg["original"]) if reg else foto


def ajustes_de(foto):
    reg = registro(foto)
    return limpar(reg["ajustes"]) if reg else ajustes_padrao()


# ---------- motor (lightcraft-cli) ----------

def _cli():
    cli = raw.localizar_cli()
    if not cli:
        raise RuntimeError("O motor de edição (lightcraft-cli) não está disponível neste computador.")
    return cli


def _rodar(args, entrada=None):
    r = subprocess.run([_cli(), *args], input=entrada, capture_output=True, text=True, timeout=TEMPO_MAXIMO,
                       **core.SEM_JANELA)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "").strip()[-300:] or f"lightcraft-cli: código {r.returncode}")
    return r.stdout


def _render(origem, destino, aj, lado=None, qualidade=QUALIDADE):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(para_lightcraft(aj), f)
        arq = f.name
    try:
        args = ["render", origem, "-o", destino, "--quality", str(qualidade), "--settings", arq]
        if lado:
            args += ["--size", str(int(lado))]
        _rodar(args)
    finally:
        os.remove(arq)


def _comandos(origem, comandos):
    """Roda comandos do LightCraft na foto e devolve o resultado de cada um."""
    script = "\n".join(json.dumps({"command": c, "params": p}) for c, p in comandos)
    saida = []
    for linha in _rodar(["run", "--import", origem, "--script", "-"], entrada=script).splitlines():
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        if not d.get("ok"):
            raise RuntimeError(f"{d.get('command')}: {d.get('error')}")
        saida.append(d.get("result"))
    return saida


def _copia_reduzida(origem):
    """Previas de JPEG saem de uma copia de 2048 px (rapida); RAW e revelado direto (precisa do arquivo RAW)."""
    if origem.lower().endswith(core.EXT_RAW):
        return origem
    chave = hashlib.sha1(f"{origem}|{os.path.getmtime(origem)}".encode()).hexdigest()
    pasta = os.path.join(core.DATA_DIR, "cache_editor")
    destino = os.path.join(pasta, chave + ".jpg")
    with _lock_cache:
        if not os.path.exists(destino):
            os.makedirs(pasta, exist_ok=True)
            with Image.open(origem) as im:
                exif = im.getexif()
                im = im.convert("RGB")
                im.thumbnail((LADO_COPIA, LADO_COPIA))
                im.save(destino + ".tmp", "JPEG", quality=95, exif=exif)   # mantem a rotacao (EXIF)
            os.replace(destino + ".tmp", destino)
    return destino


def como_fotografado(foto):
    """Temperatura e matiz originais da foto (o "Como fotografado" do balanco de branco)."""
    origem = original_de(foto)
    if origem not in _como_fotografado:
        wb = _comandos(origem, [("develop.get", {})])[-1]["wb"]
        _como_fotografado[origem] = {"temp": round(wb["temp"]), "tint": round(wb["tint"])}
    return _como_fotografado[origem]


def balanco(foto, modo=None, x=None, y=None, aj=None):
    """Temperatura/matiz de um modo do balanco de branco, ou do conta-gotas no ponto (x, y) de 0 a 1."""
    origem = _copia_reduzida(original_de(foto))
    cmds = [("develop.merge", {"settings": para_lightcraft(aj)})]
    if x is not None:
        cmds.append(("develop.wbPick", {"x": min(1.0, max(0.0, float(x))), "y": min(1.0, max(0.0, float(y)))}))
    else:
        cmds.append(("develop.wb", {"mode": modo if modo in MODOS_WB else "asShot"}))
    wb = _comandos(origem, cmds + [("develop.get", {})])[-1]["wb"]
    return {"modo": wb["mode"], "temp": round(wb["temp"]), "tint": round(wb["tint"])}


def previa(foto, aj, lado=1400):
    """lado=0: tamanho cheio a partir da original (zoom do editor, ~1 s); senao da copia reduzida (~0,2 s)."""
    if int(lado) == 0:
        origem, lado = original_de(foto), None
    else:
        lado = max(200, min(int(lado), LADO_COPIA))
        origem = _copia_reduzida(original_de(foto))
    with _lock_render:
        fd, saida = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            _render(origem, saida, aj, lado=lado, qualidade=85 if lado else 90)
            with open(saida, "rb") as f:
                return f.read()
        finally:
            os.remove(saida)


# ---------- copiar/colar e predefinicoes ----------

def _grupo(controle):
    return "cor" if controle.startswith(("wb.", "color.")) else "curva" if controle.startswith("curve.") else "luz"


def mesclar(base, copiados, grupos):
    """Ajustes de `base` com os grupos escolhidos (luz, curva, cor) trocados pelos de `copiados`."""
    base, copiados = limpar(base), limpar(copiados)
    grupos = set(grupos or GRUPOS)
    novo = {"valores": {c: v for c, v in base["valores"].items() if _grupo(c) not in grupos},
            "wb": base["wb"], "curva": {} if "curva" in grupos else base["curva"]}
    novo["valores"].update({c: v for c, v in copiados["valores"].items() if _grupo(c) in grupos})
    if "cor" in grupos:
        novo["wb"] = copiados["wb"]
    if "curva" in grupos:
        novo["curva"] = copiados["curva"]
    return limpar(novo)


def aplicar_em(fotos, copiados, grupos):
    """Cola os ajustes em varias fotos (cada uma mantem o que nao foi copiado) e salva em segundo plano."""
    for foto in fotos:
        salvar(foto, mesclar(ajustes_de(foto), copiados, grupos))


ARQ_PREDEFINICOES = os.path.join(core.DATA_DIR, "predefinicoes_edicao.json")


def predefinicoes():
    dados = core.ler_json(ARQ_PREDEFINICOES, [])
    return [{"nome": p["nome"], "ajustes": limpar(p.get("ajustes"))} for p in dados if isinstance(p, dict) and p.get("nome")]


def salvar_predefinicao(nome, aj):
    nome = (nome or "").strip()[:60]
    if not nome:
        raise ValueError("Dê um nome para a predefinição.")
    lista = [p for p in predefinicoes() if p["nome"].lower() != nome.lower()]
    lista.append({"nome": nome, "ajustes": limpar(aj)})
    lista.sort(key=lambda p: p["nome"].lower())
    core.gravar_json(ARQ_PREDEFINICOES, lista)
    return lista


def excluir_predefinicao(nome):
    lista = [p for p in predefinicoes() if p["nome"] != nome]
    core.gravar_json(ARQ_PREDEFINICOES, lista)
    return lista


def curvas_prontas():
    """Curvas de pontos que vem com o LightCraft (Linear, Contraste medio, Contraste forte)."""
    global _curvas
    if _curvas is None:
        nomes = {"Linear": "Linear", "Medium Contrast": "Contraste médio", "Strong Contrast": "Contraste forte"}
        try:
            r = _rodar(["run", "--demo", "curve.presets"]).splitlines()[0]
            lista = json.loads(r)["result"]["presets"]
            _curvas = [{"nome": nomes.get(p["name"], p["name"]), "curva": {c: _pontos(p.get(c)) for c in CANAIS_CURVA}}
                       for p in lista if p.get("builtin")]
        except Exception as e:
            print(f"Curvas prontas do LightCraft indisponiveis: {e}")
            return [{"nome": "Linear", "curva": {}}]
    return _curvas


_curvas = None


# ---------- salvar / restaurar ----------

def _jpeg_ok(caminho):
    try:
        with Image.open(caminho) as im:
            im.verify()
        return os.path.getsize(caminho) > 0
    except Exception:
        return False


def _trocar_na_lista(antigo, novo):
    E.arquivos_transferidos = [novo if p == antigo else p for p in E.arquivos_transferidos]


def _desmarcar_envio(foto):
    """Foto editada depois de enviada: pode ser enviada de novo (com a edicao)."""
    if E.active_servir:
        core.desmarcar_enviado(core.raiz_servir(E.active_servir), foto)


def salvar_agora(foto, aj):
    """Revela a foto em tamanho cheio com os ajustes. Retorna o caminho da foto editada (RAW vira .jpg)."""
    aj = limpar(aj)
    if e_padrao(aj):
        return restaurar(foto)
    origem = original_de(foto)
    pasta = os.path.dirname(foto)
    editada = os.path.join(pasta, os.path.splitext(os.path.basename(origem))[0] + ".jpg")
    if editada != foto and os.path.exists(editada):       # RAW + JPEG com o mesmo nome: nao sobrescreve
        editada = os.path.join(pasta, os.path.splitext(os.path.basename(origem))[0] + "_editada.jpg")
    temporario = editada + ".editando.jpg"
    try:
        _render(origem, temporario, aj)                   # primeiro revela: se falhar, nada foi mexido
        if not _jpeg_ok(temporario):
            raise RuntimeError("o arquivo editado saiu inválido")
        st = os.stat(origem)
        os.utime(temporario, (st.st_atime, st.st_mtime))  # a ordem das fotos e pela data
        if origem == foto:                                # primeira edicao: guarda a original
            os.makedirs(_pasta_originais(foto), exist_ok=True)
            guardada = os.path.join(_pasta_originais(foto), os.path.basename(foto))
            os.replace(foto, guardada)
            origem = guardada
        elif editada != foto and os.path.exists(foto):    # nome mudou (edicao anterior com outro nome)
            os.remove(foto)
            _remover(_arquivo_ajustes(foto))
        os.replace(temporario, editada)
    except BaseException:
        _remover(temporario)
        raise
    with open(_arquivo_ajustes(editada), "w", encoding="utf-8") as f:
        json.dump({"original": os.path.basename(origem), "ajustes": aj}, f, ensure_ascii=False)
    _trocar_na_lista(foto, editada)
    _desmarcar_envio(editada)
    return editada


def restaurar(foto):
    """Volta a foto original (desfaz a edicao). Retorna o caminho da original."""
    reg = registro(foto)
    if not reg:
        return foto
    guardada = os.path.join(_pasta_originais(foto), reg["original"])
    destino = os.path.join(os.path.dirname(foto), reg["original"])
    if destino != foto:
        _remover(foto)
    os.replace(guardada, destino)
    _remover(_arquivo_ajustes(foto))
    _trocar_na_lista(foto, destino)
    _desmarcar_envio(destino)
    return destino


def apagar(foto):
    """A foto foi descartada na selecao: apaga tambem a original guardada e os ajustes."""
    reg = registro(foto)
    if reg:
        _remover(os.path.join(_pasta_originais(foto), reg["original"]))
        _remover(_arquivo_ajustes(foto))


def _remover(caminho):
    try:
        os.remove(caminho)
    except OSError:
        pass


# ---------- fila de salvamento ----------
_ultimo = {}            # foto -> ajustes mais recentes ainda nao salvos (varios pedidos da mesma foto viram um)
_renomeadas = {}        # RAW salvo vira .jpg: pedidos que ainda usam o nome antigo seguem para o novo
_lock_fila = threading.Lock()


def _atual(foto):
    while foto in _renomeadas and not os.path.exists(foto):
        foto = _renomeadas[foto]
    return foto


def salvar(foto, aj):
    """Enfileira o salvamento (a tela segue para a proxima foto na hora)."""
    global _worker
    with _lock_fila:
        foto = _atual(foto)
        SALVANDO[foto] = "salvando"
        novo = foto not in _ultimo
        _ultimo[foto] = aj
        if novo:
            _fila.put(foto)
        if not _worker or not _worker.is_alive():
            _worker = threading.Thread(target=_trabalhar, daemon=True)
            _worker.start()


def _trabalhar():
    while True:
        try:
            foto = _fila.get(timeout=5)
        except queue.Empty:
            return
        with _lock_fila:
            aj = _ultimo.pop(foto, None)
        if aj is None:
            continue
        try:
            nova = salvar_agora(_atual(foto), aj)
            with _lock_fila:
                if nova != foto:
                    _renomeadas[foto] = nova
                if foto not in _ultimo:
                    SALVANDO.pop(foto, None)
                SALVANDO.pop(nova, None)
        except Exception as e:
            print(f"Erro ao salvar edição de {os.path.basename(foto)}: {e}")
            SALVANDO[foto] = f"erro: {e}"


def pendentes():
    return sum(1 for v in SALVANDO.values() if v == "salvando")


def situacao():
    """Lista para a tela: nome, se foi editada e se esta salvando."""
    return [{"nome": os.path.basename(p), "editada": registro(p) is not None, "estado": SALVANDO.get(p, "")}
            for p in E.arquivos_transferidos]
