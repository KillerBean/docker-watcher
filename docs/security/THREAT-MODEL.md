# Threat model — Docker watcher

**Perfil:** E — plataforma · **Nível:** L3 · **Data:** 2026-08-25

## Ativos

- token do bot e ID do chat Telegram;
- controle e metadados dos containers no host;
- disponibilidade e confidencialidade dos alertas operacionais;
- logs do processo e estado de deduplicação.

## Fronteiras e ameaças

| Superfície | Ameaça | Impacto |
|---|---|---|
| `/var/run/docker.sock` | processo comprometido usa a API para controlar o host | crítico |
| eventos Docker | nome/imagem maliciosos injetam HTML ou mensagem muito grande | médio |
| Telegram | token vazado ou tempestade de eventos bloqueia o destino | alto |
| logs | exceção/configuração registra segredo ou payload sensível | alto |
| rede de saída | indisponibilidade, timeout ou resposta 429 | médio |

## Controles atuais

- socket documentado e montado como `:ro`; o processo não chama endpoints de
  controle, embora a montagem continue sendo de alto privilégio;
- eventos restritos por filtro e containers benignos ignorados por configuração;
- metadados são limitados e escapados com `html.escape` antes do Telegram;
- timeout HTTP de 10 segundos, rate limit local e mensagens descartadas
  contabilizadas;
- erros de transporte não encerram o watcher; reconnect usa backoff e jitter;
- token não aparece no log, e a imagem não copia `.env`;
- eventos malformados e falhas de disco não viram alertas não validados.

## Riscos residuais e próximos controles

1. `docker.sock` continua equivalente a acesso administrativo ao Docker. O
   controle prioritário é um proxy de eventos com allowlist e endpoint
   somente de leitura; acompanhar em ADR quando o host suportar essa topologia.
2. O token Telegram precisa ser injetado por secret store/Compose protegido,
   nunca por arquivo versionado ou argumento de processo.
3. O rate limit é por instância; múltiplas réplicas exigem limite no gateway ou
   uma política por chat.
4. Logs devem ser coletados com retenção e acesso mínimo; não adicionar dump de
   eventos completos para diagnóstico.

## Verificação

- CI executa testes de escaping, eventos malformados, deduplicação, falhas,
  rate limit e backoff.
- Antes de promover uma mudança no socket, revisar este documento e testar o
  cenário de indisponibilidade/reconexão em host de staging.
