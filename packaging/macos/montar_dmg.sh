#!/usr/bin/env bash
# macOS: gera o .dmg (abrir e arrastar o app para Aplicativos) a partir de "dist/Descarregador de Fotos.app".
# Uso: packaging/macos/montar_dmg.sh <apple-silicon|intel>
set -euo pipefail
cd "$(dirname "$0")/../.."
VERSAO="$(tr -d '[:space:]' < VERSION)"
SUFIXO="${1:?informe apple-silicon ou intel}"
APP="dist/Descarregador de Fotos.app"
mkdir -p saida

# assinatura ad-hoc do pacote inteiro: sem ela o macOS em Apple Silicon recusa abrir o app
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Aplicativos"
hdiutil create -volname "Descarregador de Fotos $VERSAO" -srcfolder "$STAGE" -ov -format UDZO \
  "saida/DescarregadorDeFotos-$VERSAO-macos-$SUFIXO.dmg"
rm -rf "$STAGE"
ls -lh saida/
