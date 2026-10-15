# Descarregador de Fotos — versão Web

Versão web (servidor local + navegador) do Descarregador de Fotos do Ministério. O servidor Python roda no
computador que recebe o cartão SD; a interface é aberta no navegador (`http://localhost:50007`).

## Instalar (sem precisar de Python)
Baixe na página de **[Releases](https://github.com/leoomartinelli/descarregar-foto-web/releases/latest)** o arquivo do seu sistema:

| Sistema | Arquivo | Como instalar |
|---|---|---|
| Windows 10/11 | `…-windows-instalador.exe` | Abra e avance. O ícone aparece na Área de Trabalho e no Menu Iniciar. Na primeira instalação o Windows pede permissão de administrador uma vez, para liberar o Firewall para a rede local. |
| Mac com chip Apple (M1, M2…) | `…-macos-apple-silicon.dmg` | Abra e arraste para **Aplicativos**. |
| Mac com Intel | `…-macos-intel.dmg` | Igual ao de cima. |
| Ubuntu, Mint, Debian | `…-linux-amd64.deb` | Dois cliques e **Instalar**. O ícone aparece no menu. Outras distribuições: `.tar.gz`, extraia e rode `criar-atalho.sh`. |

**Só precisa instalar uma vez: o programa se atualiza sozinho.** Ele procura versão nova a cada 20 minutos, baixa
em segundo plano e instala quando o PC está livre (ninguém descarregando nem enviando ao Drive; no líder, nenhum PC
da rede descarregando). Fecha e reabre em poucos segundos, no mesmo Servir, e a tela recarrega sozinha. O login do
Google, os Dias de Servir e as fotos não são tocados. No Linux com o `.deb` ele pede a senha para instalar.

Depois é só clicar no ícone: o programa abre no navegador. Clicar de novo com ele aberto só abre o navegador outra
vez. Para fechar, use **⏻ Encerrar** no Painel Inicial.

- **Mac, na primeira vez:** o macOS avisa que não pode verificar o desenvolvedor. Abra *Ajustes do Sistema →
  Privacidade e Segurança*, desça até o aviso do Descarregador de Fotos e clique em **Abrir Mesmo Assim**. Quando
  ele pedir acesso à **rede local**, permita (sem isso o Líder/Auxiliar e o painel no celular não funcionam).
- **Windows:** se aparecer "O Windows protegeu o computador", clique em *Mais informações → Executar assim mesmo*.
- **Dados e fotos** ficam em `Descarregador de Fotos`, dentro da pasta do usuário (o mesmo nos três sistemas). O
  `.env` vai nessa pasta, e o log em `descarregador.log`. Atualizar ou reinstalar não apaga nada.
- **Todos os PCs do Servir devem ter a mesma versão** (com a atualização automática isso acontece sozinho). O programa
  mostra a versão no Painel Inicial e o painel do celular aponta os PCs com versão diferente da do líder.

## Rodar pelo código-fonte (desenvolvimento)
```bash
./rodar.sh        # Linux/macOS      |   rodar.bat  # Windows
```
Na primeira execução o ambiente virtual e as dependências são instalados automaticamente.
Copie `.env-example` para `.env` se quiser definir credenciais do Google, webhook ou porta.
Para a conversão de RAW para JPEG, baixe o conversor uma vez: `python packaging/baixar_lightcraft.py` (vai para
`vendor/lightcraft/`; sem ele o programa só avisa que há RAW e copia no formato original).

## Versões e compilação
- **Cada push na `main` que muda o programa vira uma versão nova** (`1.0.1`, `1.0.2`…) e os PCs se atualizam
  sozinhos. Mudanças só em documentação, testes ou no workflow não geram versão. Regras em
  `packaging/calcular_versao.py`; as notas da versão saem dos commits (ou da seção do `CHANGELOG.md`, se houver).
- O GitHub Actions (`.github/workflows/compilar.yml`) roda os testes nos três sistemas e compila. Cada programa
  compilado passa por autoteste (`--autoteste`), pelo teste da rede (`packaging/teste_rede.py`), é instalado como o
  usuário faria e passa pelo teste de **atualização automática** (`packaging/teste_atualizacao.py`): o programa
  instalado se acha antigo, baixa a versão nova, se instala, reabre e volta no mesmo Servir. A versão só é publicada
  se tudo isso passar nos quatro (Windows, Linux, Mac Apple Silicon e Mac Intel).
- Pull requests compilam com o número que a versão teria, sem publicar (programas em "Artifacts" da execução).

### Subir para 1.1.0 ou 2.0.0
As correções são numeradas sozinhas. Para marcar um passo maior (**MENOR**: recurso novo; **MAIOR**: mudança que
obriga todos os PCs a atualizarem juntos, como o protocolo da rede):
1. Escreva no `CHANGELOG.md` a seção `## [1.1.0] - AAAA-MM-DD` e faça o commit na `main`.
2. `python packaging/nova_versao.py 1.1.0` (confere tudo, grava o `VERSION` e faz o commit).
3. `git push`.

Compilar localmente (gera para o sistema atual): `pip install pyinstaller`, `python packaging/baixar_lightcraft.py` e
`pyinstaller --noconfirm packaging/descarregador.spec` (resultado em `dist/`).

## Módulos (equivalentes ao app desktop)
| Módulo | Onde |
|---|---|
| Dias de Servir (criar, editar, excluir, ativar) e Modo Avulso | Painel inicial |
| Detecção de cartão SD / origem manual, seleção de pastas (DCIM) | Tela de descarregamento |
| Cópia paralela, numeração `Fotografo_001`, marcador "já descarregadas", subpastas `_2`, `_3`, aviso de RAW | `app/transfer.py` |
| Conversão de RAW para JPEG ao descarregar (pergunta antes; resolução total; apaga só a cópia RAW do PC, nunca o cartão) com o motor do [LightCraft](https://github.com/storytold/lightcraft) (MIT/Apache-2.0) | `app/raw.py` |
| Seleção de fotos (miniaturas, teclado, desfazer, apagar, zoom até o tamanho original) | Botão "Selecionar Fotos" |
| Editor de fotos (Luz, Curva de tons e Cor com o motor do LightCraft; original guardada em `.originais`) | Botão "Editar Fotos" / `app/editor.py` |
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
