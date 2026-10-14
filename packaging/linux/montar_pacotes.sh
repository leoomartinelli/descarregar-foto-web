#!/usr/bin/env bash
# Linux: gera o .deb (Ubuntu, Mint, Debian: dois cliques instala e o icone aparece no menu) e o .tar.gz portatil
# a partir de dist/DescarregadorDeFotos (saida do PyInstaller). Uso: packaging/linux/montar_pacotes.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSAO="$(tr -d '[:space:]' < VERSION)"
ARQ="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
PKG="descarregador-de-fotos"
mkdir -p saida
STAGE="$(mktemp -d)"

# --- .deb ---
install -d "$STAGE/DEBIAN" "$STAGE/opt/$PKG" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
           "$STAGE/usr/share/icons/hicolor/256x256/apps" "$STAGE/etc/ufw/applications.d"
cp -a dist/DescarregadorDeFotos/. "$STAGE/opt/$PKG/"
ln -s "/opt/$PKG/DescarregadorDeFotos" "$STAGE/usr/bin/$PKG"
python3 - "$STAGE/usr/share/icons/hicolor/256x256/apps/$PKG.png" <<'EOF'
import sys
from PIL import Image
Image.open("housinho.png").convert("RGBA").resize((256, 256), Image.LANCZOS).save(sys.argv[1])
EOF
cat > "$STAGE/usr/share/applications/$PKG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Descarregador de Fotos
Comment=Descarregar as fotos do cartão, selecionar e enviar ao Google Drive
Exec=/usr/bin/$PKG
Icon=$PKG
Terminal=false
Categories=Graphics;Photography;
StartupNotify=false
EOF
cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PKG
Version: $VERSAO
Architecture: $ARQ
Maintainer: Leonardo Martinelli <leoomartinelli@users.noreply.github.com>
Section: graphics
Priority: optional
Depends: xdg-utils
Homepage: https://github.com/leoomartinelli/descarregar-foto-web
Description: Descarregador de Fotos do Ministério
 Descarrega as fotos do cartão de memória, permite selecionar as melhores e enviar
 ao Google Drive. Vários computadores trabalham juntos na rede local (Líder/Auxiliar)
 e o painel de acompanhamento abre no celular pelo QR code.
EOF
cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t /usr/share/icons/hicolor || true
# firewall do Ubuntu (ufw): libera as portas do programa, como o instalador do Windows faz
if [ "$1" = configure ] && command -v ufw >/dev/null 2>&1; then
  ufw app update "Descarregador de Fotos" >/dev/null 2>&1 || true
  ufw allow "Descarregador de Fotos" >/dev/null 2>&1 || true
fi
exit 0
EOF
cat > "$STAGE/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
# so ao desinstalar (numa atualizacao a liberacao continua)
if [ "$1" = remove ] && command -v ufw >/dev/null 2>&1; then
  ufw delete allow "Descarregador de Fotos" >/dev/null 2>&1 || true
fi
exit 0
EOF
# perfil do ufw: porta do servidor (50007/TCP) e descoberta do lider (50008/UDP). Sem a liberacao o auxiliar acha
# o lider (o anuncio sai do lider) mas nao consegue conectar ("timed out").
cat > "$STAGE/etc/ufw/applications.d/$PKG" <<EOF
[Descarregador de Fotos]
title=Descarregador de Fotos
description=Rede local Lider/Auxiliar e painel de acompanhamento no celular
ports=50007/tcp|50008/udp
EOF
echo "/etc/ufw/applications.d/$PKG" > "$STAGE/DEBIAN/conffiles"
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm"
chmod -R u+rwX,go+rX,go-w "$STAGE/opt" "$STAGE/usr" "$STAGE/etc"
dpkg-deb --root-owner-group --build "$STAGE" "saida/DescarregadorDeFotos-$VERSAO-linux-$ARQ.deb"

# --- .tar.gz portatil (qualquer distribuicao: extrair e clicar em DescarregadorDeFotos) ---
PORT="$STAGE/port/DescarregadorDeFotos-$VERSAO"
mkdir -p "$PORT"
cp -a dist/DescarregadorDeFotos/. "$PORT/"
cp "$STAGE/usr/share/icons/hicolor/256x256/apps/$PKG.png" "$PORT/icone.png"
cat > "$PORT/criar-atalho.sh" <<'EOF'
#!/usr/bin/env bash
# Cria o icone do Descarregador de Fotos no menu de aplicativos (e na Area de Trabalho, se existir).
DIR="$(cd "$(dirname "$0")" && pwd)"
ATALHO="[Desktop Entry]
Type=Application
Name=Descarregador de Fotos
Exec=\"$DIR/DescarregadorDeFotos\"
Icon=$DIR/icone.png
Terminal=false
Categories=Graphics;Photography;"
mkdir -p ~/.local/share/applications
echo "$ATALHO" > ~/.local/share/applications/descarregador-de-fotos.desktop
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo ~/Desktop)"
if [ -d "$DESK" ]; then
  echo "$ATALHO" > "$DESK/descarregador-de-fotos.desktop"
  chmod +x "$DESK/descarregador-de-fotos.desktop"
  gio set "$DESK/descarregador-de-fotos.desktop" metadata::trusted true 2>/dev/null || true
fi
echo "Atalho criado. Procure 'Descarregador de Fotos' no menu."
EOF
chmod +x "$PORT/criar-atalho.sh" "$PORT/DescarregadorDeFotos"
tar -C "$STAGE/port" -czf "saida/DescarregadorDeFotos-$VERSAO-linux-$ARQ.tar.gz" "DescarregadorDeFotos-$VERSAO"
rm -rf "$STAGE"
ls -lh saida/
