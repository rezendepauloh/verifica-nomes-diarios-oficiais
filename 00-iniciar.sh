#!/usr/bin/env bash
# =======================================================================
#       VERIFICADOR DE DIÁRIOS OFICIAIS — CLI UNIFICADO (DOCKER)
# =======================================================================

cd "$(dirname "$0")" || exit 1

# Paleta de Cores ANSI
C_RESET="\033[0m"
C_BOLD="\033[1m"
C_CYAN="\033[36m"
C_GREEN="\033[32m"
C_YELLOW="\033[33m"
C_RED="\033[31m"
C_MAGENTA="\033[35m"
C_GRAY="\033[90m"

enforce_local_permissions() {
    [ -f .env ] && chmod 600 .env 2>/dev/null || true
    [ -d data ] && chmod 700 data 2>/dev/null || true
    [ -f data/results.db ] && chmod 600 data/results.db 2>/dev/null || true
}

detect_ip() {
    LOCAL_IP="127.0.0.1"
    export HOST_LOCAL_IP="${LOCAL_IP}"
}

load_env_file() {
    if [ ! -f .env ]; then
        echo -e "${C_RED}❌ Erro [Fail-Closed]: Arquivo .env não encontrado! Copie .env-example para .env e configure as variáveis obrigatórias.${C_RESET}"
        exit 1
    fi

    enforce_local_permissions

    local env_port
    env_port=$(grep -E '^[[:space:]]*PORT[[:space:]]*=' .env | tail -n 1 | cut -d '=' -f 2 | tr -d ' "\047\r\n')
    if [[ ! "$env_port" =~ ^[0-9]{2,5}$ ]] || [ "$env_port" -lt 1 ] || [ "$env_port" -gt 65535 ]; then
        echo -e "${C_RED}❌ Erro [Fail-Closed]: Variável PORT ausente ou inválida no arquivo .env!${C_RESET}"
        exit 1
    fi
    PORT="$env_port"
}

open_browser() {
    local port="${1:-$PORT}"
    if [[ ! "$port" =~ ^[0-9]{2,5}$ ]]; then
        return 1
    fi
    local url="http://127.0.0.1:${port}"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    elif command -v gnome-open >/dev/null 2>&1; then
        gnome-open "$url" >/dev/null 2>&1 &
    fi
}

cleanup() {
    trap - INT TERM EXIT
    tput cnorm 2>/dev/null
    local rows
    rows=$(tput lines 2>/dev/null || echo 24)
    printf "\033[1;%dr" "$rows" 2>/dev/null
    printf "\033[%d;1H\n" "$rows" 2>/dev/null

    echo ""
    echo -e "${C_YELLOW}Encerrando containers do Verificador de Diários...${C_RESET}"
    docker compose down
    echo -e "${C_GREEN}[OK] Containers finalizados com sucesso.${C_RESET}"
    exit 0
}

# Desenha a barra fixa no rodapé da janela do terminal
render_bottom_toolbar() {
    local rows
    rows=$(tput lines 2>/dev/null || echo 24)
    local cols
    cols=$(tput cols 2>/dev/null || echo 80)
    local sep_len=$(( cols - 2 ))
    [ $sep_len -lt 10 ] && sep_len=70

    tput sc 2>/dev/null
    printf "\033[%d;1H" $(( rows - 1 ))
    echo -ne "${C_GRAY}─${C_RESET}"
    printf "${C_GRAY}%%0.s─${C_RESET}" $(seq 1 $sep_len)
    printf "\033[K\n"
    printf " ${C_BOLD}[c]${C_RESET} ${C_YELLOW}Limpar Logs${C_RESET} | ${C_BOLD}[s]${C_RESET} ${C_CYAN}Varredura${C_RESET} | ${C_BOLD}[r]${C_RESET} ${C_MAGENTA}Reiniciar App${C_RESET} | ${C_BOLD}[b]${C_RESET} ${C_GREEN}Navegador${C_RESET} | ${C_BOLD}[q]${C_RESET} ${C_RED}Encerrar${C_RESET}\033[K"
    tput rc 2>/dev/null
}

setup_terminal_split() {
    local rows
    rows=$(tput lines 2>/dev/null || echo 24)
    printf "\033[1;%dr" $(( rows - 2 )) 2>/dev/null
    render_bottom_toolbar
}

stream_interactive_logs() {
    local LOG_PID=""

    setup_terminal_split
    trap 'setup_terminal_split' WINCH

    docker compose logs -f --tail=100 app &
    LOG_PID=$!

    while kill -0 "$LOG_PID" 2>/dev/null; do
        if read -r -s -n 1 -t 1 key; then
            case "$key" in
                c|C)
                    clear
                    setup_terminal_split
                    ;;
                s|S)
                    kill "$LOG_PID" 2>/dev/null
                    local rows
                    rows=$(tput lines 2>/dev/null || echo 24)
                    printf "\033[1;%dr" "$rows" 2>/dev/null
                    clear
                    echo -e "${C_CYAN}Disparando varredura manual no container...${C_RESET}"
                    docker compose exec app python src/run_scan.py
                    echo ""
                    echo -e "${C_GREEN}Varredura concluída! Retornando aos logs em 3s...${C_RESET}"
                    sleep 3
                    clear
                    setup_terminal_split
                    docker compose logs -f --tail=50 app &
                    LOG_PID=$!
                    ;;
                r|R)
                    kill "$LOG_PID" 2>/dev/null
                    clear
                    echo -e "${C_YELLOW}Reiniciando serviço da aplicação...${C_RESET}"
                    docker compose restart app
                    clear
                    setup_terminal_split
                    docker compose logs -f --tail=50 app &
                    LOG_PID=$!
                    ;;
                b|B)
                    open_browser "$PORT"
                    ;;
                q|Q)
                    kill "$LOG_PID" 2>/dev/null
                    cleanup
                    ;;
            esac
        fi
    done

    wait "$LOG_PID" 2>/dev/null
}

check_auto_build() {
    local HASH_FILE=".docker_build_hash"
    local CURRENT_HASH
    CURRENT_HASH=$(cat Dockerfile requirements.txt 2>/dev/null | sha256sum | awk '{print $1}')
    local BUILD_FLAG=""

    if [ ! -f "$HASH_FILE" ] || [ "$(cat "$HASH_FILE" 2>/dev/null)" != "$CURRENT_HASH" ]; then
        echo -e "${C_YELLOW}⚙️  Detectada alteração na configuração do Docker ou primeira execução. Atualizando imagem...${C_RESET}"
        BUILD_FLAG="--build"
    fi

    docker compose up -d $BUILD_FLAG
    if [ $? -eq 0 ] && [ -n "$CURRENT_HASH" ]; then
        echo "$CURRENT_HASH" > "$HASH_FILE"
    fi
}

start_app() {
    load_env_file
    detect_ip
    clear
    echo -e "${C_CYAN}Iniciando Verificador de Diários Oficiais (127.0.0.1:${PORT})...${C_RESET}"
    check_auto_build
    open_browser "$PORT"
    trap cleanup INT TERM EXIT
    stream_interactive_logs
}

run_scan_manual() {
    load_env_file
    clear
    echo -e "${C_CYAN}Disparando varredura completa manual no container...${C_RESET}"
    docker compose up -d app >/dev/null 2>&1
    docker compose exec app python src/run_scan.py
    echo ""
    echo -e "${C_GREEN}Varredura manual finalizada!${C_RESET}"
}

rebuild_docker() {
    load_env_file
    clear
    echo -e "${C_MAGENTA}Reconstruindo imagem Docker Compose (--no-cache)...${C_RESET}"
    docker compose build --no-cache
    local HASH_FILE=".docker_build_hash"
    local CURRENT_HASH
    CURRENT_HASH=$(cat Dockerfile requirements.txt 2>/dev/null | sha256sum | awk '{print $1}')
    if [ -n "$CURRENT_HASH" ]; then
        echo "$CURRENT_HASH" > "$HASH_FILE"
    fi
    echo ""
    echo -e "${C_GREEN}Rebuild concluído!${C_RESET}"
}

view_logs() {
    load_env_file
    clear
    trap cleanup INT TERM EXIT
    stream_interactive_logs
}

stop_system() {
    echo -e "${C_YELLOW}Encerrando todos os containers...${C_RESET}"
    docker compose down
    echo -e "${C_GREEN}Containers encerrados com sucesso!${C_RESET}"
}

deploy_homelab() {
    load_env_file
    if [ -f .env ]; then
        set -a
        # shellcheck disable=SC1091
        source .env
        set +a
    fi
    clear
    echo -e "${C_CYAN}${C_BOLD}🚀 Início do Pipeline de Deploy no Homelab / Mini PC (Dockge)${C_RESET}"
    echo ""

    # Trava Fail-Closed: NUNCA usar defaults hardcoded de IPs, usuários ou diretórios
    local HOST="${HOMELAB_HOST:-}"
    local USER="${HOMELAB_USER:-}"
    local PORT_SSH="${HOMELAB_PORT:-}"
    local DEST_DIR="${HOMELAB_DEST_DIR:-}"
    local SERVER_APP_PORT="${HOMELAB_PORT_APP:-}"
    local SSH_KEY="${HOMELAB_SSH_KEY:-$HOME/.ssh/id_ed25519}"
    SSH_KEY="${SSH_KEY/#\~/$HOME}"

    if [ -z "$HOST" ] || [ -z "$USER" ] || [ -z "$PORT_SSH" ] || [ -z "$DEST_DIR" ] || [ -z "$SERVER_APP_PORT" ]; then
        echo -e "${C_RED}❌ Erro [Fail-Closed]: Variáveis HOMELAB_HOST, HOMELAB_USER, HOMELAB_PORT, HOMELAB_DEST_DIR e HOMELAB_PORT_APP são obrigatórias no .env!${C_RESET}"
        return 1
    fi

    # Whitelists Regex Estritas contra Command Injection
    if [[ ! "$HOST" =~ ^[a-zA-Z0-9._-]+$ ]]; then
        echo -e "${C_RED}❌ Erro [Fail-Closed]: HOMELAB_HOST contém caracteres inválidos!${C_RESET}"
        return 1
    fi
    if [[ ! "$USER" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo -e "${C_RED}❌ Erro [Fail-Closed]: HOMELAB_USER contém caracteres inválidos!${C_RESET}"
        return 1
    fi
    if [[ ! "$PORT_SSH" =~ ^[0-9]{2,5}$ ]] || [[ ! "$SERVER_APP_PORT" =~ ^[0-9]{2,5}$ ]]; then
        echo -e "${C_RED}❌ Erro [Fail-Closed]: HOMELAB_PORT / HOMELAB_PORT_APP devem ser numéricas!${C_RESET}"
        return 1
    fi
    if [[ ! "$DEST_DIR" =~ ^/[a-zA-Z0-9._/-]+$ ]] || [[ "$DEST_DIR" == *".."* ]]; then
        echo -e "${C_RED}❌ Erro [Fail-Closed]: HOMELAB_DEST_DIR inválido ou contém sequência '..' proibida!${C_RESET}"
        return 1
    fi

    local SSH_OPTS=("-p" "${PORT_SSH}" "-o" "StrictHostKeyChecking=accept-new" "-o" "BatchMode=yes" "-o" "PreferredAuthentications=publickey")
    local SCP_OPTS=("-P" "${PORT_SSH}" "-o" "StrictHostKeyChecking=accept-new" "-o" "BatchMode=yes" "-o" "PreferredAuthentications=publickey")
    if [ -f "$SSH_KEY" ]; then
        chmod 600 "$SSH_KEY" 2>/dev/null || true
        SSH_OPTS+=("-i" "$SSH_KEY")
        SCP_OPTS+=("-i" "$SSH_KEY")
    fi

    # 1. Testar conectividade (Ping)
    echo -e "${C_YELLOW}[1/5] Verificando conectividade com o servidor (${HOST})...${C_RESET}"
    if ! ping -c 1 -W 2 "$HOST" >/dev/null 2>&1; then
        echo -e "${C_RED}❌ Não foi possível alcançar ${HOST}. Verifique se o servidor está ligado e acessível.${C_RESET}"
        return 1
    fi
    echo -e "${C_GREEN}✅ Servidor ${HOST} respondendo perfeitamente!${C_RESET}"
    echo ""

    # 2. Criar diretório remoto se não existir com permissões restritivas (700/750, NUNCA 777)
    echo -e "${C_YELLOW}[2/5] Garantindo diretório da stack no servidor (${DEST_DIR})...${C_RESET}"
    ssh "${SSH_OPTS[@]}" "${USER}@${HOST}" "mkdir -p '${DEST_DIR}/data' '${DEST_DIR}/logs' '${DEST_DIR}/uploads' && chmod 700 '${DEST_DIR}/data' '${DEST_DIR}/logs' '${DEST_DIR}/uploads' '${DEST_DIR}'"
    if [ $? -ne 0 ]; then
        echo -e "${C_RED}❌ Falha na comunicação SSH com ${USER}@${HOST}.${C_RESET}"
        return 1
    fi
    echo -e "${C_GREEN}✅ Diretório e permissões restritivas (0700) aplicados com sucesso!${C_RESET}"
    echo ""

    # 3. Sincronizar arquivos via Rsync (com exclusões seguras)
    echo -e "${C_YELLOW}[3/5] Enviando código-fonte e assets via rsync...${C_RESET}"
    rsync -avz \
        -e "ssh ${SSH_OPTS[*]}" \
        --exclude '.git' \
        --exclude '.venv' \
        --exclude '__pycache__' \
        --exclude '.docker_build_hash' \
        --exclude 'logs' \
        --exclude 'uploads' \
        --exclude 'data' \
        --exclude '.env' \
        --exclude 'docker-compose.yml' \
        --exclude 'docker-compose.server.yml' \
        --exclude 'results.db' \
        ./ "${USER}@${HOST}:${DEST_DIR}/"

    if [ $? -ne 0 ]; then
        echo -e "${C_RED}❌ Erro durante a transferência rsync.${C_RESET}"
        return 1
    fi
    echo -e "${C_GREEN}✅ Código-fonte sincronizado com sucesso!${C_RESET}"
    echo ""

    # 4. Configurar docker-compose.yml e .env de produção no servidor com mktemp seguro (0600)
    echo -e "${C_YELLOW}[4/5] Configurando docker-compose e .env de produção no servidor...${C_RESET}"
    local TEMP_PROD_ENV
    TEMP_PROD_ENV=$(umask 077 && mktemp /tmp/diarios_prod_env.XXXXXX)
    if [ -z "$TEMP_PROD_ENV" ] || [ ! -f "$TEMP_PROD_ENV" ]; then
        echo -e "${C_RED}❌ Erro ao criar arquivo temporário seguro com mktemp.${C_RESET}"
        return 1
    fi
    chmod 600 "$TEMP_PROD_ENV"
    cp .env "$TEMP_PROD_ENV"

    if grep -q '^PORT=' "$TEMP_PROD_ENV"; then
        sed -i "s/^PORT=.*/PORT=${SERVER_APP_PORT}/" "$TEMP_PROD_ENV"
    else
        echo "PORT=${SERVER_APP_PORT}" >> "$TEMP_PROD_ENV"
    fi

    scp "${SCP_OPTS[@]}" "$TEMP_PROD_ENV" "${USER}@${HOST}:${DEST_DIR}/.env"
    local SCP_STATUS=$?
    rm -f "$TEMP_PROD_ENV"
    if [ $SCP_STATUS -ne 0 ]; then
        echo -e "${C_RED}❌ Falha ao transferir arquivo .env para o servidor.${C_RESET}"
        return 1
    fi

    ssh "${SSH_OPTS[@]}" "${USER}@${HOST}" "chmod 600 '${DEST_DIR}/.env'"

    if [ -f "docker-compose.server.yml" ]; then
        scp "${SCP_OPTS[@]}" "docker-compose.server.yml" "${USER}@${HOST}:${DEST_DIR}/docker-compose.yml"
    else
        echo -e "${C_RED}❌ Arquivo docker-compose.server.yml não encontrado!${C_RESET}"
        return 1
    fi
    echo -e "${C_GREEN}✅ Arquivos de ambiente (.env 0600) e stack compose configurados!${C_RESET}"
    echo ""

    # 5. Executar Build e Up no Docker do servidor
    echo -e "${C_YELLOW}[5/5] Reiniciando aplicação com a nova build no servidor...${C_RESET}"
    ssh "${SSH_OPTS[@]}" "${USER}@${HOST}" "cd '${DEST_DIR}' && docker compose up -d --build app"

    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${C_GREEN}${C_BOLD}🎉 DEPLOY CONCLUÍDO COM SUCESSO NO HOMELAB!${C_RESET}"
        [ -n "${APP_LOCAL_URL:-}" ] && echo -e "Acesse pelo Domínio Local: ${C_CYAN}${APP_LOCAL_URL}${C_RESET}"
        echo -e "Bind Local Seguro (Host):  ${C_CYAN}http://127.0.0.1:${SERVER_APP_PORT}${C_RESET}"
    else
        echo -e "${C_RED}❌ Ocorreu um erro ao iniciar a stack no servidor remoto.${C_RESET}"
    fi
    echo ""
    read -r -p "Pressione [Enter] para voltar ao menu..."
}

run_unit_tests() {
    echo -e "${C_CYAN}🧪 Executando suíte de testes unificada...${C_RESET}"
    docker exec -it verifica-diarios-app python tests/run_all.py || docker exec -it verifica-diarios-app pytest -v tests/
    echo ""
    read -r -p "Pressione [Enter] para voltar ao menu..."
}

show_menu() {
    clear
    echo -e "${C_CYAN}${C_BOLD}╔══════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║      VERIFICADOR DE DIÁRIOS OFICIAIS — DOCKER MANAGER        ║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║                                                              ║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_BOLD}Escolha uma opção:${C_RESET}                                          ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}1${C_RESET} - Iniciar Aplicação (Docker Compose + Streamlit)          ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}2${C_RESET} - Disparar varredura manual (run_scan.py)                 ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}3${C_RESET} - Ver logs do container em tempo real                     ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}4${C_RESET} - Reconstruir Docker Compose (--no-cache)                 ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}5${C_RESET} - Parar sistema (docker compose down)                     ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_MAGENTA}6${C_RESET} - 🚀 Deploy no Mini PC (Dockge / Homelab)                 ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_YELLOW}7${C_RESET} - 🧪 Executar Testes Unitários (pytest)                   ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_RED}0${C_RESET} - Sair                                                    ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}╚══════════════════════════════════════════════════════════════╝${C_RESET}"
    echo ""
    read -r -p "Opção [0-7]: " opcao
    case "$opcao" in
        1) start_app ;;
        2) run_scan_manual ;;
        3) view_logs ;;
        4) rebuild_docker ;;
        5) stop_system ;;
        6) deploy_homelab ;;
        7) run_unit_tests ;;
        0) exit 0 ;;
        *) echo -e "${C_RED}Opção inválida.${C_RESET}"; sleep 1; show_menu ;;
    esac
}

case "$1" in
    --start|-s|--run)
        start_app
        ;;
    --scan)
        run_scan_manual
        ;;
    --logs|-l)
        view_logs
        ;;
    --rebuild|-r)
        rebuild_docker
        ;;
    --down|--stop)
        stop_system
        ;;
    --deploy|-dp)
        deploy_homelab
        ;;
    --test|-t)
        docker exec -t verifica-diarios-app python tests/run_all.py || docker exec -t verifica-diarios-app pytest -v tests/
        ;;
    --help|-h)
        echo "Uso: ./00-iniciar.sh [OPÇÃO]"
        echo ""
        echo "Opções:"
        echo "  --start, -s              Inicia a aplicação Streamlit via Docker"
        echo "  --scan                   Dispara uma varredura manual via container"
        echo "  --logs, -l               Exibe os logs do container"
        echo "  --rebuild, -r            Reconstrói a imagem Docker (--no-cache)"
        echo "  --down, --stop           Para os containers do sistema"
        echo "  --deploy, -dp            Executa deploy no Mini PC (Dockge / Homelab)"
        echo "  --test, -t               Executa a suíte de testes unitários com pytest"
        echo "  --help, -h               Exibe esta ajuda"
        echo "  (sem argumentos)         Abre o menu interativo"
        ;;
    *)
        show_menu
        ;;
esac
