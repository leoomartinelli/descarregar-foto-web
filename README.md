# Descarregador de Fotos — versão Web

Versão web (servidor local + navegador) do Descarregador de Fotos do Ministério. O servidor Python roda no
computador que recebe o cartão SD; a interface é aberta no navegador (`http://localhost:50007`).

## Instalar (sem precisar de Python)
Baixe na página de **[Releases](https://github.com/leoomartinelli/descarregar-foto-web/releases/latest)** o arquivo do seu sistema:

| Sistema | Arquivo | Como instalar |
|---|---|---|
| Windows 10/11 | `…-windows-instalador.exe` | Abra e avance. O ícone aparece na Área de Trabalho e no Menu Iniciar, e o Firewall já fica liberado para a rede local. Sem permissão de administrador: use o `…-windows-portatil.zip`. |
| Mac com chip Apple (M1, M2…) | `…-macos-apple-silicon.dmg` | Abra e arraste para **Aplicativos**. |
| Mac com Intel | `…-macos-intel.dmg` | Igual ao de cima. |
| Ubuntu, Mint, Debian | `…-linux-amd64.deb` | Dois cliques e **Instalar**. O ícone aparece no menu. Outras distribuições: `.tar.gz`, extraia e rode `criar-atalho.sh`. |

Depois é só clicar no ícone: o programa abre no navegador. Clicar de novo com ele aberto só abre o navegador outra
vez. Para fechar, use **⏻ Encerrar** no Painel Inicial.

- **Mac, na primeira vez:** o macOS avisa que não pode verificar o desenvolvedor. Abra *Ajustes do Sistema →
  Privacidade e Segurança*, desça até o aviso do Descarregador de Fotos e clique em **Abrir Mesmo Assim**. Quando
  ele pedir acesso à **rede local**, permita (sem isso o Líder/Auxiliar e o painel no celular não funcionam).
- **Windows:** se aparecer "O Windows protegeu o computador", clique em *Mais informações → Executar assim mesmo*.
- **Dados e fotos** ficam em `Descarregador de Fotos`, dentro da pasta do usuário (o mesmo nos três sistemas). O
  `.env` vai nessa pasta, e o log em `descarregador.log`. Atualizar ou reinstalar não apaga nada.
- **Todos os PCs do Servir devem ter a mesma versão.** O programa mostra a versão no Painel Inicial, avisa quando sai
  uma nova e o painel do celular aponta os PCs com versão diferente da do líder.

## Rodar pelo código-fonte (desenvolvimento)
```bash
./rodar.sh        # Linux/macOS      |   rodar.bat  # Windows
```
Na primeira execução o ambiente virtual e as dependências são instalados automaticamente.
Copie `.env-example` para `.env` se quiser definir credenciais do Google, webhook ou porta.

## Versões e compilação
- A versão fica **só** no arquivo `VERSION` (`MAIOR.MENOR.CORREÇÃO`). Cada versão tem a sua seção no `CHANGELOG.md`.
- O GitHub Actions (`.github/workflows/compilar.yml`) roda os testes nos três sistemas e compila em cada push na
  `main`. Cada programa compilado passa por autoteste (`--autoteste`), pelo teste do protocolo da rede
  (`packaging/teste_rede.py`) e é instalado e testado de novo, como o usuário faria.
- Uma **tag `vX.Y.Z`** publica a release com os instaladores. O workflow recusa a tag se ela for diferente do
  `VERSION` ou se faltar a seção no `CHANGELOG.md`.

### Como lançar uma nova versão
1. Escreva no `CHANGELOG.md` a seção `## [1.2.0] - AAAA-MM-DD` com o que mudou e faça o commit na `main`.
2. Rode `python packaging/nova_versao.py 1.2.0`: confere tudo, grava o `VERSION`, faz o commit e cria a tag.
3. Publique: `git push origin main v1.2.0`. Em ~15 minutos a release aparece com os instaladores.

Compilar localmente (gera para o sistema atual): `pip install pyinstaller` e
`pyinstaller --noconfirm packaging/descarregador.spec` (resultado em `dist/`).

## Módulos (equivalentes ao app desktop)
| Módulo | Onde |
|---|---|
| Dias de Servir (criar, editar, excluir, ativar) e Modo Avulso | Painel inicial |
| Detecção de cartão SD / origem manual, seleção de pastas (DCIM) | Tela de descarregamento |
| Cópia paralela, numeração `Fotografo_001`, marcador "já descarregadas", subpastas `_2`, `_3`, aviso de RAW | `app/transfer.py` |
| Seleção de fotos (miniaturas, teclado, desfazer, apagar) | Botão "Selecionar Fotos" |
| Upload para o Google Drive | Tela de descarregamento |
| Conta Google (credenciais, login OAuth, teste, desconectar) | Painel → Login Google |
| Pastas do Drive e pastas locais do dia | Painel → Config Drive |
| Histórico | Painel → Histórico |
| Rede local Líder/Auxiliar (UDP 50008 + HTTP 50007) e Finalizar Servir (webhook) | Painel / `app/lan.py` |
| Painel de acompanhamento pelo celular (QR code ao iniciar o Servir): PCs livres/ocupados, quem está descarregando e há quanto tempo, quem já descarregou e quem falta | `app/painel.py` / `/painel` |
| Atualização via Git (aviso na tela, `git pull` com um clique) | `app/main.py` |

A rede local usa o **mesmo protocolo** do app desktop (`/preset`, `/stats`, `/register`, `/finalize`),
então estações desktop e web podem trabalhar juntas.

## Segurança
O servidor escuta em `0.0.0.0` somente para a rede local Líder/Auxiliar. Por padrão, **apenas a própria máquina**
acessa a interface e a API (`/api/*`); de outros computadores só respondem os endpoints do protocolo de rede (`/preset`, `/stats`, `/register`,
`/finalize`, `/numeracao`, `/atividade`) e o painel somente leitura (`/painel`, `/painel/dados`).
Para liberar a interface na rede (ex.: usar de um tablet) defina `ALLOW_REMOTE_UI=1` — só em rede confiável,
pois a interface lê e apaga arquivos do disco.

## Testes
```bash
.venv/bin/pip install pytest httpx
.venv/bin/python -m pytest tests -q
```

## Estrutura
```
app/core.py      estado, caminhos, JSON, regras de destino      app/stats.py   EXIF e estatísticas
app/transfer.py  cartão, plano e cópia                          app/review.py  JPEG para o revisor (RAW via rawpy)
app/drive.py     Google Drive                                   app/lan.py     rede local e webhook
app/main.py      API FastAPI                                    app/static/    interface (HTML/CSS/JS)
app/painel.py    painel de acompanhamento (QR code)          app/versao.py  versão e caminhos do executável
packaging/       PyInstaller, instaladores e testes do programa compilado
```
Dados do usuário ficam em `data/` e as fotos em `Fotos_Sistema/` (ambos fora do Git).
