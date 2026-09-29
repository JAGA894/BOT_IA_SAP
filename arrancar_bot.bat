@echo off
echo ===================================================
echo Iniciando entorno del Bot IA CxC (AUTO-REINICIO + ANTIPAUSA)
echo ===================================================

:: Desactivar QuickEdit Mode para evitar que el proceso se pause al hacer clic
reg add HKCU\Console /v QuickEdit /t REG_DWORD /d 0 /f >nul

echo [0/3] Limpiando procesos fantasma de sesiones anteriores...
timeout /t 1 /nobreak >nul

:: Crear scripts de auto-reinicio
echo @echo off > run_fastapi.bat
echo reg add HKCU\Console /v QuickEdit /t REG_DWORD /d 0 /f ^>nul >> run_fastapi.bat
echo :loop >> run_fastapi.bat
echo call .\venv\Scripts\activate >> run_fastapi.bat
echo python bot_app.py >> run_fastapi.bat
echo echo "Servidor FastAPI caido. Reiniciando en 5 segundos..." >> run_fastapi.bat
echo timeout /t 5 /nobreak ^>nul >> run_fastapi.bat
echo goto loop >> run_fastapi.bat

echo @echo off > run_whatsapp.bat
echo reg add HKCU\Console /v QuickEdit /t REG_DWORD /d 0 /f ^>nul >> run_whatsapp.bat
echo :loop >> run_whatsapp.bat
echo node whatsapp_client.js >> run_whatsapp.bat
echo echo "Cliente WhatsApp caido. Reiniciando en 5 segundos..." >> run_whatsapp.bat
echo timeout /t 5 /nobreak ^>nul >> run_whatsapp.bat
echo goto loop >> run_whatsapp.bat

echo @echo off > run_etl.bat
echo reg add HKCU\Console /v QuickEdit /t REG_DWORD /d 0 /f ^>nul >> run_etl.bat
echo :loop >> run_etl.bat
echo call .\venv\Scripts\activate >> run_etl.bat
echo python etl_sap_to_sqlite.py >> run_etl.bat
echo echo "Sincronizador SAP caido. Reiniciando en 5 segundos..." >> run_etl.bat
echo timeout /t 5 /nobreak ^>nul >> run_etl.bat
echo goto loop >> run_etl.bat

echo [1/3] Levantando FastAPI...
start "Servidor FastAPI" cmd /k "run_fastapi.bat"
timeout /t 3 /nobreak >nul

echo [2/3] Levantando Cliente WhatsApp...
start "Cliente WhatsApp" cmd /k "run_whatsapp.bat"
timeout /t 3 /nobreak >nul

echo [3/3] Levantando ETL SAP...
start "Sincronizador SAP ETL" cmd /k "run_etl.bat"

echo ===================================================
echo Todos los servicios han sido lanzados con AUTO-REINICIO.
echo Puedes cerrar esta ventana.
echo ===================================================
