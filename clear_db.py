import sqlite3

conn = sqlite3.connect('drink_history.db')
c = conn.cursor()
c.execute('DELETE FROM drink_history')
conn.commit()
conn.close()

print("テーブル内のデータを削除しました。")