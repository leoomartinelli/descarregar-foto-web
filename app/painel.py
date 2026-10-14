"""Painel de acompanhamento em tempo real (aberto pelo QR code): status de cada PC, quem esta descarregando,
quem ja descarregou (e quantas fotos) e quem ainda falta.

Cada estacao guarda a propria atividade em E.atividade e responde em /atividade (rede local). O lider junta a dele
com a dos auxiliares registrados em /painel/dados."""
import concurrent.futures
import ipaddress
import os
import platform
import socket
import threading
import time

import psutil
import requests

from . import core
from .core import E
from .versao import VERSAO

TIMEOUT_AUX = 1.5
_cache = {"t": 0.0, "dados": None}
_lock_cache = threading.Lock()


# ---------- atividade desta estacao ----------

def ocupar(voluntario=None):
    """O voluntario comecou: escolheu as fotos do cartao (o tempo conta a partir daqui)."""
    if E.atividade.get("estado") != "ocupado":
        E.atividade = {"estado": "ocupado", "fase": "selecionando", "voluntario": None, "inicio_ts": time.time()}
    if voluntario and voluntario.strip():
        E.atividade["voluntario"] = voluntario.strip()


def copiando(voluntario):
    ocupar(voluntario)
    E.atividade["fase"] = "copiando"


def concluido():
    if E.atividade.get("estado") == "ocupado":
        E.atividade["fase"] = "concluido"


def erro_copia():
    if E.atividade.get("estado") == "ocupado":
        E.atividade["fase"] = "selecionando"


def liberar():
    E.atividade = {"estado": "livre"}


def resumo_descarregamentos():
    """[{voluntario, categoria, fotos, vezes, ultimo}] do Servir ativo, lido do .descarregamentos.json
    (leve: nao abre as fotos, pode ser chamado a cada poucos segundos)."""
    if not E.active_servir:
        return []
    saida = []
    for chave, reg in core.carregar_descarregamentos(core.raiz_servir(E.active_servir)).items():
        partes = [p for p in chave.split("/") if p]
        if not partes or not reg.get("fotos"):
            continue
        eventos = reg.get("eventos") or []
        saida.append({"voluntario": partes[-1], "categoria": core.sem_data(partes[0]) if len(partes) > 1 else None,
                      "fotos": int(reg.get("fotos", 0)), "vezes": len(eventos) or 1,
                      "ultimo": max((e.get("data_hora", "") for e in eventos), default="")})
    return saida


def atividade_local():
    """O que esta estacao responde em /atividade."""
    a = {k: v for k, v in E.atividade.items() if k != "inicio_ts"}
    if a.get("estado") == "ocupado":
        a["segundos"] = round(time.time() - E.atividade.get("inicio_ts", time.time()), 1)
        if a.get("fase") == "copiando":
            a["feitos"], a["total"] = E.transfer.get("feitos", 0), E.transfer.get("total", 0)
    return {"nome": platform.node() or "Estação", "versao": VERSAO, "servir_id": (E.active_servir or {}).get("id"),
            "atividade": a, "descarregados": resumo_descarregamentos(), "uploads": uploads_locais()}


_CAMPOS_UPLOAD = ("id", "fotografo", "total", "feitos", "progresso", "erros", "estado", "destino", "msg", "atuais",
                  "servir_id")


def uploads_locais():
    """Envios ao Drive desta estacao (o mesmo que aparece no quadro de envios da tela)."""
    return [{k: (list(j.get(k) or []) if k == "atuais" else j.get(k)) for k in _CAMPOS_UPLOAD} for j in list(E.uploads)]


# ---------- endereco do painel (QR code) ----------

# interfaces virtuais (Docker, VMs, VPN): os celulares da rede local nao chegam por elas
_VIRTUAIS = ("docker", "br-", "veth", "virbr", "vmnet", "vboxnet", "tun", "tap", "wg", "zt", "tailscale", "utun",
             "vEthernet", "VirtualBox", "VMware", "Hyper-V")


def ips_locais():
    """IPv4 desta maquina alcancaveis na rede local; o da rota principal primeiro."""
    ips = []
    status = psutil.net_if_stats()
    for nome, addrs in psutil.net_if_addrs().items():
        if nome.startswith(_VIRTUAIS) or any(v in nome for v in _VIRTUAIS[-4:]) or \
                (nome in status and not status[nome].isup):
            continue
        for a in addrs:
            if a.family != socket.AF_INET:
                continue
            try:
                ip = ipaddress.ip_address(a.address)
            except ValueError:
                continue
            if not (ip.is_loopback or ip.is_link_local) and a.address not in ips:
                ips.append(a.address)
    principal = core.obter_ip_local()
    if principal in ips:
        ips.remove(principal)
        ips.insert(0, principal)
    return ips or [principal]


def url_painel(ip):
    return f"http://{ip}:{E.local_port}/painel"


def qr_svg(texto):
    import segno  # dependencia leve (pure Python); importada aqui para o resto funcionar mesmo sem ela
    import io
    buf = io.BytesIO()
    segno.make(texto, error="m").save(buf, kind="svg", scale=8, border=2, dark="#000", light="#fff")
    return buf.getvalue()


# ---------- dados do painel (lider) ----------

def _consultar_auxiliar(ip, info):
    est = {"nome": info.get("nome") or ip, "ip": ip, "papel": "auxiliar", "online": False, "atividade": None,
           "descarregados": [], "uploads": [], "versao": info.get("versao")}
    try:
        r = requests.get(f"http://{ip}:{info.get('port', 50007)}/atividade", timeout=TIMEOUT_AUX)
    except Exception:
        return est
    est["online"] = True
    if r.status_code == 200:
        d = r.json()
        est["atividade"] = d.get("atividade")
        est["versao"] = d.get("versao") or est["versao"]
        # descarregamentos de outro Servir (auxiliar ainda nao sincronizou o atual) nao entram na conta
        if d.get("servir_id") == (E.active_servir or {}).get("id"):
            est["descarregados"] = d.get("descarregados") or []
        est["uploads"] = d.get("uploads") or []
    else:
        est["sem_suporte"] = True   # app desktop ou versao antiga: esta conectado, mas nao informa o status
    return est


def _montar():
    servir = E.active_servir
    if E.network_mode != "lider":
        return {"modo": "auxiliar", "lider": E.lider_detectado}
    if not servir:
        return {"modo": "lider", "servir": None}
    local = atividade_local()
    estacoes = [{"nome": local["nome"], "ip": core.obter_ip_local(), "papel": "lider", "online": True,
                 "versao": VERSAO,
                 "atividade": local["atividade"], "descarregados": local["descarregados"],
                 "uploads": local["uploads"]}]
    aux = list(E.auxiliar_stations.items())
    if aux:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(aux))) as ex:
            estacoes += list(ex.map(lambda x: _consultar_auxiliar(*x), aux))

    agora, vols, uploads = [], {}, []
    for est in estacoes:
        for j in est["uploads"]:
            # so os envios deste Servir (jobs antigos, sem servir_id, tambem aparecem)
            if j.get("servir_id") in (None, servir.get("id")):
                uploads.append({**j, "estacao": est["nome"], "papel": est["papel"]})
        a = est.get("atividade") or {}
        if a.get("estado") == "ocupado":
            agora.append({"estacao": est["nome"], "papel": est["papel"], "voluntario": a.get("voluntario"),
                          "fase": a.get("fase"), "segundos": a.get("segundos", 0),
                          "feitos": a.get("feitos"), "total": a.get("total")})
        for d in est["descarregados"]:
            v = vols.setdefault(d["voluntario"].strip().lower(), {
                "voluntario": d["voluntario"], "fotos": 0, "vezes": 0, "categorias": {}, "estacoes": [], "ultimo": ""})
            v["fotos"] += d["fotos"]
            v["vezes"] += d.get("vezes", 1)
            if d.get("categoria"):
                v["categorias"][d["categoria"]] = v["categorias"].get(d["categoria"], 0) + d["fotos"]
            if est["nome"] not in v["estacoes"]:
                v["estacoes"].append(est["nome"])
            v["ultimo"] = max(v["ultimo"], d.get("ultimo") or "")

    # nome do voluntario como esta cadastrado no Servir (a pasta pode ter outra caixa)
    cadastro = {n.strip().lower(): n for n in servir.get("voluntarios", [])}
    for k, v in vols.items():
        v["voluntario"] = cadastro.get(k, v["voluntario"])
    ja = sorted(vols.values(), key=lambda v: (-v["fotos"], v["voluntario"].lower()))
    ocupados_agora = {(x["voluntario"] or "").strip().lower() for x in agora}
    faltam = [{"voluntario": n, "descarregando_agora": n.strip().lower() in ocupados_agora}
              for n in servir.get("voluntarios", []) if n.strip().lower() not in vols]

    online = [e for e in estacoes if e["online"]]
    ocupadas = [e for e in online if (e.get("atividade") or {}).get("estado") == "ocupado"]
    livres = [e for e in online if (e.get("atividade") or {}).get("estado") == "livre"]
    return {
        "modo": "lider",
        "servir": {"id": servir.get("id"), "nome": servir.get("nome"), "data": servir.get("data_criacao")},
        "estacoes": [{k: e.get(k) for k in ("nome", "ip", "papel", "online", "atividade", "sem_suporte", "versao")}
                     for e in estacoes],
        # PCs com versao diferente da do lider (ou que nao informam a versao): podem nao se entender direito
        "versao_lider": VERSAO,
        "versoes_diferentes": [e["nome"] for e in estacoes if e["online"] and e.get("versao") != VERSAO],
        "agora": agora, "ja_descarregaram": ja, "faltam": faltam, "uploads": uploads,
        "gerais": {"total_fotos": sum(v["fotos"] for v in ja), "descarregamentos": sum(v["vezes"] for v in ja),
                   "voluntarios": len(servir.get("voluntarios", [])), "ja_descarregaram": len(ja),
                   "faltam": len(faltam), "pcs": len(estacoes), "pcs_livres": len(livres),
                   "pcs_ocupados": len(ocupadas), "pcs_offline": len(estacoes) - len(online)},
        "atualizado": time.strftime("%H:%M:%S"),
    }


def dados_painel():
    """Varios celulares atualizam o painel ao mesmo tempo: reaproveita o resultado por 1 segundo."""
    with _lock_cache:
        if _cache["dados"] is None or time.time() - _cache["t"] > 1.0:
            _cache.update(dados=_montar(), t=time.time())
        return _cache["dados"]


def limpar_cache():
    _cache["dados"] = None


PAGINA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "painel.html")
