"""Atualizacao automatica do programa instalado.

Procura a ultima release no GitHub; se for mais nova, baixa em segundo plano o arquivo deste sistema, confere o
SHA-256 publicado na release e instala quando o PC estiver livre (ninguem descarregando nem enviando ao Drive; no
lider, nenhum PC da rede descarregando). O programa fecha, a versao nova e instalada e ele reabre sozinho, voltando
ao Servir que estava ativo. Se a instalacao falhar, reabre a versao antiga.

Rodando pelo codigo-fonte nada disso acontece (la a atualizacao e pelo git)."""
import hashlib
import os
import platform
import shlex
import subprocess
import sys
import threading
import time

import requests

from . import core, painel, versao
from .core import E

# procura versao nova a cada 20 min (a variavel de ambiente encurta o intervalo no teste do GitHub Actions)
INTERVALO_BUSCA = int(os.environ.get("DESCARREGADOR_INTERVALO_BUSCA") or 20 * 60)
INTERVALO_LIVRE = 15           # com a versao baixada, confere a cada 15 s se o PC ficou livre
PASTA = os.path.join(versao.PASTA_USUARIO, "atualizacao")
ARQ_RETOMAR = os.path.join(core.DATA_DIR, "retomar.json")
VALIDADE_RETOMAR = 15 * 60

# estado: nenhuma | baixando | pronta | instalando | erro | manual (nao da para instalar sozinho: so o link)
ESTADO = {"estado": "nenhuma", "versao": None, "msg": "", "url": ""}


# ---------- qual arquivo da release serve para este computador ----------

def tipo_instalacao():
    """'windows' | 'macos' | 'deb' | 'targz'; None rodando pelo codigo-fonte."""
    if not versao.EMPACOTADO:
        return None
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "deb" if os.path.realpath(sys.executable).startswith("/opt/descarregador-de-fotos/") else "targz"


def sufixo_arquivo(tipo, maquina=None):
    maquina = (maquina or platform.machine()).lower()
    if tipo == "macos":
        return "-macos-apple-silicon.dmg" if maquina in ("arm64", "aarch64") else "-macos-intel.dmg"
    if tipo in ("deb", "targz") and maquina not in ("x86_64", "amd64"):
        return None                                  # so ha pacote Linux para PCs comuns (amd64)
    return {"windows": "-windows-instalador.exe", "deb": "-linux-amd64.deb", "targz": "-linux-amd64.tar.gz"}.get(tipo)


def escolher_arquivos(release, tipo, maquina=None):
    """(arquivo deste sistema, SHA256SUMS.txt) da release; None no que faltar."""
    sufixo = sufixo_arquivo(tipo, maquina)
    assets = release.get("assets") or []
    arq = next((a for a in assets if sufixo and a.get("name", "").endswith(sufixo)), None)
    somas = next((a for a in assets if a.get("name") == "SHA256SUMS.txt"), None)
    return arq, somas


def sha_esperado(texto_somas, nome):
    for linha in texto_somas.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[1].lstrip("*") == nome:
            return partes[0].lower()
    return None


# ---------- buscar e baixar ----------

def buscar_release():
    """A ultima release, se for mais nova que esta versao; senao None."""
    r = requests.get(versao.API_ULTIMA_RELEASE, timeout=10, headers={"Accept": "application/vnd.github+json"})
    if r.status_code != 200:
        return None
    rel = r.json()
    return rel if versao.tupla(rel.get("tag_name")) > versao.tupla(versao.VERSAO) else None


def baixar(release, tipo):
    arq, somas = escolher_arquivos(release, tipo)
    if not arq or not somas:
        raise RuntimeError("a versão nova não tem arquivo para este computador")
    esperado = sha_esperado(requests.get(somas["browser_download_url"], timeout=30).text, arq["name"])
    if not esperado:
        raise RuntimeError("a versão nova não tem a soma de verificação do arquivo")
    os.makedirs(PASTA, exist_ok=True)
    for antigo in os.listdir(PASTA):                 # sobras de atualizacoes anteriores
        try:
            os.remove(os.path.join(PASTA, antigo))
        except OSError:
            pass
    destino = os.path.join(PASTA, arq["name"])
    h = hashlib.sha256()
    with requests.get(arq["browser_download_url"], stream=True, timeout=60) as r, open(destino + ".parcial", "wb") as f:
        r.raise_for_status()
        for bloco in r.iter_content(1 << 20):
            f.write(bloco)
            h.update(bloco)
    if h.hexdigest() != esperado:
        os.remove(destino + ".parcial")
        raise RuntimeError("o arquivo baixado veio corrompido (SHA-256 não confere); tento de novo mais tarde")
    os.replace(destino + ".parcial", destino)
    return destino


# ---------- quando instalar ----------

def motivo_ocupado():
    """Por que ainda nao da para reiniciar; None se o PC (e, no lider, a rede) esta livre."""
    if E.atividade.get("estado") == "ocupado":
        return "um voluntário está usando este PC"
    if E.transfer.get("estado") == "rodando":
        return "copiando fotos"
    if any(j.get("estado") in ("fila", "rodando") for j in E.uploads):
        return "enviando fotos ao Drive"
    if E.login.get("estado") == "aguardando":
        return "login do Google em andamento"
    if E.network_mode == "lider" and E.active_servir and E.auxiliar_stations:
        # os auxiliares pedem a numeracao ao lider no comeco de cada copia: o lider nao some no meio
        if painel.dados_painel().get("agora"):
            return "outro PC da rede está descarregando"
    return None


# ---------- voltar como estava depois de reiniciar ----------

def salvar_retomar():
    core.gravar_json(ARQ_RETOMAR, {"ts": time.time(), "servir": E.active_servir, "modo": E.network_mode,
                                   "lider": E.lider_detectado, "auxiliares": E.auxiliar_stations,
                                   "destino_base": E.destino_base, "de_versao": versao.VERSAO})


def ler_retomar():
    """Dados salvos antes da atualizacao (apaga o arquivo); None se nao houver ou forem antigos."""
    dados = core.ler_json(ARQ_RETOMAR, None)
    try:
        os.remove(ARQ_RETOMAR)
    except OSError:
        pass
    if not isinstance(dados, dict) or time.time() - dados.get("ts", 0) > VALIDADE_RETOMAR:
        return None
    return dados


# ---------- instalar ----------

def _ambiente_limpo():
    env = dict(os.environ)
    env.pop("DESCARREGADOR_FINGIR_VERSAO", None)     # a versao nova nao pode herdar a versao fingida do teste
    return env


def _script_windows(instalador, exe):
    log = os.path.join(PASTA, "instalador.log")
    q = lambda t: "'" + t.replace("'", "''") + "'"   # noqa: E731  (texto entre aspas simples no PowerShell)
    # Start-Process junta os argumentos com espaco sem colocar aspas: o caminho do log (com espacos) vai entre aspas
    return f"""$ErrorActionPreference = 'Continue'
function Passo($t) {{ Add-Content -Path {q(os.path.join(PASTA, "passos.log"))} -Value "$(Get-Date -Format s) $t" }}
Passo 'esperando o programa fechar'
Start-Sleep -Seconds 3
Passo 'rodando o instalador'
$p = Start-Process -FilePath {q(instalador)} -PassThru -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /REABRIR=1 /LOG={'"' + log.replace("'", "''") + '"'}'
$p.WaitForExit()
Passo "instalador terminou: codigo $($p.ExitCode)"
# o instalador reabre a versao nova; se ele falhar, reabre a antiga
if ($p.ExitCode -ne 0) {{ Passo 'reabrindo a versao antiga'; Start-Process -FilePath {q(exe)} -ArgumentList '--sem-navegador' }}
"""


def _script_unix(tipo, arquivo):
    exe = os.path.realpath(sys.executable)
    if tipo == "macos":
        app = exe.split("/Contents/MacOS/")[0]
        corpo = f"""APP={shlex.quote(app)}
MNT="$(mktemp -d)"
if hdiutil attach {shlex.quote(arquivo)} -nobrowse -noverify -mountpoint "$MNT"; then
  NOVO="$(ls -d "$MNT"/*.app | head -1)"
  rm -rf "$APP.velho"
  if mv "$APP" "$APP.velho" && ditto "$NOVO" "$APP"; then rm -rf "$APP.velho"; echo "instalado"
  else rm -rf "$APP"; mv "$APP.velho" "$APP"; echo "falhou: versao antiga mantida"; fi
  hdiutil detach "$MNT" -quiet || true
fi
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
BIN="$APP/Contents/MacOS/{os.path.basename(exe)}"
"""
    elif tipo == "deb":
        corpo = f"""DEB={shlex.quote(arquivo)}
if command -v pkexec >/dev/null 2>&1 && [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then
  pkexec apt-get install -y --reinstall --allow-downgrades "$DEB" || sudo -n apt-get install -y --reinstall --allow-downgrades "$DEB"
else
  sudo -n apt-get install -y --reinstall --allow-downgrades "$DEB"
fi
BIN=/usr/bin/descarregador-de-fotos
"""
    else:   # .tar.gz portatil: troca a pasta inteira, mantendo o mesmo caminho (os atalhos continuam valendo)
        corpo = f"""DIR={shlex.quote(os.path.dirname(exe))}
TMP="$(mktemp -d)"
if tar -xzf {shlex.quote(arquivo)} -C "$TMP" && NOVO="$(ls -d "$TMP"/DescarregadorDeFotos-* | head -1)" && [ -n "$NOVO" ]; then
  rm -rf "$DIR.velho"
  if mv "$DIR" "$DIR.velho" && mv "$NOVO" "$DIR"; then rm -rf "$DIR.velho"; echo "instalado"
  else rm -rf "$DIR"; mv "$DIR.velho" "$DIR"; echo "falhou: versao antiga mantida"; fi
fi
rm -rf "$TMP"
BIN="$DIR/{os.path.basename(exe)}"
"""
    return f"""#!/bin/sh
# gerado pelo Descarregador de Fotos para se atualizar
# espera este programa fechar (processo "zumbi" ja fechou; no maximo 60 s)
for i in $(seq 120); do
  ESTADO="$(ps -o stat= -p {os.getpid()} 2>/dev/null)"
  case "$ESTADO" in ""|Z*) break ;; esac
  sleep 0.5
done
{corpo}nohup "$BIN" --sem-navegador >/dev/null 2>&1 &
"""


def aplicar(arquivo, tipo):
    """Salva o estado, dispara o instalador num processo separado e fecha este programa."""
    salvar_retomar()
    ESTADO.update(estado="instalando", msg=f"Instalando a versão {ESTADO['versao']}… o programa volta em instantes.")
    log = open(os.path.join(PASTA, "aplicar.log"), "a", encoding="utf-8")
    if tipo == "windows":
        script = os.path.join(PASTA, "aplicar.ps1")
        with open(script, "w", encoding="utf-8-sig") as f:      # BOM: o PowerShell le acentos certo
            f.write(_script_windows(arquivo, sys.executable))
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                          "-WindowStyle", "Hidden", "-File", script], creationflags=flags, env=_ambiente_limpo(),
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL, close_fds=True)
    else:
        script = os.path.join(PASTA, "aplicar.sh")
        with open(script, "w", encoding="utf-8") as f:
            f.write(_script_unix(tipo, arquivo))
        subprocess.Popen(["/bin/sh", script], start_new_session=True, env=_ambiente_limpo(),
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL, close_fds=True)
    print(f"[Atualizacao] instalando {os.path.basename(arquivo)}; fechando para reabrir na versao nova")
    threading.Timer(1.5, os._exit, args=(0,)).start()


def pode_instalar_sozinho(tipo):
    if not tipo or not sufixo_arquivo(tipo):
        return False
    if tipo == "macos":
        app = os.path.realpath(sys.executable).split("/Contents/MacOS/")[0]
        return os.access(os.path.dirname(app), os.W_OK) and os.access(app, os.W_OK)
    if tipo == "targz":
        return os.access(os.path.dirname(os.path.dirname(os.path.realpath(sys.executable))), os.W_OK)
    return True


# ---------- laco em segundo plano ----------

def _laco(tipo):
    proxima, arquivo = 0.0, None
    while True:
        try:
            if ESTADO["estado"] in ("nenhuma", "erro", "manual") and time.time() >= proxima:
                proxima = time.time() + INTERVALO_BUSCA
                rel = buscar_release()
                if rel and not pode_instalar_sozinho(tipo):
                    ESTADO.update(estado="manual", versao=rel.get("tag_name", "").lstrip("v"),
                                  url=rel.get("html_url") or versao.URL_RELEASES,
                                  msg=f"Nova versão disponível: {rel.get('tag_name')}. Baixe e instale por cima.")
                elif rel:
                    ESTADO.update(estado="baixando", versao=rel.get("tag_name", "").lstrip("v"), url="",
                                  msg=f"Baixando a versão {rel.get('tag_name')} em segundo plano…")
                    arquivo = baixar(rel, tipo)
                    ESTADO.update(estado="pronta", msg=f"Versão {ESTADO['versao']} baixada.")
            if ESTADO["estado"] == "pronta":
                motivo = motivo_ocupado()
                if not motivo:
                    return aplicar(arquivo, tipo)
                ESTADO["msg"] = f"Versão {ESTADO['versao']} pronta: instala sozinha quando o PC ficar livre ({motivo})."
        except Exception as e:
            print(f"[Atualizacao] {e}")
            ESTADO.update(estado="erro", msg=f"Não foi possível atualizar agora: {e}")
        time.sleep(INTERVALO_LIVRE)


def iniciar():
    tipo = tipo_instalacao()
    if not tipo or os.environ.get("AUTO_ATUALIZAR", "1") == "0":
        return
    threading.Thread(target=_laco, args=(tipo,), daemon=True).start()
