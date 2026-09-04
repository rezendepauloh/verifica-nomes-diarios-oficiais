@echo off
setlocal enabledelayedexpansion
title Verificador de Diários Oficiais - Docker Manager
cd /d "%~dp0"

:: Verificar parametro CLI
if /i "%~1"=="--start" goto :start_app
if /i "%~1"=="-s" goto :start_app
if /i "%~1"=="--run" goto :start_app
if /i "%~1"=="--scan" goto :run_scan_manual
if /i "%~1"=="--logs" goto :view_logs
if /i "%~1"=="-l" goto :view_logs
if /i "%~1"=="--rebuild" goto :rebuild_docker
if /i "%~1"=="-r" goto :rebuild_docker
if /i "%~1"=="--down" goto :stop_system
if /i "%~1"=="--stop" goto :stop_system
if /i "%~1"=="-d" goto :stop_system
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h" goto :show_help

:show_menu
cls
echo ================================================================
echo       VERIFICADOR DE DIARIOS OFICIAIS -- DOCKER MANAGER         
echo ================================================================
echo.
echo   Escolha uma opcao:
echo   1 - Iniciar Aplicacao (Docker Compose + Streamlit)
echo   2 - Disparar varredura manual (run_scan.py)
echo   3 - Ver logs do container em tempo real
echo   4 - Reconstruir Docker Compose (--no-cache)
echo   5 - Parar sistema (docker compose down)
echo   0 - Sair
echo.
echo ================================================================
set /p "OPCAO=Opcao [0-5]: "

if "%OPCAO%"=="1" goto :start_app
if "%OPCAO%"=="2" goto :run_scan_manual
if "%OPCAO%"=="3" goto :view_logs
if "%OPCAO%"=="4" goto :rebuild_docker
if "%OPCAO%"=="5" goto :stop_system
if "%OPCAO%"=="0" exit /b 0

echo Opcao invalida.
timeout /t 1 >nul
goto :show_menu

:setup_docker_and_env
set "PORT="
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%i in (".env") do (
        set "KEY=%%i"
        set "VAL=%%j"
        if not "!KEY!"=="" (
            for /f "tokens=* delims= " %%k in ("!KEY!") do set "KEY=%%k"
            if "!KEY!"=="PORT" (
                for /f "tokens=* delims= " %%v in ("!VAL!") do set "PORT=%%v"
            )
        )
    )
)

if "%PORT%"=="" (
    echo [ERRO] Variavel PORT nao encontrada no arquivo .env!
    pause
    exit /b 1
)
set "PORT=%PORT: =%"

where docker >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "DOCKER_CMD=docker compose"
) else (
    where wsl >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "DOCKER_CMD=wsl.exe docker compose"
    ) else (
        echo [ERRO] Nem o Docker Desktop nem o WSL foram encontrados.
        echo Instale ou inicie o Docker Desktop para continuar.
        pause
        exit /b 1
    )
)
exit /b 0

:start_app
call :setup_docker_and_env
cls
echo Iniciando Verificador de Diarios Oficiais (Porta: %PORT%)...
%DOCKER_CMD% up -d --build
if %ERRORLEVEL% neq 0 (
    echo [ERRO] Falha ao iniciar containers do Docker.
    pause
    exit /b %ERRORLEVEL%
)
timeout /t 2 /nobreak >nul
start http://localhost:%PORT%
goto :stream_logs

:run_scan_manual
call :setup_docker_and_env
cls
echo Disparando varredura manual no container...
%DOCKER_CMD% up -d app >nul 2>nul
%DOCKER_CMD% exec app python src/run_scan.py
echo.
echo Varredura manual finalizada!
pause
goto :show_menu

:view_logs
call :setup_docker_and_env
cls
goto :stream_logs

:stream_logs
cls
echo ---------------------------------------------------------------------------------
echo  [C] Limpar Logs  ^|  [S] Varredura  ^|  [R] Reiniciar App  ^|  [B] Navegador  ^|  [Q] Encerrar
echo ---------------------------------------------------------------------------------
%DOCKER_CMD% logs -f --tail=100 app
echo.
echo Encerrando containers...
%DOCKER_CMD% down
exit /b 0

:rebuild_docker
call :setup_docker_and_env
cls
echo Reconstruindo imagem Docker Compose (--no-cache)...
%DOCKER_CMD% build --no-cache
echo.
echo Rebuild concluido com sucesso!
pause
goto :show_menu

:stop_system
call :setup_docker_and_env
echo Encerrando todos os containers do Verificador de Diarios...
%DOCKER_CMD% down
echo Containers encerrados com sucesso!
pause
exit /b 0

:show_help
echo Uso: 00-iniciar.cmd [OPCAO]
echo.
echo Opcoes:
echo   --start, -s              Inicia a aplicacao via Docker Compose
echo   --scan                   Dispara uma varredura manual
echo   --logs, -l               Exibe os logs do container
echo   --rebuild, -r            Reconstroi a imagem Docker (--no-cache)
echo   --down, -d               Para os containers do sistema
echo   --help, -h               Exibe esta ajuda
echo   (sem argumentos)         Abre o menu interativo
exit /b 0