# 🚀 Guia de Deploy no Homelab / Mini PC (Dockge)

Este guia documenta o fluxo automatizado de deploy do **Verifica Nomes em Diários Oficiais & Central de Editais** no homelab Mini PC (`192.168.0.8`) gerenciado pelo Dockge/docker-compose.

---

## 🔑 Autenticação SSH Passwordless (Sem Senha)

O deploy é projetado para rodar de ponta a ponta sem qualquer solicitação interativa de senha. Para isso, são utilizados dois pilares:

1. **Chave SSH Ed25519**:
   - Chave pública/privada configurada em `~/.ssh/id_ed25519`.
   - O script [`00-iniciar.sh`](../../00-iniciar.sh) injeta automaticamente:
     ```bash
     -o BatchMode=yes -o PreferredAuthentications=publickey -i ~/.ssh/id_ed25519
     ```
     impedindo que o SSH solicite senha interativa caso a autenticação falhe.

2. **Permissões de Docker no Servidor (`umbrel`)**:
   - O usuário `umbrel` no servidor remoto faz parte do grupo `docker` (`usermod -aG docker umbrel`), permitindo invocar `docker compose` sem exigir elevação com `sudo` ou senhas de superusuário.

---

## ⚙️ Variáveis de Ambiente de Deploy (`.env`)

No arquivo `.env` do projeto local:

```env
# DEPLOY NO HOMELAB / MINI PC (DOCKGE)
HOMELAB_HOST=192.168.0.8
HOMELAB_USER=umbrel
HOMELAB_PORT=22
HOMELAB_DEST_DIR=/home/umbrel/umbrelos-scripts/compose/verifica-nomes-diarios-oficiais
HOMELAB_SSH_KEY=~/.ssh/id_ed25519
HOMELAB_PORT_APP=8093
```

---

## 🚀 Como Executar o Deploy

1. Abra o inicializador interativo no terminal:
   ```bash
   ./00-iniciar.sh
   ```
2. Escolha a opção correspondente ao deploy no Homelab / Mini PC.
3. O pipeline executa 5 passos de forma transparente:
   - **[1/5]** Teste de conectividade com o servidor (`ping`);
   - **[2/5]** Garantia dos diretórios remotos de persistência (`data`, `logs`, `uploads`);
   - **[3/5]** Sincronização incremental do código-fonte via `rsync` através do túnel SSH autenticado;
   - **[4/5]** Transferência e ajuste das variáveis de produção (`.env`) e do stack compose oficial (`docker-compose.server.yml`);
   - **[5/5]** Build e reinicialização dos containers via `docker compose up -d --build app`.

---

## 🌐 URLs de Acesso no Homelab

- **Domínio Local HTTPS (com SSL Wildcard):** [https://diarios.pk.local/](https://diarios.pk.local/)
- **Acesso Direto por IP:** [http://192.168.0.8:8093](http://192.168.0.8:8093)
- **Painel Dockge:** [http://192.168.0.8:5001](http://192.168.0.8:5001)
- **Nginx Proxy Manager:** [http://192.168.0.8:81](http://192.168.0.8:81)

---

## 🔌 Integração de Rede Docker (`homelab_network`)

Para que o **Nginx Proxy Manager** (OpenResty) consiga resolver e encaminhar requisições diretamente para o container `verifica-diarios-app` sem erro **502 Bad Gateway**, a stack do servidor conecta-se à rede externa `homelab_network` no [`docker-compose.server.yml`](../../docker-compose.server.yml):

```yaml
networks:
  default:
    name: homelab_network
    external: true
```

Dessa forma, o proxy reverso do NPM comunica-se diretamente pelo hostname interno `verifica-diarios-app:8093`.

