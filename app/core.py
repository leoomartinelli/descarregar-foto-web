"""Estado global, caminhos, utilitarios e persistencia em JSON."""
import json
import os
import re
import platform
import socket
import subprocess
import threading
import time
from datetime import date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_DIR / FOTOS_DIR permitem apontar para outras pastas (usado nos testes, para nao tocar nos dados reais)
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(BASE_DIR, "data")
DEFAULT_DEST = os.environ.get("FOTOS_DIR") or os.path.join(BASE_DIR, "Fotos_Sistema")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DEFAULT_DEST, exist_ok=True)

PATH_CONFIG = os.path.join(DATA_DIR, "config_pastas.json")
PATH_DIAS = os.path.join(DATA_DIR, "dias_servir.json")
PATH_HIST = os.path.join(DATA_DIR, "historico_downloads.json")
PATH_PRED = os.path.join(DATA_DIR, "predefinicoes.json")
PATH_CRED = os.path.join(DATA_DIR, "credentials.json")
PATH_TOKEN = os.path.join(DATA_DIR, "token.json")
PATH_ENV = os.path.join(BASE_DIR, ".env")

EXT_RAW = ('.cr2', '.nef', '.arw', '.cr3')
EXT_IMG = ('.png', '.jpg', '.jpeg') + EXT_RAW
EXT_TODAS = EXT_IMG + ('.mp4',)
MARKER_NAME = "FOTOS_DESCARREGADAS_ATE_AQUI.txt"
INVALID_NAME_CHARS = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_URL", "https://sistema-crescer-n8n.vuvd0x.easypanel.host/webhook/finalizar-servir")

lock_json = threading.Lock()


def ler_json(caminho, padrao):
    with lock_json:
        if os.path.exists(caminho):
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erro ao ler {caminho}: {e}")
    return padrao


def gravar_json(caminho, dados):
    with lock_json:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)


class Estado:
    """Estado em memoria da estacao (equivale aos atributos do app desktop)."""

    def __init__(self):
        self.active_servir = None
        self.destino_base = DEFAULT_DEST
        # origem das fotos (cartao SD ou pasta manual)
        self.drive_path = ""
        self.cartao_detectado = False
        self.origem_manual = False
        # fotos transferidas na ultima copia (lista para revisor/upload)
        self.arquivos_transferidos = []
        self.sessao_fotografo = None
        self.sessao_destino = None
        # rede local
        self.network_mode = "lider"
        self.local_port = int(os.environ.get("PORT", 50007))
        self.auxiliar_stations = {}
        self.lider_detectado = None
        self.servir_finalizado_remotamente = False
        # jobs em background
        self.transfer = {"estado": "idle", "progresso": 0, "total": 0, "feitos": 0, "msg": ""}
        self.uploads = []  # fila/historico de envios ao Drive (cada um e um "job")
        self.login = {"estado": "idle", "msg": ""}


E = Estado()


def hoje():
    return date.today().isoformat()


_SUFIXO_DATA = re.compile(r" \d{4}-\d{2}-\d{2}$")


def nome_pasta_categoria(categoria):
    """Nome da pasta no disco: 'Voltz' vira 'Voltz 2026-10-08' (data de hoje). 'Raiz (Nenhuma)' nao tem pasta."""
    return f"{categoria} {hoje()}"


def sem_data(nome_pasta):
    """Inverso de nome_pasta_categoria: 'Voltz 2026-10-08' -> 'Voltz' (usado nas estatisticas/webhook)."""
    return _SUFIXO_DATA.sub("", nome_pasta)


def nome_valido(nome):
    return not any(c in nome for c in INVALID_NAME_CHARS) and nome not in ('.', '..')


def obter_ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def abrir_no_gerenciador(caminho):
    """Abre uma pasta no gerenciador de arquivos da maquina que roda o servidor."""
    if not caminho or not os.path.isdir(caminho):
        return False
    try:
        if platform.system() == "Windows":
            os.startfile(caminho)  # noqa
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
        return True
    except Exception as e:
        print(f"Erro ao abrir pasta {caminho}: {e}")
        return False


# ---------- configuracao de pastas (valida somente no dia) ----------

def carregar_config():
    dados = ler_json(PATH_CONFIG, {})
    if isinstance(dados, dict) and dados.get("data") == hoje():
        return {"pastas": dados.get("pastas", []), "pastas_local": dados.get("pastas_local", [])}
    return {"pastas": [], "pastas_local": []}


def salvar_config(pastas, pastas_local):
    gravar_json(PATH_CONFIG, {"data": hoje(), "pastas": pastas, "pastas_local": pastas_local})


# ---------- dias de servir ----------

def carregar_dias():
    dados = ler_json(PATH_DIAS, [])
    return dados if isinstance(dados, list) else []


def salvar_dias(dias):
    gravar_json(PATH_DIAS, dias)


ARQ_VOLUNTARIOS = "voluntarios.txt"


def nomes_do_texto(texto):
    return [l.split(" - ", 1)[0].strip() for l in texto.splitlines() if l.strip()]


def texto_voluntarios(voluntarios, info=None):
    """Conteudo do voluntarios.txt: so os nomes, ou 'Nome - N fotos | Categoria: ... | Câmera: ... | Lente: ...' quando ha
    'info' ({nome minusculo: {"fotos": n, "categorias": {nome: fotos}, "cameras": [...], "lentes": [...]}})."""
    if info is None:
        return "\n".join(voluntarios) + "\n"
    linhas = []
    for v in voluntarios:
        i = info.get(v.lower(), {})
        linha = f"{v} - {i.get('fotos', 0)} fotos"
        if i.get("categorias"):
            linha += " | Categoria: " + ", ".join(f"{c} ({n})" for c, n in sorted(i["categorias"].items()))
        if i.get("cameras"):
            linha += " | Câmera: " + ", ".join(sorted(i["cameras"]))
        if i.get("lentes"):
            linha += " | Lente: " + ", ".join(sorted(i["lentes"]))
        linhas.append(linha)
    return "\n".join(linhas) + "\n"


def _nomes_do_arquivo(caminho):
    try:
        with open(caminho, encoding="utf-8") as f:
            return nomes_do_texto(f.read())
    except OSError:
        return None


def gravar_voluntarios(raiz, voluntarios, info=None):
    """Escreve <raiz>/voluntarios.txt. Sem 'info' so lista os nomes (e preserva o arquivo se os nomes nao mudaram,
    para nao apagar as contagens); com 'info' coloca fotos, camera e lente na frente do nome."""
    caminho = os.path.join(raiz, ARQ_VOLUNTARIOS)
    if info is None:
        if _nomes_do_arquivo(caminho) == list(voluntarios):
            return
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto_voluntarios(voluntarios, info))


def criar_estrutura_servir(servir):
    """Pre-cria <base>/<servir>/<categoria> nas bases conhecidas."""
    nome = servir.get("nome")
    bases = [DEFAULT_DEST]
    if servir.get("local_path"):
        bases.append(servir["local_path"])
    for p in carregar_config()["pastas_local"]:
        bases.append(p.get("caminho"))
    for base in bases:
        if not base:
            continue
        try:
            raiz = os.path.join(base, nome)
            os.makedirs(raiz, exist_ok=True)
            for cat in servir.get("pastas_predefinidas", []):
                os.makedirs(os.path.join(raiz, nome_pasta_categoria(cat)), exist_ok=True)
            gravar_voluntarios(raiz, servir.get("voluntarios", []))
        except Exception as e:
            print(f"Erro ao criar estrutura de pastas em {base}: {e}")


def ativar_servir(servir):
    E.active_servir = servir
    E.arquivos_transferidos = []
    if servir:
        lp = servir.get("local_path")
        E.destino_base = lp if lp and os.path.isdir(lp) else DEFAULT_DEST
        criar_estrutura_servir(servir)
    else:
        E.destino_base = DEFAULT_DEST


# ---------- caminhos de destino ----------

def tem_midia(pasta):
    if not os.path.isdir(pasta):
        return False
    for _, _, files in os.walk(pasta):
        for f in files:
            if f.lower().endswith(EXT_TODAS):
                return True
    return False


def calcular_caminho_final(base_destino, fotografo, categoria="Raiz (Nenhuma)", criar_subpasta=True):
    """Mesma regra do app desktop, incluindo a subpasta _2, _3 em descarregamentos consecutivos."""
    if not base_destino or not fotografo:
        return base_destino
    if E.active_servir:
        base_servir = os.path.join(base_destino, E.active_servir.get("nome"))
        destino = (os.path.join(base_servir, fotografo) if categoria == "Raiz (Nenhuma)"
                   else os.path.join(base_servir, nome_pasta_categoria(categoria), fotografo))
        tem_pasta = True
    else:
        destino = os.path.join(base_destino, fotografo) if criar_subpasta else base_destino
        tem_pasta = criar_subpasta
    if tem_pasta and tem_midia(destino):
        n = 2
        while os.path.exists(os.path.join(destino, f"{fotografo}_{n}")):
            n += 1
        destino = os.path.join(destino, f"{fotografo}_{n}")
    return destino


def pasta_fotografo(base_destino, fotografo, categoria, criar_subpasta=True):
    """Pasta do fotografo SEM o sufixo _N (usada em historico, estatisticas e 'abrir pasta')."""
    if E.active_servir:
        base_servir = os.path.join(base_destino, E.active_servir.get("nome"))
        return (os.path.join(base_servir, fotografo) if categoria == "Raiz (Nenhuma)"
                else os.path.join(base_servir, nome_pasta_categoria(categoria), fotografo))
    return os.path.join(base_destino, fotografo) if criar_subpasta else base_destino


# ---------- historico ----------

def registrar_historico(fotografo, destino, descarregadas):
    hist = ler_json(PATH_HIST, [])
    hist.append({
        "data": hoje(), "hora": time.strftime("%H:%M:%S"), "fotografo": fotografo,
        "descarregadas": descarregadas, "selecionadas": descarregadas, "destino": destino,
    })
    gravar_json(PATH_HIST, hist)
    E.sessao_fotografo, E.sessao_destino = fotografo, destino


def atualizar_historico_selecao(total):
    hist = ler_json(PATH_HIST, [])
    for entry in reversed(hist):
        if entry.get("fotografo") == E.sessao_fotografo and entry.get("destino") == E.sessao_destino:
            entry["selecionadas"] = total
            break
    gravar_json(PATH_HIST, hist)
