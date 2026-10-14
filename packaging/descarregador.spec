# PyInstaller: gera o programa para o sistema em que roda (Windows, macOS ou Linux).
# Uso (na raiz do projeto): pyinstaller --noconfirm packaging/descarregador.spec
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))
VERSAO = open(os.path.join(RAIZ, "VERSION"), encoding="utf-8").read().strip()
NOME = "DescarregadorDeFotos"

datas = [
    (os.path.join(RAIZ, "app", "static"), os.path.join("app", "static")),
    (os.path.join(RAIZ, "VERSION"), "."),
]
datas += collect_data_files("certifi")
datas += collect_data_files("googleapiclient", includes=["**/drive.v3.json"])

hidden = (collect_submodules("uvicorn") + collect_submodules("app")
          + ["googleapiclient.discovery", "google_auth_oauthlib.flow", "segno"])

a = Analysis(
    [os.path.join(RAIZ, "run.py")],
    pathex=[RAIZ],
    binaries=collect_dynamic_libs("rawpy"),
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
# a biblioteca do Google traz a descricao de todas as APIs (~100 MB); so a do Drive v3 e usada
a.datas = [d for d in a.datas if "discovery_cache" not in d[0].replace("\\", "/")
           or os.path.basename(d[0]) in ("drive.v3.json", "__init__.py")]
pyz = PYZ(a.pure)

icone = os.path.join(RAIZ, "housinho.ico" if sys.platform == "win32" else "housinho.png")
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NOME,
    console=False,               # sem janela de terminal: a interface e o navegador
    icon=icone,
    version=os.path.join(SPECPATH, "versao_windows.txt") if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NOME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Descarregador de Fotos.app",
        icon=icone,
        bundle_identifier="br.com.crescer.descarregadorfotos",
        version=VERSAO,
        info_plist={
            "CFBundleShortVersionString": VERSAO,
            "CFBundleVersion": VERSAO,
            "LSUIElement": True,           # sem icone no Dock: a interface e o navegador ("Encerrar" fecha)
            "NSHighResolutionCapable": True,
            # macOS 15+: sem estas descricoes o sistema bloqueia a rede local (lider/auxiliar) e o cartao SD
            "NSLocalNetworkUsageDescription": "Conversar com os outros computadores do Servir (Líder/Auxiliar) "
                                              "e mostrar o painel nos celulares da rede.",
            "NSRemovableVolumesUsageDescription": "Ler as fotos do cartão de memória.",
            "NSDesktopFolderUsageDescription": "Salvar ou ler fotos na Mesa, se você escolher essa pasta.",
            "NSDocumentsFolderUsageDescription": "Salvar ou ler fotos em Documentos, se você escolher essa pasta.",
            "NSDownloadsFolderUsageDescription": "Ler fotos de Downloads, se você escolher essa pasta.",
        },
    )
