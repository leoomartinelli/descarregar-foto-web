# Histórico de versões

Todas as mudanças de cada versão ficam aqui. O número segue o [Versionamento Semântico](https://semver.org/lang/pt-BR/)
(`MAIOR.MENOR.CORREÇÃO`):

- **MAIOR** — muda algo que obriga todos os PCs a atualizarem juntos (ex.: protocolo da rede Líder/Auxiliar).
- **MENOR** — recurso novo que continua conversando com as versões anteriores.
- **CORREÇÃO** — numerada sozinha: cada mudança no programa que chega na `main` publica a seguinte, com as notas
  tiradas dos commits. Só MAIOR e MENOR precisam de seção aqui (veja "Subir para 1.1.0 ou 2.0.0" no README).

## [1.1.0] - 2026-10-14

### Novo
- **Editor de fotos** (botão "🎨 Editar Fotos" na etapa final, depois de selecionar): foto por foto, no modelo do
  LightCraft e com o mesmo motor dele.
  - **Luz:** Exposição, Contraste, Realces, Sombras, Brancos e Pretos.
  - **Curva de tons:** Realces, Claros, Escuros e Sombras.
  - **Cor:** Equilíbrio de branco (Como fotografado, Automático, Luz do dia, Nublado, Sombra, Tungstênio,
    Fluorescente, Flash ou Personalizado), conta-gotas, Temperatura, Matiz, Vibratilidade e Saturação.
  - Prévia ao vivo revelada pelo LightCraft (o que aparece é o que vai para o Drive), Antes/Depois, Redefinir e
    duplo clique para voltar uma régua ao padrão.
  - Ao trocar de foto ou concluir, a foto editada é salva em tamanho cheio em segundo plano (RAW vira JPEG); a
    original fica guardada na pasta oculta `.originais` e pode ser restaurada. O envio ao Drive espera os
    salvamentos e leva as fotos editadas.
- **Zoom na seleção de fotos** (v1.0.1): roda do mouse/pinça, arrastar, duplo clique para 100% e foto original.

## [1.0.0] - 2026-10-14

Primeira versão com instaladores para Windows, macOS e Linux.

### Novo
- Programa instalável com ícone: instalador no Windows, `.dmg` no macOS (Apple Silicon e Intel), `.deb` e `.tar.gz` no Linux.
- Abre com um clique no ícone; clicar de novo com o programa aberto só abre o navegador.
- **Atualização automática**: baixa a versão nova em segundo plano, confere o SHA-256 e instala sozinho quando o PC
  está livre; reabre no mesmo Servir, sem perder o login do Google nem os dados.
- Botão "⏻ Encerrar" no Painel Inicial para fechar o programa.
- Versão visível na tela e andamento da atualização no topo.
- Painel e lista de estações avisam quando um PC está numa versão diferente da do líder.
- Painel de acompanhamento em tempo real pelo QR code: PCs livres/ocupados, quem está descarregando e há quanto
  tempo, quem já descarregou, quem falta e os envios ao Drive de todos os PCs.
- No Windows o instalador libera o programa no Firewall e no Linux o `.deb` libera as portas no ufw (rede local
  Líder/Auxiliar e painel no celular).
- Auxiliar explica o que fazer quando o firewall do líder bloqueia a conexão.
- O líder anuncia na rede de cada placa (Mac e Windows com VPN não achavam o líder).
- Auxiliares se registram de novo no líder de tempos em tempos (o líder volta a vê-los depois de reiniciar).

### Antes desta versão
- Descarregamento do cartão com numeração única entre líder e auxiliar, seleção de fotos, envio ao Google Drive em
  segundo plano, Dias de Servir, predefinições de categorias, rede local Líder/Auxiliar e Finalizar Servir.
