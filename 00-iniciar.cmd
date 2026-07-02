@echo off
echo Iniciando o verificador de nomes...
call .venv\Scripts\activate
streamlit run app.py --server.port 8503
pause