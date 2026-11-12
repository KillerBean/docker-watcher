# Changelog

## [Unreleased] — 2026-08-25

### Added

- escaping e limite de tamanho para mensagens Telegram;
- testes unitários, métricas de alertas e rate limit local;
- reconexão com backoff exponencial e jitter;
- documentação de arquitetura, operação e threat model do Docker socket;
- Dependabot configurado para atualizações de dependências (#1).

### Fixed

- imagem de runtime passa a instalar atualizações de segurança (#1);
- certifi 2026.10.18 e urllib3 2.8.0, corrigindo achados HIGH/CRITICAL do Trivy (#5).

### Changed

- atualização de dependências Python minor/patch (5 pacotes) (#6).
