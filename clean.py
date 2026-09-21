import sqlite3
conn = sqlite3.connect('bot_ia.db')
conn.cursor().execute("DELETE FROM notificacion_destinatarios WHERE destino NOT LIKE '854405%'")
conn.commit()
print('Eliminados')
