import sqlite3, os
from dotenv import load_dotenv
load_dotenv()
db = os.getenv('DB_NAME', 'bot_ia.db')
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT SUM(Importe_aplicado) FROM CxC_Local WHERE Empresa='ERSA_PRODUCTIVA' AND Nombre_cliente LIKE '%MAIZ GRUPO%'")
for row in cur.fetchall(): print('Total cobrado:', row)
