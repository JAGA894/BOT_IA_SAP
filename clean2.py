import sqlite3
conn = sqlite3.connect('bot_ia.db')
conn.cursor().execute("UPDATE notificaciones_pendientes SET enviado = 1")
conn.commit()
