# 🧹 Guia de Limpeza de URLs Processadas (`processed_urls`)

Este guia explica o propósito da tabela `processed_urls` do SQLite (`results.db`) e documenta os comandos equivalentes para limpar esse cache tanto no **ambiente Docker (container)** quanto **localmente**.

---

## 📌 Para que serve a tabela `processed_urls`?

Durante as varreduras de diários oficiais (DOM-CG, DOE-MS, DOU, AMEMS, Diário da Justiça, etc.), cada URL de edição ou documento já baixado e analisado para determinado nome é gravado em `processed_urls`.

* **Objetivo:** Evitar downloads repetidos e otimizar tempo e recursos.
* **Quando limpar:** Se você precisar forçar o robô a **reler todos os diários oficiais desde o início**, basta truncar/limpar essa tabela. As ocorrências já encontradas (`occurrences`) permanecerão preservadas.

---

## 🐳 1. Executando no Docker (Quando a aplicação estiver rodando)

> **⚠️ Atenção:** Para executar comandos dentro do container, certifique-se de que a aplicação está iniciada (ex: via `./00-iniciar.sh` no seu computador ou no servidor). Caso o container esteja parado, utilize a opção **Local (Host)** descrita na seção 2 ou o comando `docker run` descartável.

### Opção A: Com o container já em execução (`verifica-diarios-app`)
```bash
docker exec -it verifica-diarios-app python3 -c "import sqlite3; conn = sqlite3.connect('data/results.db'); conn.cursor().execute('DELETE FROM processed_urls'); conn.commit(); print('✅ processed_urls limpo com sucesso no container!'); conn.close()"
```

### Opção B: Com o container parado (utilizando docker compose run)
Caso a aplicação esteja desligada, você pode executar o comando sem precisar subir o servidor web:
```bash
docker compose run --rm app python3 -c "from src.database.db import get_connection; conn = get_connection(); conn.cursor().execute('DELETE FROM processed_urls'); conn.commit(); print('✅ processed_urls limpo com sucesso!'); conn.close()"
```

---

## 🖥️ 2. Executando Localmente no Host (Mais Rápido e Direto)

Como o banco SQLite é persistido diretamente no arquivo local `./data/results.db` da sua máquina, **não é obrigatório usar o Docker** para limpar essa tabela. Você pode rodar diretamente no seu terminal:

### A. Limpar todas as URLs processadas (Reset de Leitura)
```bash
python3 -c "from src.database.db import get_connection; conn = get_connection(); conn.cursor().execute('DELETE FROM processed_urls'); conn.commit(); print('✅ processed_urls limpo com sucesso!'); conn.close()"
```

### B. Consultar quantas URLs estão registradas
```bash
python3 -c "from src.database.db import get_connection; conn = get_connection(); print('Total registrado:', conn.cursor().execute('SELECT COUNT(*) FROM processed_urls').fetchone()[0]); conn.close()"
```

---

## ☁️ 3. No Mini PC / Homelab (Servidor Remoto)

Caso a stack esteja rodando no servidor Mini PC (Dockge/Homelab):

### A. Consultar quantas URLs estão registradas no servidor
```bash
ssh "${HOMELAB_USER}@${HOMELAB_HOST}" "docker exec verifica-diarios-app python3 -c \"import sqlite3; conn = sqlite3.connect('data/results.db'); print('Total registrado no servidor:', conn.cursor().execute('SELECT COUNT(*) FROM processed_urls').fetchone()[0]); conn.close()\""
```

### B. Limpar todas as URLs processadas no servidor (Reset de Leitura)
```bash
ssh "${HOMELAB_USER}@${HOMELAB_HOST}" "docker exec verifica-diarios-app python3 -c \"import sqlite3; conn = sqlite3.connect('data/results.db'); conn.cursor().execute('DELETE FROM processed_urls'); conn.commit(); print('✅ processed_urls limpo no servidor!'); conn.close()\""
```

