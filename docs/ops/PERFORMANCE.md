# Performance e resiliência

O watcher não expõe HTTP; sua jornada crítica é `evento Docker → validação →
rate limit → Telegram`. Os testes devem usar stream Docker e endpoint Telegram
fakes, nunca o socket de produção ou a API real do Telegram.

## SLO inicial (hipótese a validar em staging)

- p95 de processamento local de um evento válido: `< 100 ms`;
- p95 entre evento recebido e tentativa de envio: `< 5 s` sob até 10 eventos/min;
- memória estável durante 8 horas de stream contínuo;
- nenhuma exceção não tratada para evento malformado;
- em tempestade acima do limite, descarte explícito e contável, sem loop de
  envio ilimitado.

O limite padrão é 30 alertas/minuto por instância. `alerts_dropped` não é perda
silenciosa: deve gerar decisão operacional sobre o limite, deduplicação ou
proxy centralizado.

## Cenários

1. Smoke: um evento `die`, um OOM, um unhealthy e um cruzamento de disco.
2. Malformados: objetos sem actor/nome, tipos inválidos e metadados HTML.
3. Spike: volume acima do limite por 5 minutos; verificar memória, descarte e
   retorno ao normal.
4. Recuperação: interromper o stream, validar backoff/jitter e confirmar que o
   watcher retoma sem duplicar alerta de inicialização indefinidamente.
5. Soak: stream fake contínuo por 8 horas, com alternância do uso de disco.

Resultados devem registrar commit, imagem, configuração, volume, p95, falhas,
descartes, memória inicial/final e evidência dos logs de métricas. A execução
deve ocorrer fora do host monitorado.
