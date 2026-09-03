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

detect_ip() {
    LOCAL_IP=""
    if [ -f /proc/sys/fs/binfmt_misc/WSLInterop ] || [ -n "$WSL_DISTRO_NAME" ]; then
        WIN_IP=$(powershell.exe -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { (\$_.IPAddress -like '192.168.*' -or \$_.IPAddress -like '10.*') -and \$_.IPAddress -notlike '192.168.56.*' -and \$_.InterfaceAlias -notlike '*Virtual*' -and \$_.InterfaceAlias -notlike '*vEthernet*' } | Select-Object -ExpandProperty IPAddress -First 1)" 2>/dev/null | tr -d '\r\n')
        if [ -n "$WIN_IP" ]; then
            LOCAL_IP="$WIN_IP"
        fi
    fi

    if [ -z "$LOCAL_IP" ]; then
        if command -v hostname >/dev/null 2>&1; then
            LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
        fi

        if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" = "127.0.0.1" ]; then
            if command -v ip >/dev/null 2>&1; then
                LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+')
            fi
        fi
    fi

    if [ -z "$LOCAL_IP" ]; then
        LOCAL_IP="localhost"
    fi

    export HOST_LOCAL_IP="${LOCAL_IP}"
}

load_env_file() {
    if [ ! -f .env ]; then
        if [ -f .env-example ]; then
            echo -e "${C_YELLOW}⚠️  Arquivo .env não encontrado. Criando a partir de .env-example...${C_RESET}"
            cp .env-example .env
        else
            echo -e "${C_RED}❌ Erro: Arquivo .env não encontrado e .env-example não disponível.${C_RESET}"
            exit 1
        fi
    fi

    local env_port
    env_port=$(grep -E '^[[:space:]]*PORT[[:space:]]*=' .env | tail -n 1 | cut -d '=' -f 2 | tr -d ' "\r\n')
    if [ -z "$env_port" ]; then
        echo -e "${C_RED}❌ Erro: Variável PORT não configurada no arquivo .env!${C_RESET}"
        exit 1
    fi
    PORT="$env_port"
}


open_browser() {
    local port="${1:-$PORT}"
    local url="http://localhost:${port}"
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    elif command -v gnome-open >/dev/null 2>&1; then
        gnome-open "$url" >/dev/null 2>&1 &
    fi
}

cleanup() {
    trap - INT TERM EXIT
    echo ""
    echo -e "${C_YELLOW}Encerrando containers do Verificador de Diários...${C_RESET}"
    docker compose down
    exit 0
}

check_auto_build() {
    local HASH_FILE=".docker_build_hash"
    local CURRENT_HASH
    CURRENT_HASH=$(cat Dockerfile requirements.txt 2>/dev/null | md5sum | awk '{print $1}')
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
    echo -e "${C_CYAN}Iniciando Verificador de Diários Oficiais (Porta: ${PORT})...${C_RESET}"
    check_auto_build
    open_browser "$PORT"
    trap cleanup INT TERM EXIT
    docker compose logs -f --tail=50 app
}

run_scan_manual() {
    clear
    echo -e "${C_CYAN}Disparando varredura completa manual no container...${C_RESET}"
    docker compose up -d app >/dev/null 2>&1
    docker compose exec app python src/run_scan.py
    echo ""
    echo -e "${C_GREEN}Varredura manual finalizada!${C_RESET}"
}

rebuild_docker() {
    clear
    echo -e "${C_MAGENTA}Reconstruindo imagem Docker Compose (--no-cache)...${C_RESET}"
    docker compose build --no-cache
    local HASH_FILE=".docker_build_hash"
    local CURRENT_HASH
    CURRENT_HASH=$(cat Dockerfile requirements.txt 2>/dev/null | md5sum | awk '{print $1}')
    if [ -n "$CURRENT_HASH" ]; then
        echo "$CURRENT_HASH" > "$HASH_FILE"
    fi
    echo ""
    echo -e "${C_GREEN}Rebuild concluído!${C_RESET}"
}

view_logs() {
    clear
    echo -e "${C_CYAN}Exibindo logs em tempo real (Ctrl+C para sair)...${C_RESET}"
    docker compose logs -f --tail=100 app
}

stop_system() {
    echo -e "${C_YELLOW}Encerrando todos os containers...${C_RESET}"
    docker compose down
    echo -e "${C_GREEN}Containers encerrados com sucesso!${C_RESET}"
}

show_menu() {
    clear
    echo -e "${C_CYAN}${C_BOLD}╔══════════════════════════════════════════════════════════════╗${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║      VERIFICADOR DE DIÁRIOS OFICIAIS — DOCKER MANAGER       ║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║                                                              ║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_BOLD}Escolha uma opção:${C_RESET}                                          ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}1${C_RESET} - Iniciar Aplicação (Docker Compose + Streamlit)          ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}2${C_RESET} - Disparar varredura manual (run_scan.py)                 ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}3${C_RESET} - Ver logs do container em tempo real                     ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}4${C_RESET} - Reconstruir Docker Compose (--no-cache)                 ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_GREEN}5${C_RESET} - Parar sistema (docker compose down)                     ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}║${C_RESET}  ${C_RED}0${C_RESET} - Sair                                                    ${C_CYAN}${C_BOLD}║${C_RESET}"
    echo -e "${C_CYAN}${C_BOLD}╚══════════════════════════════════════════════════════════════╝${C_RESET}"
    echo ""
    read -p "Opção [0-5]: " opcao
    case "$opcao" in
        1) start_app ;;
        2) run_scan_manual ;;
        3) view_logs ;;
        4) rebuild_docker ;;
        5) stop_system ;;
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
    --help|-h)
        echo "Uso: ./00-iniciar.sh [OPÇÃO]"
        echo ""
        echo "Opções:"
        echo "  --start, -s              Inicia a aplicação Streamlit via Docker"
        echo "  --scan                   Dispara uma varredura manual via container"
        echo "  --logs, -l               Exibe os logs do container"
        echo "  --rebuild, -r            Reconstrói a imagem Docker (--no-cache)"
        echo "  --down, --stop           Para os containers do sistema"
        echo "  --help, -h               Exibe esta ajuda"
        echo "  (sem argumentos)         Abre o menu interativo"
        ;;
    *)
        show_menu
        ;;
esac
