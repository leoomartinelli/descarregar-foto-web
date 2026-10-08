"""Estatisticas por categoria/fotografo (camera e lente via EXIF) e mescla com auxiliares."""
import os

from PIL import Image
from PIL.ExifTags import TAGS

from . import core
from .core import E


def extrair_camera_e_lente(caminho):
    camera = lente = "Desconhecida"
    if caminho.lower().endswith(('.mp4', '.mov', '.avi', '.wav')):
        return camera, lente
    try:
        with Image.open(caminho) as img:
            exif = img.getexif()
            if not exif:
                return camera, lente
            make, model = exif.get(271), exif.get(272)
            if model:
                model = str(model).strip()
                camera = f"{str(make).strip()} {model}" if make and str(make).strip() not in model else model
            elif make:
                camera = str(make).strip()
            try:
                ifd = exif.get_ifd(34665)
                lmake, lmodel = ifd.get(42035), ifd.get(42036)
                if lmodel:
                    lmodel = str(lmodel).strip()
                    lente = f"{str(lmake).strip()} {lmodel}" if lmake and str(lmake).strip() not in lmodel else lmodel
                elif lmake:
                    lente = str(lmake).strip()
            except Exception:
                pass
            if lente == "Desconhecida":
                for tag_id, val in exif.items():
                    if TAGS.get(tag_id, tag_id) in ('LensModel', 'LensName'):
                        lente = str(val).strip()
                        break
    except Exception:
        pass
    return camera, lente


def obter_estatisticas_locais():
    if not E.active_servir:
        return []
    raiz = os.path.join(E.destino_base, E.active_servir.get('nome'))
    categorias = {}
    if not os.path.isdir(raiz):
        return []
    for cat in os.listdir(raiz):
        cat_dir = os.path.join(raiz, cat)
        if not os.path.isdir(cat_dir):
            continue
        # a pasta no disco tem a data ('Voltz 2026-10-08'); o nome da categoria enviado e so 'Voltz'.
        # Dias diferentes do mesmo Servir caem na mesma categoria.
        destino_cat = categorias.setdefault(core.sem_data(cat), [])
        for fotog in os.listdir(cat_dir):
            fdir = os.path.join(cat_dir, fotog)
            if not os.path.isdir(fdir):
                continue
            total, cams, lentes = 0, set(), set()
            for root, _, files in os.walk(fdir):
                for nome in files:
                    if nome.lower().endswith(core.EXT_TODAS):
                        total += 1
                        if nome.lower().endswith(core.EXT_IMG):
                            cam, len_ = extrair_camera_e_lente(os.path.join(root, nome))
                            if cam != "Desconhecida":
                                cams.add(cam)
                            if len_ != "Desconhecida":
                                lentes.add(len_)
            destino_cat.append({"nome_fotografo": fotog, "total_fotos": total,
                                    "cameras": list(cams), "lentes": list(lentes)})
    return [{"nome": n, "fotografos": f} for n, f in categorias.items()]


def mesclar_estatisticas(stats_lider, stats_auxiliares):
    mapa = {}

    def somar(lista):
        for cat in lista:
            nome = cat.get("nome")
            if not nome:
                continue
            m = mapa.setdefault(nome, {})
            for f in cat.get("fotografos", []):
                fn = f.get("nome_fotografo")
                if not fn:
                    continue
                d = m.setdefault(fn, {"total_fotos": 0, "cameras": set(), "lentes": set()})
                d["total_fotos"] += f.get("total_fotos", 0)
                d["cameras"].update(f.get("cameras", []))
                d["lentes"].update(f.get("lentes", []))

    somar(stats_lider)
    for sa in stats_auxiliares:
        somar(sa)
    return [{"nome": cn, "fotografos": [
        {"nome_fotografo": n, "total_fotos": d["total_fotos"],
         "cameras": list(d["cameras"]), "lentes": list(d["lentes"])} for n, d in fm.items()]}
        for cn, fm in mapa.items()]
