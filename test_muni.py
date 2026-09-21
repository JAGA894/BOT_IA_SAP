import sqlite3
conn = sqlite3.connect('bot_ia.db')
cur = conn.cursor()
cur.execute("SELECT Nombre_cliente, Nombre_extranjero, Proyecto, Saldo_vencido FROM CxC_Local WHERE Proyecto LIKE '%MUNICIPIO DE QUERETARO%'")
print(cur.fetchall())
conn.close()
