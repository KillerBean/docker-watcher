# Adequação arquitetural

Projeto: docker-watcher  
Owner: plataforma/infraestrutura (a confirmar)  
Perfil: E — plataforma  
Nível atual: L2  
Nível alvo: L3  
Data da avaliação: 2026-08-25

## Controles

- [x] Status e arquitetura documentados
- [x] Runtime e dependências fixados
- [x] CI obrigatório em PR
- [x] Testes exigidos pelo nível — baseline unitária criada
- [x] Secret/dependency/image scan
- [x] Dados e migrations conformes — não aplicável, serviço stateless
- [x] Segurança e threat model conformes
- [x] Logs, métricas, alertas e runbook
- [x] Imagem reproduzível por digest
- [ ] Deploy imutável e rollback comprovados no host
- [ ] Backup/restore comprovado — não aplicável ao estado do processo; validar
      rotação/recuperação de secrets no ambiente

## Exceções/ADRs

| Regra | ADR | Owner | Expira em |
|---|---|---|---|
| Montagem direta do `docker.sock` | a criar | plataforma | revisão antes da próxima mudança de host |

## Próximas três ações

1. Decidir e registrar proxy/agente de eventos com privilégios mínimos.
2. Executar smoke de reconexão e tempestade em staging com Telegram fake.
3. Comprovar rollback da imagem e rotação do token no host de produção.
