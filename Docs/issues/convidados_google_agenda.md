# 🚨 Issue #1 — Suporte a Convidados no Google Agenda (.ics RFC-5545)

> **Status**: Aberta / Documentada no Repositório  
> **Link GitHub**: [Issue #1 no GitHub](https://github.com/rezendepauloh/verifica-nomes-diarios-oficiais/issues/1)

---

## 1. Descrição do Problema
Ao gerar o arquivo `.ics` com o cronograma do concurso para importação no Google Agenda, o campo `ATTENDEE` com o e-mail configurado em `GCAL_GUEST_EMAIL` (`convidado@exemplo.com`) é incluído conforme a especificação RFC-5545:
```text
ATTENDEE;CN=Kamila;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:convidado@exemplo.com
```
Entretanto, ao importar o arquivo `.ics` pela interface web do Google Agenda (**Configurações > Importar e Exportar**), o Google Agenda não adiciona o contato na lista de convidados do evento importado.

---

## 2. Diagnóstico Técnico
- O Google Agenda aplica uma restrição na importação em massa via arquivos `.ics`: por questões anti-spam, ele ignora linhas `ATTENDEE` que enviariam convites automáticos por e-mail a terceiros.
- **Solução Futura / Alternativas Planejadas**:
  1. Integração nativa com a **Google Calendar API v3** via OAuth2 / Service Account para criação programática direta com inclusão de convidados e permissões de edição.
  2. Compartilhamento da agenda secundária "Concursos" direto no Google Agenda com a conta da Kamila com permissão de *"Fazer alterações nos eventos"*.

