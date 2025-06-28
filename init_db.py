import sqlite3


conn = sqlite3.connect('drinklog.db')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS drinks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          date TEXT,
          name TEXT,
          volume REAL,
          alcohol REAL,
          memo TEXT
)
''')

conn.commit()
conn.close()

print("Database initialized.")