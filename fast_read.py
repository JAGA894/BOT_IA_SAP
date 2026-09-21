import sqlite3
import time

def fast_read():
    time.sleep(1) # wait for slow_write to hold lock
    with sqlite3.connect('bot_ia.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM CxC_Local")
        res = cursor.fetchone()
        print("Fast read done:", res)

if __name__ == '__main__':
    fast_read()
