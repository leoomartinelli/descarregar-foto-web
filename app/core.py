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
        # ultimo descarregamento ainda sem envio ao Drive: {"raiz", "chave", "fim_ts"} (mede o tempo ate o envio)
        self.descarregamento_atual = None
        # rede local
        self.network_mode = "lider"
        self.local_port = int(os.environ.get("PORT", 50007))
        self.auxiliar_stations = {}
        self.lider_detectado = None
        self.servir_finalizado_remotamente = False
        # o que esta estacao esta fazendo agora (painel do QR code): livre ou ocupado por um voluntario
        self.atividade = {"estado": "livre"}
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


ARQ_ENVIADOS = ".enviados_drive.json"
_lock_enviados = threading.Lock()


def raiz_servir(servir):
    return os.path.join(E.destino_base, servir.get("nome"))


def _chave_arquivo(raiz, caminho):
    return os.path.relpath(caminho, raiz).replace(os.sep, "/")


def _ler_enviados(raiz):
    try:
        with open(os.path.join(raiz, ARQ_ENVIADOS), encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return {}
    if isinstance(dados, list):      # formato antigo: so os caminhos, sem a pasta de destino
        return {c: None for c in dados}
    return dados if isinstance(dados, dict) else {}


def carregar_enviados(raiz):
    """Conjunto de caminhos (relativos a <raiz> do Servir) que ja foram enviados com sucesso ao Drive."""
    return set(_ler_enviados(raiz))


def carregar_enviados_destino(raiz):
    """{caminho relativo: id da pasta do Drive para onde foi}; None quando o registro e antigo."""
    return _ler_enviados(raiz)


def marcar_enviados(raiz, caminhos, pasta_drive=None):
    """Registra no disco os arquivos enviados ao Drive (sobrevive a reinicios; mesmo arquivo nao conta duas vezes)."""
    if not caminhos:
        return
    with _lock_enviados:
        todos = _ler_enviados(raiz)
        for c in caminhos:
            todos[_chave_arquivo(raiz, c)] = pasta_drive
        with open(os.path.join(raiz, ARQ_ENVIADOS), "w", encoding="utf-8") as f:
            json.dump(todos, f)


ARQ_NUMERACAO = ".numeracao.json"


def maior_numero(pasta, fotografo):
    """Maior N entre os arquivos '<fotografo>_N...' dentro da pasta (recursivo); 0 se nao houver."""
    prefixo = f"{fotografo}_"
    maior = 0
    for _, _, files in os.walk(pasta):
        for f in files:
            if f.startswith(prefixo):
                parte = os.path.splitext(f[len(prefixo):])[0].split('_')[0]
                if parte.isdigit():
                    maior = max(maior, int(parte))
    return maior


def reservar_numeracao(raiz, chave, fotografo, quantidade, maximo_remoto=0):
    """Roda no LIDER (e no PC unico): devolve o primeiro numero livre para 'quantidade' fotos do fotografo e reserva
    a faixa, para que o mesmo voluntario descarregando em outro PC (auxiliar) continue a sequencia sem repetir."""
    with _lock_enviados:
        caminho = os.path.join(raiz, ARQ_NUMERACAO)
        try:
            with open(caminho, encoding="utf-8") as f:
                reservas = json.load(f)
        except (OSError, ValueError):
            reservas = {}
        ultimo = max(maior_numero(os.path.join(raiz, chave), fotografo), int(reservas.get(chave, 0)),
                     int(maximo_remoto or 0))
        reservas[chave] = ultimo + quantidade
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(reservas, f)
        return ultimo + 1


ARQ_DESCARREGAMENTOS = ".descarregamentos.json"


def carregar_descarregamentos(raiz):
    """{'<categoria>/<fotografo>': {'fotos': n copiadas do cartao, 'segundos': tempo gasto copiando}}.
    Guarda o que foi descarregado de verdade: as fotos no disco diminuem quando o revisor apaga as ruins."""
    try:
        with open(os.path.join(raiz, ARQ_DESCARREGAMENTOS), encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def registrar_descarregamento(raiz, pasta_fotografo, fotos, segundos):
    """Grava o descarregamento. Retorna {"raiz", "chave", "fim_ts"} para depois medir o tempo ate o envio ao Drive."""
    chave = _chave_arquivo(raiz, pasta_fotografo)
    fim_ts = time.time()
    with _lock_enviados:
        dados = carregar_descarregamentos(raiz)
        atual = dados.setdefault(chave, {"fotos": 0, "segundos": 0.0})
        atual["fotos"] += fotos
        atual["segundos"] = round(atual["segundos"] + segundos, 1)
        atual.setdefault("eventos", []).append({
            "data_hora": time.strftime("%Y-%m-%d %H:%M:%S"), "fotos": fotos, "segundos": round(segundos, 1),
            "estacao": platform.node() or "Estação", "fim_ts": fim_ts, "segundos_ate_envio": None})
        with open(os.path.join(raiz, ARQ_DESCARREGAMENTOS), "w", encoding="utf-8") as f:
            json.dump(dados, f)
    return {"raiz": raiz, "chave": chave, "fim_ts": fim_ts}


def marcar_envio_drive(atual):
    """Chamado quando o voluntario manda as fotos desse descarregamento ao Drive: grava quanto tempo passou
    desde o fim da copia (so a primeira vez)."""
    with _lock_enviados:
        dados = carregar_descarregamentos(atual["raiz"])
        for ev in dados.get(atual["chave"], {}).get("eventos", []):
            if ev.get("fim_ts") == atual["fim_ts"] and ev.get("segundos_ate_envio") is None:
                ev["segundos_ate_envio"] = round(time.time() - atual["fim_ts"], 1)
                with open(os.path.join(atual["raiz"], ARQ_DESCARREGAMENTOS), "w", encoding="utf-8") as f:
                    json.dump(dados, f)
                return


def formatar_duracao(segundos):
    s = int(round(segundos))
    h, resto = divmod(s, 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h}h {m:02d}min {s:02d}s"
    return f"{m}min {s:02d}s" if m else f"{s}s"


def texto_voluntarios(voluntarios, info=None):
    """Conteudo do voluntarios.txt: so os nomes, ou 'Nome - Descarregadas: N | No Drive: M | Categoria: ... | Câmera: ... | Lente: ...' quando ha
    'info' ({nome minusculo: {"descarregadas": n, "fotos": n_no_disco, "drive": enviadas, "categorias": {nome: fotos}, "cameras": [...], "lentes": [...]}})."""
    if info is None:
        return "\n".join(voluntarios) + "\n"
    linhas = []
    for v in voluntarios:
        i = info.get(v.lower(), {})
        linha = f"{v} - Descarregadas: {i.get('descarregadas', i.get('fotos', 0))}" \
                f" | No Drive: {i.get('drive', 0)}"
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
    E.atividade = {"estado": "livre"}
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
