import sqlite3
conn = sqlite3.connect('bot_ia.db')
cur = conn.cursor()
cur.execute("SELECT Saldo_vencido FROM CxC_Local WHERE Nombre_extranjero LIKE '%QUERETARO%'")
print("Extranjero:", cur.fetchall())
cur.execute("SELECT Saldo_vencido FROM CxC_Local WHERE Nombre_cliente LIKE '%QUERETARO%'")
print("Cliente:", cur.fetchall())
conn.close()
