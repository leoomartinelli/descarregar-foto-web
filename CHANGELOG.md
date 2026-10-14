# Histórico de versões

Todas as mudanças de cada versão ficam aqui. O número segue o [Versionamento Semântico](https://semver.org/lang/pt-BR/)
(`MAIOR.MENOR.CORREÇÃO`):

- **MAIOR** — muda algo que obriga todos os PCs a atualizarem juntos (ex.: protocolo da rede Líder/Auxiliar).
- **MENOR** — recurso novo que continua conversando com as versões anteriores.
- **CORREÇÃO** — só correções.

Para lançar uma versão, veja "Como lançar uma nova versão" no README.

## [1.0.0] - 2026-10-14

Primeira versão com instaladores para Windows, macOS e Linux.

### Novo
- Programa instalável com ícone: instalador no Windows, `.dmg` no macOS (Apple Silicon e Intel), `.deb` e `.tar.gz` no Linux.
- Abre com um clique no ícone; clicar de novo com o programa aberto só abre o navegador.
- Botão "⏻ Encerrar" no Painel Inicial para fechar o programa.
- Versão visível na tela; aviso quando sai uma versão nova, com botão para baixar.
- Painel e lista de estações avisam quando um PC está numa versão diferente da do líder.
- Painel de acompanhamento em tempo real pelo QR code: PCs livres/ocupados, quem está descarregando e há quanto
  tempo, quem já descarregou, quem falta e os envios ao Drive de todos os PCs.
- No Windows o instalador libera o programa no Firewall (rede local Líder/Auxiliar e painel no celular).

### Antes desta versão
- Descarregamento do cartão com numeração única entre líder e auxiliar, seleção de fotos, envio ao Google Drive em
  segundo plano, Dias de Servir, predefinições de categorias, rede local Líder/Auxiliar e Finalizar Servir.
