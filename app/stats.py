"""Estatisticas por categoria/fotografo (camera e lente via EXIF) e mescla com auxiliares."""
import os
import threading

from PIL import Image
from PIL.ExifTags import TAGS

from . import core, drive
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
    enviados = core.carregar_enviados(raiz)
    descarregamentos = core.carregar_descarregamentos(raiz)
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
            total, no_drive, cams, lentes = 0, 0, set(), set()
            for root, _, files in os.walk(fdir):
                for nome in files:
                    if nome.lower().endswith(core.EXT_TODAS):
                        total += 1
                        if core._chave_arquivo(raiz, os.path.join(root, nome)) in enviados:
                            no_drive += 1
                        if nome.lower().endswith(core.EXT_IMG):
                            cam, len_ = extrair_camera_e_lente(os.path.join(root, nome))
                            if cam != "Desconhecida":
                                cams.add(cam)
                            if len_ != "Desconhecida":
                                lentes.add(len_)
            reg = descarregamentos.get(core._chave_arquivo(raiz, fdir), {})
            destino_cat.append({"nome_fotografo": fotog, "total_fotos": total, "enviadas_drive": no_drive,
                                    "descarregadas": max(reg.get("fotos", 0), total),
                                    "segundos": reg.get("segundos", 0),
                                    "descarregamentos": reg.get("eventos", []),
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
                d = m.setdefault(fn, {"total_fotos": 0, "enviadas_drive": 0, "descarregadas": 0,
                                                "segundos": 0, "descarregamentos": [], "cameras": set(), "lentes": set()})
                d["total_fotos"] += f.get("total_fotos", 0)
                d["descarregadas"] += f.get("descarregadas", f.get("total_fotos", 0))
                d["segundos"] += f.get("segundos", 0)
                d["descarregamentos"].extend(f.get("descarregamentos", []))
                d["enviadas_drive"] += f.get("enviadas_drive", 0)
                d["cameras"].update(f.get("cameras", []))
                d["lentes"].update(f.get("lentes", []))

    somar(stats_lider)
    for sa in stats_auxiliares:
        somar(sa)
    return [{"nome": cn, "fotografos": [
        {"nome_fotografo": n, "total_fotos": d["total_fotos"], "enviadas_drive": d["enviadas_drive"],
         "descarregadas": d["descarregadas"], "segundos": d["segundos"],
         "vezes_descarregou": len(d["descarregamentos"]),
         "descarregamentos": sorted(d["descarregamentos"], key=lambda e: e.get("data_hora", "")),
         "cameras": list(d["cameras"]), "lentes": list(d["lentes"])} for n, d in fm.items()]}
        for cn, fm in mapa.items()]


def resumo_por_voluntario(categorias):
    """Soma fotos e junta cameras/lentes de todas as categorias, por fotografo (chave em minusculas)."""
    info = {}
    for cat in categorias:
        for f in cat.get("fotografos", []):
            i = info.setdefault(f["nome_fotografo"].strip().lower(), {"fotos": 0, "drive": 0, "descarregadas": 0,
                                                                    "cameras": set(), "lentes": set(), "categorias": {}})
            i["fotos"] += f.get("total_fotos", 0)
            i["descarregadas"] += f.get("descarregadas", f.get("total_fotos", 0))
            i["drive"] += f.get("enviadas_drive", 0)
            i["categorias"][cat["nome"]] = i["categorias"].get(cat["nome"], 0) + f.get("total_fotos", 0)
            i["cameras"].update(f.get("cameras", []))
            i["lentes"].update(f.get("lentes", []))
    return info


def gravar_voluntarios_servir(servir, info):
    """Atualiza o voluntarios.txt local (e o do Drive, se o Servir tiver pasta). Nunca levanta excecao."""
    try:
        core.gravar_voluntarios(os.path.join(E.destino_base, servir.get("nome")), servir.get("voluntarios", []), info)
    except Exception as e:
        print(f"Erro ao atualizar voluntarios.txt: {e}")
    if servir.get("drive_folders"):
        drive.gravar_voluntarios(servir, info)


_lock_voluntarios = threading.Lock()


def atualizar_voluntarios_em_segundo_plano():
    """Chamado ao fim de cada descarregamento: recalcula fotos/camera/lente de todos e regrava o voluntarios.txt."""
    servir = E.active_servir
    if not servir:
        return

    def tarefa():
        with _lock_voluntarios:
            gravar_voluntarios_servir(servir, resumo_por_voluntario(obter_estatisticas_locais()))
    threading.Thread(target=tarefa, daemon=True).start()
