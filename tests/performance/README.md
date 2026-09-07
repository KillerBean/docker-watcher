# Testes de performance

Os testes de carga deste componente devem usar um fake de `client.events()` e
um fake do Telegram. Não conecte um gerador ao `docker.sock` real nem envie
carga à API externa.

O plano, SLOs e cenários estão em [`docs/ops/PERFORMANCE.md`](../../docs/ops/PERFORMANCE.md).
Um harness executável será adicionado quando o ambiente de staging e o owner
da infraestrutura forem definidos.
