# Política de segurança

## Reporte

Não publique detalhes de vulnerabilidades em issues públicas. Envie um relato
privado ao owner do ambiente que executa o watcher, incluindo versão/commit,
host afetado, reprodução mínima e impacto. Não inclua tokens Telegram ou
eventos com dados sensíveis.

## Escopo

O escopo inclui o código do watcher, a imagem Docker, o transporte Telegram e
a configuração de montagem do socket. O acesso ao `docker.sock` é um risco de
alto impacto por definição; a política de ameaça e os controles estão em
[`docs/security/THREAT-MODEL.md`](docs/security/THREAT-MODEL.md).
