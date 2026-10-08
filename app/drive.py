"""Google Drive: credenciais, login OAuth, teste de conexao, nome de pasta e upload."""
import concurrent.futures
import json
import os
import queue
import threading

from . import core
from .core import E

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    DISPONIVEL = True
except ImportError:
    DISPONIVEL = False

SCOPES = ['https://www.googleapis.com/auth/drive']


# ---------- credenciais ----------

def _escrever_credenciais(client_id, client_secret):
    atuais = core.ler_json(core.PATH_CRED, {}).get("installed", {})
    if atuais.get("client_id") == client_id and atuais.get("client_secret") == client_secret:
        return False
    core.gravar_json(core.PATH_CRED, {"installed": {
        "client_id": client_id,
        "project_id": atuais.get("project_id", "descarregar-foto"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": client_secret,
        "redirect_uris": ["http://localhost"]}})
    if os.path.exists(core.PATH_TOKEN):  # credencial mudou: forca novo login
        os.remove(core.PATH_TOKEN)
    return True


def sincronizar_env():
    """Gera credentials.json a partir do .env (variaveis ou formato de linhas do app desktop)."""
    cid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if (not cid or not secret) and os.path.exists(core.PATH_ENV):
        with open(core.PATH_ENV, encoding='utf-8') as f:
            linhas = [l.strip() for l in f.read().splitlines() if l.strip() and not l.strip().startswith('#')]
        for l in linhas:
            val = l.split("=", 1)[1].strip().strip('"\'') if "=" in l else l
            if l.startswith("GOOGLE_CLIENT_ID="):
                cid = val
            elif l.startswith("GOOGLE_CLIENT_SECRET="):
                secret = val
            elif ".apps.googleusercontent.com" in l and not cid:
                cid = val
            elif "GOCSPX-" in l and not secret:
                secret = val
    if cid and secret:
        _escrever_credenciais(cid, secret)


def salvar_credenciais_manuais(client_id, client_secret):
    client_id, client_secret = client_id.strip(), client_secret.strip()
    if not client_id or not client_secret:
        raise ValueError("Informe o Client ID e o Client Secret.")
    _escrever_credenciais(client_id, client_secret)


def importar_json(conteudo: bytes):
    dados = json.loads(conteudo.decode('utf-8'))
    inst = dados.get("installed") or dados.get("web")
    if not inst or not inst.get("client_id") or not inst.get("client_secret"):
        raise ValueError("JSON inválido: não contém client_id e client_secret.")
    _escrever_credenciais(inst["client_id"], inst["client_secret"])


def status():
    return {"disponivel": DISPONIVEL,
            "tem_credenciais": os.path.exists(core.PATH_CRED),
            "tem_token": os.path.exists(core.PATH_TOKEN),
            "login": E.login}


def _credenciais():
    if not DISPONIVEL or not os.path.exists(core.PATH_TOKEN):
        return None
    try:
        creds = Credentials.from_authorized_user_file(core.PATH_TOKEN, SCOPES)
        if creds and not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(core.PATH_TOKEN, 'w', encoding='utf-8') as f:
                f.write(creds.to_json())
        return creds if creds and creds.valid else None
    except Exception as e:
        print(f"Erro ao carregar token: {e}")
        return None


# ---------- login ----------

def iniciar_login():
    if not DISPONIVEL:
        raise RuntimeError("Bibliotecas da API do Google não estão instaladas.")
    if not os.path.exists(core.PATH_CRED):
        raise RuntimeError("Configure o Client ID e o Client Secret antes de fazer login.")
    if E.login["estado"] == "aguardando":
        raise RuntimeError("Já existe um login em andamento (verifique a janela do navegador).")
    E.login = {"estado": "aguardando", "msg": "Aguardando autorização no navegador..."}

    def fluxo():
        try:
            flow = InstalledAppFlow.from_client_secrets_file(core.PATH_CRED, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(core.PATH_TOKEN, 'w', encoding='utf-8') as f:
                f.write(creds.to_json())
            E.login = {"estado": "ok", "msg": "Login realizado com sucesso!"}
        except Exception as e:
            E.login = {"estado": "erro", "msg": f"Não foi possível concluir o login: {e}"}

    threading.Thread(target=fluxo, daemon=True).start()


def testar_conexao():
    creds = _credenciais()
    if not creds:
        raise RuntimeError("Faça o login no Google primeiro.")
    about = build('drive', 'v3', credentials=creds).about().get(fields="user").execute()
    u = about.get("user", {})
    return {"nome": u.get("displayName", "Usuário"), "email": u.get("emailAddress", "Sem e-mail")}


def remover_token():
    if os.path.exists(core.PATH_TOKEN):
        os.remove(core.PATH_TOKEN)
    E.login = {"estado": "idle", "msg": ""}


# ---------- pastas ----------

def extrair_id_pasta(link_ou_id):
    link_ou_id = (link_ou_id or "").strip()
    if not link_ou_id:
        return 'root'
    if "drive.google.com" in link_ou_id:
        partes = link_ou_id.split("/folders/")
        if len(partes) > 1:
            return partes[1].split("?")[0].split("/")[0]
    return link_ou_id


def nome_pasta(link_ou_id):
    fid = extrair_id_pasta(link_ou_id)
    if fid == 'root':
        return "Raiz do Google Drive"
    creds = _credenciais()
    if not creds:
        return None
    try:
        return build('drive', 'v3', credentials=creds).files().get(fileId=fid, fields='name').execute().get('name')
    except Exception as e:
        print(f"Erro ao obter nome da pasta no Drive: {e}")
        return None


# ---------- upload (fila em segundo plano) ----------

_MIME = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.mp4': 'video/mp4'}
_fila = queue.Queue()
_worker_ativo = False
_lock_fila = threading.Lock()
_contador = 0


def _pasta_filha(svc, nome, pai_id):
    """Retorna o id da subpasta `nome` dentro de `pai_id`, criando-a se nao existir."""
    nome_q = nome.replace("\\", "\\\\").replace("'", "\\'")
    q = (f"name = '{nome_q}' and '{pai_id}' in parents and "
         "mimeType = 'application/vnd.google-apps.folder' and trashed = false")
    achadas = svc.files().list(q=q, fields='files(id)', pageSize=1).execute().get('files', [])
    if achadas:
        return achadas[0]['id']
    meta = {'name': nome, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [pai_id]}
    return svc.files().create(body=meta, fields='id').execute()['id']


def criar_pastas_categorias(servir):
    """Cria, dentro de cada pasta do Drive do Servir, uma pasta por categoria ('Voltz 2026-10-08').
    Retorna uma lista com o resultado de cada pasta (ja existentes sao reaproveitadas)."""
    if not DISPONIVEL:
        raise RuntimeError("Bibliotecas da API do Google não estão instaladas.")
    creds = _credenciais()
    if not creds:
        raise RuntimeError("Você não está logado no Google. Faça o login na tela 'Conta Google'.")
    svc = build('drive', 'v3', credentials=creds)
    resultado = []
    for pasta in servir.get("drive_folders", []):
        if pasta.get("auto"):
            continue  # pastas de categoria criadas antes: nao sao "base"
        base = extrair_id_pasta(pasta.get("link"))
        if base == 'root':
            continue  # nunca cria categorias soltas na raiz do Drive
        for cat in servir.get("pastas_predefinidas", []):
            nome = core.nome_pasta_categoria(cat)
            try:
                fid = _pasta_filha(svc, nome, base)
                resultado.append({"base": pasta.get("nome"), "pasta": nome, "categoria": cat, "id": fid, "ok": True})
            except Exception as e:
                resultado.append({"base": pasta.get("nome"), "pasta": nome, "categoria": cat, "ok": False, "erro": str(e)})
    return resultado


def iniciar_upload(link_pasta, fotografo=""):
    """Enfileira o envio das fotos atuais. Retorna na hora; o envio roda em segundo plano,
    um job por vez (cada job usa 2 conexoes paralelas, como no app original)."""
    global _contador, _worker_ativo
    if not DISPONIVEL:
        raise RuntimeError("Bibliotecas da API do Google não estão instaladas.")
    if not E.arquivos_transferidos:
        raise RuntimeError("Não há fotos disponíveis para upload!")
    if not os.path.exists(core.PATH_CRED):
        raise RuntimeError("credentials.json não encontrado. Configure a Conta Google.")
    creds = _credenciais()
    if not creds:
        raise RuntimeError("Você não está logado no Google. Faça o login na tela 'Conta Google'.")

    folder_id = extrair_id_pasta(link_pasta)
    destino_nome = "a raiz do Google Drive"
    if folder_id != 'root':
        try:
            meta = build('drive', 'v3', credentials=creds).files().get(
                fileId=folder_id, fields='name, mimeType').execute()
        except Exception:
            raise RuntimeError("Não foi possível acessar a pasta no Google Drive. "
                               "Verifique o link, se a pasta existe e as permissões.")
        if meta.get('mimeType') != 'application/vnd.google-apps.folder':
            folder_id = 'root'
        else:
            destino_nome = f"a pasta '{meta.get('name')}'"

    arquivos = list(E.arquivos_transferidos)  # copia: o proximo fotografo pode trocar a lista global
    with _lock_fila:
        _contador += 1
        job = {"id": _contador, "fotografo": fotografo or "Fotógrafo", "total": len(arquivos), "feitos": 0,
               "progresso": 0, "erros": 0, "estado": "fila", "destino": destino_nome, "atuais": [],
               "msg": "Na fila de envio..."}
        E.uploads.append(job)
        del E.uploads[:-20]  # mantem so os 20 mais recentes
        _fila.put((job, creds, folder_id, arquivos))
        if not _worker_ativo:
            _worker_ativo = True
            threading.Thread(target=_worker, daemon=True).start()
    return {"id": job["id"], "total": job["total"]}


def limpar_concluidos():
    E.uploads[:] = [j for j in E.uploads if j["estado"] in ("fila", "rodando")]


def _worker():
    global _worker_ativo
    while True:
        with _lock_fila:
            if _fila.empty():
                _worker_ativo = False
                return
            job, creds, folder_id, arquivos = _fila.get()
        _enviar(job, creds, folder_id, arquivos)


def _enviar(job, creds, folder_id, arquivos):
    lock = threading.Lock()
    total = job["total"]
    job.update(estado="rodando", msg=f"Enviando 0/{total}...")

    def um(caminho):
        nome = os.path.basename(caminho)
        with lock:
            job["atuais"].append(nome)   # so para exibir na tela: arquivos sendo enviados agora
        if os.path.exists(caminho):
            try:
                svc = build('drive', 'v3', credentials=creds)
                meta = {'name': nome}
                if folder_id != 'root':
                    meta['parents'] = [folder_id]
                ext = os.path.splitext(nome)[1].lower()
                mime = 'image/x-raw' if ext in core.EXT_RAW else _MIME.get(ext, 'application/octet-stream')
                req = svc.files().create(body=meta, media_body=MediaFileUpload(caminho, mimetype=mime, resumable=True),
                                         fields='id')
                resp = None
                while resp is None:
                    _, resp = req.next_chunk()
            except Exception as e:
                print(f"Erro ao enviar {nome}: {e}")
                with lock:
                    job["erros"] += 1
        with lock:
            if nome in job["atuais"]:
                job["atuais"].remove(nome)
            job["feitos"] += 1
            job["progresso"] = job["feitos"] / total
            job["msg"] = f"Enviando {job['feitos']}/{total}..."

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(um, arquivos))
        ok = total - job["erros"]
        job.update(estado="concluido" if not job["erros"] else "erro", progresso=1, atuais=[],
                   msg=f"{ok} de {total} fotos enviadas para {job['destino']}.")
    except Exception as e:
        job.update(estado="erro", atuais=[], msg=f"Erro durante o envio: {e}")
