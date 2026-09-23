@echo off
echo ===================================================
echo Iniciando entorno del Bot IA CxC...
echo ===================================================

echo [0/3] Limpiando procesos fantasma de sesiones anteriores...
timeout /t 1 /nobreak >nul

echo [1/3] Levantando FastAPI (bot_app.py)...
start "Servidor FastAPI" cmd /k ".\venv\Scripts\activate && python bot_app.py"
timeout /t 3 /nobreak >nul

echo [2/3] Levantando Cliente WhatsApp (whatsapp_client.js)...
start "Cliente WhatsApp" cmd /k "node whatsapp_client.js"
timeout /t 3 /nobreak >nul

echo [3/3] Levantando ETL SAP (etl_sap_to_sqlite.py)...
start "Sincronizador SAP ETL" cmd /k ".\venv\Scripts\activate && python etl_sap_to_sqlite.py"

echo ===================================================
echo Todos los servicios han sido lanzados en terminales separadas.
echo Puedes cerrar esta ventana.
echo ===================================================
