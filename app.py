from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('drinklog.db')
    conn.row_factory = sqlite3.Row
    return conn

#トップ画面
@app.route('/')
def index():
    conn = get_db_connection()
    drinks = conn.execute('SELECT * FROM drinks ORDER BY date DESC').fetchall()
    conn.close()
    return render_template('index.html', drinks=drinks)

#記録追加画面
@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        # フォームデータ取得してDB登録
        date = request.form['date']
        name = request.form['name']
        volume = request.form['volume']
        alcohol = request.form['alcohol']
        memo = request.form['memo']

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO drinks (date, name, volume, alcohol, memo) VALUES (?, ?, ?, ?, ?)',
            (date, name, volume, alcohol, memo)
        )
        conn.commit()
        conn.close()
        return redirect('/')
    return render_template('add.html')

if __name__ == '__main__':
    app.run(debug=True)