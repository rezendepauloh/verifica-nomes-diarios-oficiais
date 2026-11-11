# 📖 Guia da Central de Editais e Planejamento de Concursos

A **Central de Editais** é o módulo do sistema voltado para centralizar, estruturar e acompanhar concursos públicos para **Paulo** e **Kamila**.

---

## 1. Cadastro de Concursos e Upload de PDFs

### Passos:
1. Acesse a aba **`📚 Editais & Concursos`**.
2. Na barra lateral, clique no botão azul **`➕ Novo Edital (Upload)`**.
3. Preencha as informações:
   - **Título / Órgão do Concurso**: Ex: `UFMS`, `CGU`, `TJMS`.
   - **Cargo Desejado**: Ex: `Professor Visitante - INBIO`, `Auditor Federal`.
   - **Banca Organizadora**: Ex: `FAPEC`, `Cebraspe`, `FGV`.
   - **Ano**: Ex: `2026`.
   - **Candidato(a)**: `Paulo`, `Kamila` ou `Ambos`.
   - **Link Oficial da Página do Concurso / Editais**: URL onde são publicadas as retificações e comunicados.
   - **Link Direto de Inscrição (Opcional)**: URL direta da plataforma de inscrições dos candidatos.
   - **Arquivos do Edital (.pdf)**: Permite enviar **múltiplos PDFs de uma vez** (o 1º arquivo será o edital geral mestre, e os demais serão vinculados como editais específicos da área / anexos).
4. **Auto-Descoberta de Cargos**: O sistema analisa o PDF principal e lista os cargos detectados no documento para você escolher o seu foco.
5. Clique em **`💾 Salvar e Processar Edital`**. O extrator analisa o cronograma de datas e as disciplinas de forma automática.

---

## 2. Edição de Concursos Cadastrados (`✏️ Editar Concurso`)

Caso precise atualizar informações de um concurso já cadastrado (como links, cargo, banca ou status):
1. Selecione o concurso desejado no menu lateral.
2. Clique no botão **`✏️ Editar Concurso`** (disponível no menu lateral e acima dos cards de detalhes).
3. Ajuste os campos desejados e clique em **`💾 Salvar Alterações`**.

---

## 3. Navegação pelas Sub-Abas Internas

Quando um concurso é selecionado, a aplicação disponibiliza 4 subtabs integradas:

### 📅 1. Cronograma & Prazos
- Tabela interativa moderna renderizada em HTML nativo com tema escuro.
- **Cálculo em Tempo Real da Situação**:
  - ⚪ `Concluído`: Prazos que já se encerraram.
  - 🟢 `Em Andamento`: Períodos que estão ativos no dia de hoje.
  - ⚡ `Hoje`: Eventos pontuais com término na data atual.
  - 🔵 `Previsto`: Datas futuras.
- **Recursos da Tabela**:
  - Ordenação dinâmica por colunas (ascendente/descendente com parsing cronológico).
  - Redimensionamento livre de colunas (arrastar a borda da coluna).
  - Botões de atalho **`[+ Adicionar]`**, **`[Início]`** e **`[Fim]`** para criar eventos individuais diretamente no Google Agenda web com apenas um clique.
- **Menu Lateral Exclusivo**:
  - Botão **`📅 Exportar (.ics Google)`** para baixar o calendário de eventos formatado no padrão RFC-5545 para importar na agenda "Concursos".
  - Botão **`🔄 Reextrair Localmente`** caso deseje forçar reextração do arquivo base.

### 🎯 2. Edital Verticalizado & Checklist de Estudos
- Tabela completa de matérias, disciplinas e tópicos extraídos do anexo de conteúdo programático.
- **Checklist Interativo**:
  - 📖 **Teoria** (checkbox)
  - 📝 **Resumo** (checkbox)
  - ❓ **Questões** (checkbox)
  - 🔁 **Rev 1** (checkbox de 1ª revisão)
- **Cards de Métricas em Tempo Real**:
  - Total de Tópicos do cargo.
  - Teoria Estudada (% concluído).
  - Questões Feitas (% praticado).
  - Resumos Concluídos.
- **Filtro por Disciplina no Menu Lateral**: Selecione uma disciplina específica (ex: *Direito Constitucional*, *Auditoria Governamental*) para focar nos estudos sem rolagem excessiva.
- **Exportação CSV**: Botão no menu lateral para baixar a planilha formatada.

### 📖 3. Leitor do PDF Embutido
- Visualizador com alta fidelidade visual, integrado na interface sem sair do sistema.
- **Seletor de Documentos no Menu Lateral**:
  - Permite alternar entre o **Edital Original** e quaisquer **Editais de Retificação / Comunicados** anexados ao concurso.
  - O título completo do documento selecionado é exibido em destaque no topo da página.
- **Modo Maximizar Janela (`⛶ Maximizar Janela`)**:
  - Botão flutuante que expande o PDF para ocupar 100% da janela do navegador (`100vw` e `100vh`), mantendo o navegador e abas acessíveis.
  - Pressione a tecla **`ESC`** para restaurar o tamanho normal instantaneamente.

### ⚙️ 4. Ações & Reprocessamento
- Central de manutenção do concurso.
- Verificação de retificações na banca, upload manual de aditivos e reprocessamento com IA (Google Gemini).

