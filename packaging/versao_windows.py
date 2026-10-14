"""Gera packaging/versao_windows.txt (Propriedades > Detalhes do .exe no Windows) a partir do VERSION."""
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
versao = open(os.path.join(AQUI, "..", "VERSION"), encoding="utf-8").read().strip()
n = tuple(int(x) for x in versao.split("-")[0].split(".")) + (0,)

with open(os.path.join(AQUI, "versao_windows.txt"), "w", encoding="utf-8") as f:
    f.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={n}, prodvers={n}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('CompanyName', 'Sistemas Educacionais Crescer'),
      StringStruct('FileDescription', 'Descarregador de Fotos'),
      StringStruct('FileVersion', '{versao}'),
      StringStruct('InternalName', 'DescarregadorDeFotos'),
      StringStruct('OriginalFilename', 'DescarregadorDeFotos.exe'),
      StringStruct('ProductName', 'Descarregador de Fotos'),
      StringStruct('ProductVersion', '{versao}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
""")
print(f"versao_windows.txt: {versao}")
