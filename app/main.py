"""Servidor web do Descarregador de Fotos."""
import ipaddress
import os
import subprocess
import threading
import time

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import core, drive, lan, review, stats, transfer
from .core import E

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app = FastAPI(title="Descarregador de Fotos - Web")

# Endpoints publicos na rede local (protocolo Lider/Auxiliar). Todo o resto so aceita a propria maquina,
# a menos que ALLOW_REMOTE_UI=1.
ROTAS_LAN = {"/preset", "/stats", "/register", "/finalize"}
UPDATE = {"disponivel": False, "msg": ""}


def _head():
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=core.BASE_DIR, capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or None
    except Exception:
        return None


_HEAD_INICIO = _head()           # versao do codigo quando este servidor foi iniciado
_cache_reinicio = {"t": 0.0, "v": False}


def precisa_reiniciar():
    """True se o codigo em disco (git HEAD) mudou depois que este servidor iniciou: o Python so le o codigo ao
    iniciar, entao a tela avisa que e preciso reiniciar para as mudancas do servidor valerem."""
    agora = time.time()
    if agora - _cache_reinicio["t"] > 10:
        atual = _head()
        _cache_reinicio.update(t=agora, v=bool(_HEAD_INICIO and atual and atual != _HEAD_INICIO))
    return _cache_reinicio["v"]


@app.middleware("http")
async def restringir_acesso(request: Request, call_next):
    if request.url.path not in ROTAS_LAN and os.environ.get("ALLOW_REMOTE_UI") != "1":
        host = request.client.host if request.client else ""
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host in ("localhost", "testclient")
        if not local:
            return JSONResponse({"erro": "Acesso permitido apenas na própria máquina."}, status_code=403)
    return await call_next(request)


def erro(msg, codigo=400):
    raise HTTPException(status_code=codigo, detail=msg)


# ======================= estado geral =======================

@app.get("/api/state")
def estado():
    cfg = core.carregar_config()
    return {
        "active_servir": E.active_servir,
        "destino_base": E.destino_base,
        "destino_padrao": core.DEFAULT_DEST,
        "origem": {"detectada": E.cartao_detectado, "caminho": E.drive_path, "manual": E.origem_manual},
        "rede": {"modo": E.network_mode, "ip": core.obter_ip_local(), "porta": E.local_port,
                 "lider": E.lider_detectado,
                 "auxiliares": [{"ip": ip, **info} for ip, info in E.auxiliar_stations.items()]},
        "servir_finalizado_remotamente": E.servir_finalizado_remotamente,
        "pastas_drive": cfg["pastas"], "pastas_local": cfg["pastas_local"],
        "transferidas": len(E.arquivos_transferidos),
        "update": UPDATE,
        "precisa_reiniciar": precisa_reiniciar(),
    }


@app.post("/api/ack-finalizado")
def ack_finalizado():
    E.servir_finalizado_remotamente = False
    return {"ok": True}


# ======================= dias de servir =======================

def _montar_servir(dados, base):
    nome = (dados.get("nome") or "").strip()
    if not nome:
        erro("Por favor, insira o nome do Servir!")
    if not core.nome_valido(nome):
        erro("O nome do Servir não pode conter / \\ : * ? \" < > |")
    vols = [v.strip() for v in dados.get("voluntarios", []) if v and v.strip()]
    if not vols:
        erro("Por favor, adicione pelo menos um voluntário!")
    drives = [d for d in dados.get("drive_folders", []) if d.get("link")]
    for d in drives:
        d["nome"] = d.get("nome") or "Pasta do Google Drive"
    local = (dados.get("local_path") or "").strip()
    base.update({
        "nome": nome, "voluntarios": vols,
        "pastas_predefinidas": [p.strip() for p in dados.get("pastas_predefinidas", []) if p.strip()],
        "drive_link": drives[0]["link"] if drives else "", "drive_nome": drives[0]["nome"] if drives else "",
        "drive_folders": drives, "local_path": local,
        "drive_criar_categorias": bool(dados.get("drive_criar_categorias")) and bool(drives),
        "local_nome": os.path.basename(local.rstrip("/\\")) if local else "",
    })
    return base


@app.get("/api/servir")
def listar_servir():
    return core.carregar_dias()


@app.post("/api/servir")
def criar_servir(dados: dict = Body(...)):
    servir = _montar_servir(dados, {"id": str(int(time.time())), "data_criacao": core.hoje()})
    dias = core.carregar_dias()
    dias.append(servir)
    core.salvar_dias(dias)
    core.ativar_servir(servir)
    return servir


@app.put("/api/servir/{sid}")
def editar_servir(sid: str, dados: dict = Body(...)):
    dias = core.carregar_dias()
    for i, s in enumerate(dias):
        if s.get("id") == sid:
            dias[i] = _montar_servir(dados, s)
            core.salvar_dias(dias)
            core.criar_estrutura_servir(dias[i])
            if E.active_servir and E.active_servir.get("id") == sid:
                E.active_servir = dias[i]
            return dias[i]
    erro("Servir não encontrado.", 404)


@app.delete("/api/servir/{sid}")
def excluir_servir(sid: str):
    core.salvar_dias([d for d in core.carregar_dias() if d.get("id") != sid])
    return {"ok": True}


@app.post("/api/servir/{sid}/ativar")
def ativar_servir(sid: str):
    for s in core.carregar_dias():
        if s.get("id") == sid:
            core.ativar_servir(s)
            return s
    erro("Servir não encontrado.", 404)


@app.post("/api/servir/{sid}/drive-pastas")
def criar_pastas_drive(sid: str):
    for s in core.carregar_dias():
        if s.get("id") == sid:
            if not s.get("pastas_predefinidas"):
                erro("Este Servir não tem pastas de categoria.")
            if not any(drive.extrair_id_pasta(d.get("link")) != "root" for d in s.get("drive_folders", [])):
                erro("Este Servir não tem pasta do Drive configurada.")
            try:
                resultado = drive.criar_pastas_categorias(s)
            except RuntimeError as e:
                erro(str(e), 502)
            return {"resultado": resultado, "servir": _registrar_pastas_drive(sid, resultado)}
    erro("Servir não encontrado.", 404)


def _registrar_pastas_drive(sid, resultado):
    """Salva as pastas criadas no Drive em 'Pastas do Google Drive' do Servir (nome + link), para o voluntario
    escolher o destino do envio. As de dias anteriores (criadas automaticamente) saem da lista."""
    dias = core.carregar_dias()
    for d in dias:
        if d.get("id") != sid:
            continue
        hoje = core.hoje()
        pastas = [f for f in d.get("drive_folders", []) if not (f.get("auto") and f.get("data") != hoje)]
        links = {f.get("link") for f in pastas}
        for r in resultado:
            if not r.get("ok"):
                continue
            link = f"https://drive.google.com/drive/folders/{r['id']}"
            if link not in links:
                links.add(link)
                pastas.append({"link": link, "nome": r["pasta"], "auto": True, "categoria": r["categoria"], "data": hoje})
        d["drive_folders"] = pastas
        core.salvar_dias(dias)
        if E.active_servir and E.active_servir.get("id") == sid:
            E.active_servir = d
        return d
    return None


@app.post("/api/avulso")
def modo_avulso():
    core.ativar_servir(None)
    return {"ok": True}


@app.post("/api/servir/finalizar")
def finalizar_servir(dados: dict = Body(default={})):
    try:
        return lan.finalizar_servir(ignorar_erros=bool(dados.get("ignorar_erros")))
    except Exception as e:
        erro(str(e), 502)


# ======================= predefinicoes de categorias =======================

PRED_PADRAO = [{"titulo": "ELEVE", "pastas": ["Voltz", "Bold", "Burn", "A3"]}]


@app.get("/api/predefinicoes")
def listar_predefinicoes():
    dados = core.ler_json(core.PATH_PRED, None)
    if not isinstance(dados, list):
        dados = PRED_PADRAO  # primeira vez: exemplo para o usuario editar ou excluir
        core.gravar_json(core.PATH_PRED, dados)
    return dados


@app.put("/api/predefinicoes")
def salvar_predefinicoes(dados: list = Body(...)):
    limpo = []
    for p in dados:
        titulo = (p.get("titulo") or "").strip()
        pastas = []
        for n in p.get("pastas", []):
            n = (n or "").strip()
            if n and not core.nome_valido(n):
                erro(f"O nome de pasta '{n}' não pode conter / \\ : * ? \" < > |")
            if n and n not in pastas:
                pastas.append(n)
        if not titulo or not pastas:
            erro("Cada predefinição precisa de um título e de pelo menos uma pasta.")
        limpo.append({"titulo": titulo, "pastas": pastas})
    core.gravar_json(core.PATH_PRED, limpo)
    return limpo


# ======================= configuracao de pastas (Drive e locais) =======================

@app.get("/api/config")
def obter_config():
    return core.carregar_config()


@app.put("/api/config")
def salvar_config(dados: dict = Body(...)):
    pastas = [p for p in dados.get("pastas", []) if p.get("link")]
    locais = [p for p in dados.get("pastas_local", []) if p.get("caminho")]
    core.salvar_config(pastas, locais)
    return {"ok": True}


@app.get("/api/drive/nome-pasta")
def nome_pasta(link: str):
    return {"nome": drive.nome_pasta(link)}


# ======================= sistema de arquivos do servidor =======================

@app.get("/api/fs/list")
def fs_list(path: str = ""):
    path = os.path.abspath(path or os.path.expanduser("~"))
    if not os.path.isdir(path):
        erro("Pasta inexistente.", 404)
    pastas = []
    try:
        for n in sorted(os.listdir(path), key=str.lower):
            if not n.startswith('.') and os.path.isdir(os.path.join(path, n)):
                pastas.append(n)
    except PermissionError:
        erro("Sem permissão para ler esta pasta.", 403)
    atalhos = [{"nome": "Início", "caminho": os.path.expanduser("~")},
               {"nome": "Pasta do aplicativo", "caminho": core.DEFAULT_DEST}]
    atalhos += [{"nome": c["mountpoint"], "caminho": c["mountpoint"]} for c in transfer._candidatos()]
    return {"path": path, "parent": os.path.dirname(path), "pastas": pastas, "atalhos": atalhos}


@app.post("/api/fs/mkdir")
def fs_mkdir(dados: dict = Body(...)):
    pai, nome = dados.get("path", ""), (dados.get("nome") or "").strip()
    if not os.path.isdir(pai) or not nome or not core.nome_valido(nome):
        erro("Pasta ou nome inválido.")
    os.makedirs(os.path.join(pai, nome), exist_ok=True)
    return {"path": os.path.join(pai, nome)}


@app.post("/api/fs/abrir")
def fs_abrir(dados: dict = Body(...)):
    if not core.abrir_no_gerenciador(dados.get("path", "")):
        erro("A pasta não existe ou foi movida/deletada.", 404)
    return {"ok": True}


# ======================= origem (cartao) e transferencia =======================

@app.get("/api/origem")
def origem():
    return {"detectada": E.cartao_detectado, "caminho": E.drive_path, "manual": E.origem_manual,
            "pastas": transfer.listar_pastas_origem() if E.cartao_detectado else [],
            "candidatos": transfer._candidatos()}


@app.post("/api/origem")
def definir_origem(dados: dict = Body(...)):
    p = dados.get("path", "")
    if not os.path.isdir(p):
        erro("Pasta de origem inexistente.", 404)
    transfer.definir_origem(p)
    return {"ok": True}


@app.get("/api/destino/preview")
def preview_destino(base: str = "", fotografo: str = "", categoria: str = "Raiz (Nenhuma)",
                    subpasta: bool = True):
    if not base:
        return {"caminho": "Selecione a pasta de destino acima..."}
    return {"caminho": core.calcular_caminho_final(base, fotografo or "(Aguardando nome do fotógrafo)",
                                                    categoria, subpasta)}


def _validar_transferencia(d):
    fot = (d.get("fotografo") or "").strip()
    if not E.cartao_detectado:
        erro("Nenhum cartão SD detectado!")
    if not fot or not core.nome_valido(fot):
        erro("Selecione ou digite um nome de fotógrafo válido!")
    if not d.get("destino_base"):
        erro("Selecione a pasta de destino no computador!")
    if not d.get("pastas"):
        erro("Selecione pelo menos uma pasta do cartão para descarregar!")
    return fot


@app.post("/api/transferencia/plano")
def plano(d: dict = Body(...)):
    _validar_transferencia(d)
    return transfer.planejar(d["pastas"])


@app.post("/api/transferencia/iniciar")
def iniciar_transferencia(d: dict = Body(...)):
    fot = _validar_transferencia(d)
    E.destino_base = d["destino_base"]
    try:
        return transfer.iniciar(fot, d["destino_base"], d["pastas"], d.get("categoria", "Raiz (Nenhuma)"),
                                d.get("subpasta", True), d.get("modo", "novas"))
    except RuntimeError as e:
        erro(str(e))


@app.get("/api/transferencia/status")
def status_transferencia():
    return E.transfer


@app.post("/api/transferencia/nova")
def nova_transferencia():
    E.arquivos_transferidos = []
    E.transfer = {"estado": "idle", "progresso": 0, "total": 0, "feitos": 0, "msg": ""}
    # os envios ao Drive em andamento NAO sao tocados: continuam em segundo plano
    return {"ok": True}


# ======================= revisor =======================

@app.get("/api/revisor")
def revisor_lista():
    return {"arquivos": [os.path.basename(p) for p in E.arquivos_transferidos]}


@app.get("/api/revisor/imagem/{i}")
def revisor_imagem(i: int, lado: int = 1600):
    if not 0 <= i < len(E.arquivos_transferidos):
        erro("Foto inexistente.", 404)
    lado = max(64, min(lado, 4000))
    try:
        dados = review.renderizar(E.arquivos_transferidos[i], lado)
    except Exception as e:
        erro(f"Erro ao carregar imagem: {e}", 500)
    return Response(dados, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@app.post("/api/revisor/finalizar")
def revisor_finalizar(d: dict = Body(...)):
    """Apaga permanentemente as fotos marcadas (indices na lista atual)."""
    lista = E.arquivos_transferidos
    idx = {int(i) for i in d.get("descartar", []) if 0 <= int(i) < len(lista)}
    apagadas = erros = 0
    for i in idx:
        try:
            if os.path.exists(lista[i]):
                os.remove(lista[i])
                apagadas += 1
        except Exception as e:
            print(f"Erro ao deletar {lista[i]}: {e}")
            erros += 1
    E.arquivos_transferidos = [p for i, p in enumerate(lista) if i not in idx]
    core.atualizar_historico_selecao(len(E.arquivos_transferidos))
    return {"apagadas": apagadas, "erros": erros, "restantes": len(E.arquivos_transferidos)}


@app.post("/api/revisor/abrir-pasta")
def revisor_abrir_pasta(d: dict = Body(default={})):
    alvo = E.sessao_destino
    if not alvo or not os.path.isdir(alvo):
        alvo = E.destino_base
    if not core.abrir_no_gerenciador(alvo):
        erro("Pasta não encontrada.", 404)
    return {"ok": True}


# ======================= upload para o Drive =======================

@app.post("/api/upload/iniciar")
def upload_iniciar(d: dict = Body(default={})):
    try:
        return drive.iniciar_upload(d.get("link", ""), E.sessao_fotografo or "")
    except RuntimeError as e:
        erro(str(e))


@app.get("/api/uploads")
def upload_lista():
    return E.uploads


@app.post("/api/uploads/limpar")
def upload_limpar():
    drive.limpar_concluidos()
    return {"ok": True}


# ======================= historico =======================

@app.get("/api/historico")
def historico():
    return list(reversed(core.ler_json(core.PATH_HIST, [])))


@app.delete("/api/historico")
def limpar_historico():
    if os.path.exists(core.PATH_HIST):
        os.remove(core.PATH_HIST)
    return {"ok": True}


# ======================= conta Google =======================

@app.get("/api/google/status")
def google_status():
    return drive.status()


@app.post("/api/google/credenciais")
def google_credenciais(d: dict = Body(...)):
    try:
        drive.salvar_credenciais_manuais(d.get("client_id", ""), d.get("client_secret", ""))
    except ValueError as e:
        erro(str(e))
    return drive.status()


@app.post("/api/google/importar")
def google_importar(d: dict = Body(...)):
    """Recebe o conteudo do credentials.json (lido no navegador) como texto."""
    try:
        drive.importar_json((d.get("conteudo") or "").encode("utf-8"))
    except Exception as e:
        erro(f"Arquivo inválido: {e}")
    return drive.status()


@app.post("/api/google/login")
def google_login():
    try:
        drive.iniciar_login()
    except RuntimeError as e:
        erro(str(e))
    return drive.status()


@app.post("/api/google/testar")
def google_testar():
    try:
        return drive.testar_conexao()
    except Exception as e:
        erro(str(e), 502)


@app.post("/api/google/desconectar")
def google_desconectar():
    drive.remover_token()
    return drive.status()


# ======================= rede local =======================

@app.post("/api/rede/modo")
def rede_modo(d: dict = Body(...)):
    lan.mudar_modo(d.get("modo", "lider"))
    return {"ok": True}


@app.post("/api/rede/reiniciar")
def rede_reiniciar():
    lan.iniciar_servicos()
    return {"ok": True}


@app.post("/api/rede/sincronizar")
def rede_sincronizar():
    try:
        return lan.sincronizar_com_lider()
    except Exception as e:
        erro(str(e), 502)


# --- protocolo Lider/Auxiliar (compativel com o app desktop) ---

@app.get("/preset")
def lan_preset():
    if not E.active_servir:
        return Response("No active servir event", status_code=404)
    return E.active_servir


@app.get("/stats")
def lan_stats():
    return {"categorias": stats.obter_estatisticas_locais()}


@app.post("/register")
def lan_register(d: dict = Body(...)):
    if not d.get("ip") or not d.get("nome"):
        return Response(status_code=400)
    E.auxiliar_stations[d["ip"]] = {"nome": d["nome"], "port": d.get("port", 50007), "last_seen": time.time()}
    return {"status": "ok"}


@app.post("/finalize")
def lan_finalize():
    core.ativar_servir(None)
    E.servir_finalizado_remotamente = True
    return {"status": "ok"}


# ======================= atualizacao via git =======================

def _git(*args, timeout=10):
    return subprocess.run(["git", *args], cwd=core.BASE_DIR, capture_output=True, text=True, timeout=timeout)


def verificar_atualizacao():
    try:
        if not os.path.isdir(os.path.join(core.BASE_DIR, ".git")):
            return
        if _git("fetch", "origin", "main", timeout=8).returncode != 0:
            return
        remoto = _git("rev-parse", "origin/main", timeout=3).stdout.strip()
        # Só há atualização se o origin/main tem commits que o HEAD local não tem.
        # (HEAD igual ou à frente do remoto = nada a atualizar.)
        ja_contem = _git("merge-base", "--is-ancestor", "origin/main", "HEAD", timeout=3).returncode == 0
        if remoto and not ja_contem:
            UPDATE.update(disponivel=True, msg=f"Nova versão disponível ({remoto[:7]}).")
    except Exception as e:
        print(f"[AutoUpdate] verificação ignorada: {e}")


@app.post("/api/update/aplicar")
def aplicar_atualizacao():
    r = _git("pull", "--ff-only", "origin", "main", timeout=30)
    if r.returncode != 0:
        erro(f"Falha ao atualizar: {r.stderr.strip()}", 500)
    UPDATE.update(disponivel=False, msg="Atualizado. Reinicie o servidor para aplicar.")
    return UPDATE


@app.on_event("startup")
def iniciar():
    drive.sincronizar_env()
    lan.iniciar_servicos()
    threading.Thread(target=transfer.monitorar_cartao, daemon=True).start()
    threading.Thread(target=verificar_atualizacao, daemon=True).start()


@app.get("/")
def index():
    """Entrega o index com ?v=<data do arquivo> nos CSS/JS: o navegador baixa de novo sempre que mudarem,
    sem precisar de Ctrl+F5 depois de uma atualizacao."""
    html = open(os.path.join(STATIC, "index.html"), encoding="utf-8").read()
    for nome in ("style.css", "app.js"):
        v = int(os.path.getmtime(os.path.join(STATIC, nome)))
        html = html.replace(f"/static/{nome}", f"/static/{nome}?v={v}")
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=STATIC), name="static")
