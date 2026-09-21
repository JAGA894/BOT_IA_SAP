import sqlite3
conn = sqlite3.connect('bot_ia.db')
cursor = conn.cursor()

cursor.execute("SELECT Nombre_cliente, SUM(Saldo_vencido) as deud FROM CxC_Local GROUP BY Nombre_cliente HAVING deud > 0 ORDER BY deud DESC LIMIT 5")
print("\n--- Clientes con deuda ---")
for r in cursor.fetchall(): print(r)

conn.close()
