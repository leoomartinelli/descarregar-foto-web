"""Rede local Lider/Auxiliar: broadcast UDP e sincronizacao (mesmos protocolos do app desktop).

O servidor HTTP e o proprio servidor web (porta 50007): /preset, /stats, /register e /finalize."""
import json
import platform
import socket
import threading
import time

import requests

from . import core, stats
from .core import E

UDP_PORT = 50008
_geracao = 0


def _transmitir(gen):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(1.0)
    while gen == _geracao and E.network_mode == "lider":
        if not E.active_servir:
            time.sleep(2.0)
            continue
        try:
            msg = f"SERVIR_LEADER:{core.obter_ip_local()}:{E.local_port}:" \
                  f"{E.active_servir.get('nome', 'Servir')}:{E.active_servir.get('id', '0')}"
            sock.sendto(msg.encode(), ('<broadcast>', UDP_PORT))
        except Exception as e:
            print(f"Erro no broadcast UDP: {e}")
        time.sleep(3.0)
    sock.close()


def _escutar(gen):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass
    try:
        sock.bind(('', UDP_PORT))
    except Exception as e:
        print(f"Erro ao bindar porta UDP: {e}")
        sock.close()
        return
    sock.settimeout(1.0)
    while gen == _geracao and E.network_mode == "auxiliar":
        if E.active_servir:
            time.sleep(2.0)
            continue
        try:
            data, origem = sock.recvfrom(1024)
            msg = data.decode()
            if msg.startswith("SERVIR_LEADER:"):
                p = msg.split(":")
                if len(p) >= 5:
                    # usa o endereco de origem do pacote: e o IP realmente alcancavel nesta rede
                    # (o IP escrito na mensagem pode ser de VPN/outra interface do lider)
                    E.lider_detectado = {"ip": origem[0] or p[1], "port": int(p[2]), "nome_evento": p[3], "evento_id": p[4]}
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Erro ao receber broadcast: {e}")
    sock.close()


def iniciar_servicos():
    global _geracao
    _geracao += 1
    E.auxiliar_stations.clear()
    E.lider_detectado = None
    alvo = _transmitir if E.network_mode == "lider" else _escutar
    threading.Thread(target=alvo, args=(_geracao,), daemon=True).start()


def mudar_modo(modo):
    E.network_mode = "lider" if modo == "lider" else "auxiliar"
    iniciar_servicos()


def sincronizar_com_lider():
    if not E.lider_detectado:
        raise RuntimeError("Nenhum lider detectado na rede.")
    ip, port = E.lider_detectado["ip"], E.lider_detectado["port"]
    r = requests.post(f"http://{ip}:{port}/register", timeout=3.0, json={
        "ip": core.obter_ip_local(), "nome": platform.node() or "Estação Auxiliar", "port": E.local_port})
    if r.status_code != 200:
        raise RuntimeError(f"Não foi possível se registrar no líder: código {r.status_code}")
    r = requests.get(f"http://{ip}:{port}/preset", timeout=3.0)
    if r.status_code != 200:
        raise RuntimeError(f"Não foi possível obter os dados do evento: código {r.status_code}")
    preset = r.json()
    core.ativar_servir(preset)
    return preset


# ---------- finalizar servir (lider) ----------

def coletar_stats_auxiliares():
    """Retorna (lista_de_stats, nomes_com_erro)."""
    ok, erros = [], []
    if E.network_mode != "lider":
        return ok, erros
    for ip, info in list(E.auxiliar_stations.items()):
        try:
            r = requests.get(f"http://{ip}:{info['port']}/stats", timeout=3.0)
            if r.status_code == 200:
                ok.append(r.json().get("categorias", []))
            else:
                erros.append(info['nome'])
        except Exception:
            erros.append(info['nome'])
    return ok, erros


def finalizar_servir(ignorar_erros=False):
    servir = E.active_servir
    if not servir:
        raise RuntimeError("Nenhum dia de Servir ativo para finalizar.")
    aux, erros = coletar_stats_auxiliares()
    if erros and not ignorar_erros:
        return {"status": "confirmar", "estacoes_com_erro": erros}
    categorias = stats.mesclar_estatisticas(stats.obter_estatisticas_locais(), aux)
    info = stats.resumo_por_voluntario(categorias)
    stats.gravar_voluntarios_servir(servir, info)
    payload = {
        "servir": {k: servir.get(k) for k in ("id", "nome", "data_criacao", "drive_link", "drive_nome")}
        | {"voluntarios": servir.get("voluntarios", []), "pastas_predefinidas": servir.get("pastas_predefinidas", [])},
        "categorias": categorias,
    }
    r = requests.post(core.WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Código de status do webhook: {r.status_code}")
    if E.network_mode == "lider":
        for ip, info in list(E.auxiliar_stations.items()):
            try:
                requests.post(f"http://{ip}:{info['port']}/finalize", timeout=2.0)
            except Exception:
                pass
    core.ativar_servir(None)
    return {"status": "ok"}
