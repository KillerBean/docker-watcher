# docker-watcher

Monitora containers Docker e envia alertas no Telegram quando um container cai.

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
