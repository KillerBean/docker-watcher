# AGENTS.md

## Escopo

Daemon Python sem framework que lê o stream de eventos do Docker e envia
alertas Telegram. Ele não deve receber comandos administrativos nem expor uma
API HTTP.

## Comandos

```bash
python -m unittest discover -s tests -v
python -m py_compile watcher.py
docker build -t docker-watcher .
```

## Ordem de validação

1. Testes unitários e compilação Python.
2. Revisão de alterações de segurança, especialmente `docker.sock` e Telegram.
3. Build da imagem; deploy somente com CI aprovado.

## Arquivos-chave

- `watcher.py`: configuração, transporte Telegram, validação de eventos, disco e reconexão.
- `tests/test_watcher.py`: classificação, escaping, deduplicação, rate limit e backoff.
- `docs/security/THREAT-MODEL.md`: ameaça e controles do socket.
- `docs/ops/RUNBOOKS.md`: diagnóstico e recuperação.

## Regras

- Nunca registrar token Telegram, payload completo ou valores sensíveis.
- Todo metadado vindo do Docker deve passar por `escaped()` antes de entrar em HTML.
- Mudanças no socket exigem atualização do threat model.
- Não adicionar ações de controle Docker ao watcher sem ADR e revisão de segurança.
