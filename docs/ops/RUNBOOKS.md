# Runbooks

## Watcher reiniciando

1. Verifique `docker logs docker-watcher` e confirme `alerts_failed` versus
   `events_malformed`.
2. Verifique se o daemon Docker está ativo e se o socket está montado.
3. Confirme `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` no secret store, sem
   imprimir valores.
4. Se o Docker daemon estiver indisponível, aguarde o backoff; não faça
   restart em loop manual.

## Alertas Telegram ausentes

1. Consulte `alerts_dropped`: aumento indica tempestade ou limite configurado
   baixo, não necessariamente falha de rede.
2. Consulte `alerts_failed` e valide conectividade de saída HTTPS/429.
3. Teste o chat com uma mensagem controlada e remova o token somente por
   rotação no secret store.

## Disco cheio

1. Identifique o caminho nos logs e preserve evidência do uso.
2. Remova apenas artefatos conhecidos e autorizados; não apague dados Docker
   sem confirmar volumes e política de retenção.
3. Após ficar abaixo do limite, o estado é liberado e um novo cruzamento gera
   um único alerta.

## Rotação ou comprometimento do token

1. Revogue o token no BotFather.
2. Atualize o secret store e recrie somente o serviço.
3. Confirme `alerts_sent` e registre o incidente sem incluir o token nos logs.
