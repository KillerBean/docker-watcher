# Arquitetura

O watcher é um processo único com três responsabilidades isoladas por
função:

1. `watch()` abre o stream somente de eventos `die`, `oom` e `health_status`.
2. `process_event()` valida o formato, aplica a lista de ignorados e despacha
   somente notificações; eventos malformados são descartados e contabilizados.
3. `watch_disk()` faz polling independente e mantém estado de deduplicação por
   caminho.

`TelegramNotifier` é o adapter externo. Ele aplica rate limit, timeout,
limite de tamanho e contadores de sucesso, falha e descarte. O supervisor
`run()` reinicia o stream com backoff exponencial limitado e jitter.

O socket Docker é uma dependência de leitura de alto privilégio, não uma
fronteira de segurança. O desenho recomendado de longo prazo é substituir a
montagem direta por um proxy/agente de eventos com allowlist; a decisão e o
risco residual estão no [threat model](../security/THREAT-MODEL.md).
