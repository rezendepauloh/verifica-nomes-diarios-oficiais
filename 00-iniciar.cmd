@echo off
echo ========================================================
echo   Iniciando Verificador de Diários Oficiais via Docker
echo ========================================================
echo.

if not exist .env (
    echo.
    echo [ERRO] Arquivo .env nao encontrado! Crie o arquivo .env com a variavel PORT.
    pause
    exit /b 1
)

for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if /i "%%A"=="PORT" set PORT=%%B
)

if "%PORT%"=="" (
    echo.
    echo [ERRO] Variavel PORT nao encontrada no arquivo .env!
    pause
    exit /b 1
)

docker compose up -d --build

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERRO] Falha ao iniciar containers do Docker. Verifique se o Docker Desktop esta em execucao.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo Abrindo o navegador na porta %PORT%...
start http://localhost:%PORT%

echo.
echo Exibindo logs da aplicacao (Pressione Ctrl+C para sair dos logs sem parar o container)...
docker compose logs -f --tail=50 app