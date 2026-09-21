import sqlite3
import time

def slow_write():
    with sqlite3.connect('bot_ia.db') as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO notificacion_destinatarios (tipo, destino, activo) VALUES ('test', 'slow@c.us', 0)")
        time.sleep(3)
        conn.commit()
    print("Slow write done")

if __name__ == '__main__':
    slow_write()
