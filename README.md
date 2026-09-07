# docker-watcher

Daemon de plataforma que monitora eventos Docker e envia alertas no Telegram
quando um container cai. O processo é somente observador: não executa comandos
nem altera containers.

Perfil E — plataforma | Nível alvo L3 | Status: infraestrutura

## Como funciona

Escuta `docker events` via socket e notifica em:

| Evento | Mensagem |
|--------|----------|
| Container crashou (exit ≠ 0, 143) | 🔴 nome crashou + exit code |
| Container parou graceful (exit 0 ou 143) | 🟡 nome parou (graceful) |
| OOM killer | 💀 nome morreu por OOM |
| Healthcheck unhealthy | ⚠️ nome está unhealthy |

## Variáveis de ambiente

| Variável | Obrigatório | Descrição |
|----------|-------------|-----------|
| `TELEGRAM_BOT_TOKEN` | ✅ | Token do bot (via @BotFather) |
| `TELEGRAM_CHAT_ID` | ✅ | ID do chat/grupo destino |
| `WATCHER_IGNORE` | ❌ | Containers ignorados, separados por vírgula (default: `certbot`) |
| `WATCHER_ALERTS_PER_MINUTE` | ❌ | Limite local de alertas enviados por minuto (default: `30`) |
| `WATCHER_METRICS_INTERVAL` | ❌ | Intervalo dos contadores no log (default: `60`) |
| `RECONNECT_INITIAL_DELAY` | ❌ | Backoff inicial da reconexão em segundos (default: `1`) |
| `RECONNECT_MAX_DELAY` | ❌ | Teto do backoff (default: `60`) |
| `RECONNECT_JITTER` | ❌ | Jitter proporcional do backoff, de `0` a `1` (default: `0.2`) |

Os logs periódicos incluem `events_seen`, `events_malformed`,
`alerts_sent`, `alerts_failed`, `alerts_dropped` e falhas de disco. Alertas
com metadados do Docker são limitados e escapados para Telegram HTML.

## Deploy

```yaml
# docker-compose.yml
docker-watcher:
  build: ./docker-watcher
  container_name: docker-watcher
  restart: always
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  environment:
    - TELEGRAM_BOT_TOKEN=${WATCHER_TELEGRAM_TOKEN}
    - TELEGRAM_CHAT_ID=${WATCHER_TELEGRAM_CHAT_ID}
    - WATCHER_IGNORE=${WATCHER_IGNORE:-certbot}
```

```bash
docker compose build docker-watcher
docker compose up -d docker-watcher
```

O socket deve permanecer montado como `:ro`, mas isso não transforma o Docker
API em uma permissão de baixo risco. Leia o [threat model](docs/security/THREAT-MODEL.md)
antes de instalar o serviço em um host compartilhado.

## Desenvolvimento

```bash
python -m unittest discover -s tests -v
python -m py_compile watcher.py
```

Arquitetura, operação e segurança estão em [`docs/`](docs/), e as instruções
para agentes estão em [`AGENTS.md`](AGENTS.md).
