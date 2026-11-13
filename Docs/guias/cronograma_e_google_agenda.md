# 📅 Guia de Cronograma & Integração com o Google Agenda

O sistema oferece uma integração fluida entre as datas oficiais dos editais e o seu fluxo diário no **Google Agenda**.

---

## 1. Fatiamento Semântico de Datas (`split_period_into_events`)

Muitas etapas de concursos são publicadas em formato de períodos (intervalos de dias), como:
> *"Período de solicitação de inscrições: 10/10/2026 a 04/11/2026"*

Para que a sua agenda permaneça limpa e com avisos claros nas datas que realmente importam, o gerador divide o período em **dois eventos independentes**:
1. **`[CGU] Início das inscrições`** no dia 10/10/2026 às 10:00 (dia inteiro ou horário da banca).
2. **`[CGU] Fim das inscrições`** no dia 04/11/2026 com descrição avisando que é o último dia.

---

## 2. Padrão Visual das Nomenclaturas

Seguindo o estilo da sua agenda "Concursos":
- Títulos concisos e diretos com a sigla do órgão entre colchetes:
  - `[CGU] Início das inscrições`
  - `[CGU] Consulta aos locais de provas`
  - `[CGU] Aplicação das provas objetivas e discursiva`
  - `[CGU] Recursos contra prova objetiva`
- **Descrições Formatadas**:
  - Parágrafos espaçados com quebra dupla de linha.
  - Link oficial da página da banca logo no topo.
  - Texto literal extraído do edital para consulta rápida.

---

## 3. Formas de Uso

### Opção A: Atalhos Rápidos na Tabela (1-Click)
Na coluna **Google Agenda** da tabela de cronograma:
- Botões **`[Início]`** e **`[Fim]`** (ou **`[+ Adicionar]`**):
  - Abrem diretamente a tela de criação do Google Agenda web (`calendar.google.com/calendar/render?action=TEMPLATE...`) com título, datas, links e detalhes já preenchidos.

### Opção B: Exportação Completa em Arquivo `.ics`
Na barra lateral da subtab `crono`:
- Clique em **`📅 Exportar (.ics Google)`**.
- Um arquivo padronizado RFC-5545 é baixado com todos os eventos do concurso.
- No Google Agenda, vá em **Configurações > Importar e Exportar**, selecione a sua agenda "Concursos" e faça o upload do arquivo. Todos os prazos aparecerão instantaneamente organizados.

---

## 4. Alertas Automáticos via WhatsApp (CallMeBot)

O sistema possui um robô inteligente que monitora os prazos do cronograma diariamente às **07:30 da manhã** (e sob demanda via botão **`📲 Testar Alertas no WhatsApp`**):
- **Gatilhos de Notificação**:
  - `🚨 Vence Hoje!`: Etapas pontuais que vencem no dia atual.
  - `🚨 Último dia Hoje!` / `🟢 Começa Hoje!`: Períodos que encerram ou iniciam no próprio dia.
  - `⏳ Encerra Amanhã` / `⏳ Prazo Amanhã`: Aviso prévio de 24h para você não perder prazos críticos (pagamento de GRU, encerramento de inscrições, recursos, etc.).
- **Segmentação por Interessado**:
  - Respeita o campo de interessado do edital (*Paulo*, *Kamila* ou *Ambos*).
- **Links Diretos na Mensagem**:
  - Envia os links configurados em `APP_LOCAL_URL` e `APP_PUBLIC_URL` no `.env` para consulta rápida.
- **Prevenção de Duplicidade (Idempotência)**:
  - Registra o envio na tabela `cronograma_alert_history` do SQLite, garantindo que você nunca receba o mesmo alerta duas vezes no mesmo dia.


