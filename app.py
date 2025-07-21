from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import requests
import json
from datetime import datetime, timedelta
from flask import jsonify
from flask import url_for
from urllib.parse import urlencode
from collections import defaultdict
from itertools import zip_longest
from dotenv import load_dotenv



def init_db():
    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS drink_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            jan_code TEXT,
            product_name TEXT,
            volume INTEGER,
            alcohol REAL,
            alcohol_grams REAL,
            pure_alcohol REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()


app = Flask(__name__)
app.secret_key = "hisajo34tnjngkrejk34"

# =========API呼び出し関数============

def search_item_by_jan(jan_code):
    load_dotenv()
    APP_ID = os.getenv("JAN_API_KEY")
    endpoint = "https://api.jancodelookup.com/"
    params = {
        "appId": APP_ID,
        "query": jan_code,
        "hits": 1,
    }
    try:
        response = requests.get(endpoint, params=params)
        data = response.json()

        products = data.get("product")
        if not products or len(products) == 0:
            raise Exception("商品が見つかりません")

        product = products[0]
        item_name = product.get('itemName')
        image_url = product.get('itemImageUrl')
        
        #容量の抽出と数値化
        product_details = product.get("ProductDetails", {})
        volume_str = product_details.get("内容量", "")
        volume = None
        if volume_str:
            #350ml -> 350
            volume = ''.join(filter(str.isdigit, volume_str))
            volume = int(volume) if volume else None

        return {
            "name": item_name,
            "image_url": image_url,
            "volume": volume
        }
    
    except Exception as e:
        print("取得失敗", e)
        print(data)
        return None

#==========API呼び出し関数終わり===============

def get_db_connection():
    conn = sqlite3.connect('drink_history.db')
    conn.row_factory = sqlite3.Row
    return conn


#トップ画面
@app.route('/')
def index():
#    conn = get_db_connection()
#    drinks = conn.execute('SELECT * FROM drinks ORDER BY date DESC').fetchall()
#    conn.close()
    return render_template('index.html')


#飲み会用記録追加画面 
@app.route('/quick_add', methods=['GET', 'POST'])
def quick_add():
    if request.method == 'POST':
        data = request.get_json()
        drinks = data.get('drinks', [])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        for drink in drinks:
            name = drink['name']
            volume = float(drink['volume'])
            alcohol = float(drink['alcohol'])
            count = drink['count']

            pure_alcohol = (volume * alcohol / 100) * 0.8

            for _ in range(count):
                cursor.execute(
                    '''
                    INSERT INTO drink_history (timestamp, jan_code, product_name, volume, alcohol, pure_alcohol)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (timestamp, None, name, volume, alcohol, pure_alcohol)
                )
        conn.commit()
        conn.close()

        return jsonify({'status': 'success'})
    
    return render_template('quick_add.html')

@app.route('/graph')
def graph():
    mode = request.args.get('mode', 'daily')
    month = request.args.get('month', default=datetime.today().month, type=int)
    year = request.args.get('year', default=datetime.today().year, type=int)

    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    c.execute('SELECT timestamp, pure_alcohol FROM drink_history')
    rows = c.fetchall()
    conn.close()

    data = defaultdict(float)
    #current_year = datetime.now().year
    #monthly_data = defaultdict(float)
    

    for timestamp_str, pure_alcohol in rows:
        if not timestamp_str or pure_alcohol is None:
            continue
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        if dt.year == year and dt.month == month:
            day = dt.day
        #    monthly_data[month_key] += pure_alcohol
        # key = dt.strftime('%Y-%m') if mode == 'monthly' else dt.strftime('%Y-%m-%d %H:%M:%S')
            data[day] += pure_alcohol if pure_alcohol else 0

    labels = [f"{day}日" for day in sorted(data.keys())]
    values = [round(data[day], 2) for day in sorted(data.keys())]

    return render_template('graph.html', labels=labels, values=values, mode=mode, month=month, year=year, prev_month=prev_month, prev_year=prev_year, next_month=next_month, next_year=next_year)

@app.route('/calendar')
def calendar():
    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    c.execute('SELECT timestamp, pure_alcohol FROM drink_history')
    rows = c.fetchall()
    conn.close()

    # 月初と月末を取り出す
    today = datetime.today()
    target_year = request.args.get('year', type=int)
    target_month = request.args.get('month', type=int)
    if not target_year or not target_month:
        target_year = today.year
        target_month = today.month

    first_day_of_month = datetime(target_year, target_month, 1)
    last_day_of_month = (first_day_of_month.replace(month=target_month % 12 + 1, day=1) - timedelta(days=1))
    last_day_num = last_day_of_month.day

    # 日付: 合計純アルコール量 を作成
    day_to_alcohol = defaultdict(float)
    for timestamp_str, pure_alcohol in rows:
        if not timestamp_str or pure_alcohol is None:
            continue
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        if first_day_of_month <= dt <= last_day_of_month:
            day_key = dt.day
            day_to_alcohol[day_key] += pure_alcohol

    # 月初の曜日（0=Monday, 6=Sunday）
    first_weekday = first_day_of_month.weekday()  # カレンダー表示で使うなら template 側で調整も可能

    # 1日から末日までのリスト作成
    days = []
    for day in range(1, last_day_num + 1):
        alcohol = round(day_to_alcohol.get(day, 0), 1)
        days.append((day, alcohol))

    # 先頭に空白を入れて曜日位置を調整
    empty_cells = (first_weekday + 1) % 7  # 日曜始まりならこの形で
    days = [("", "")] * empty_cells + days

    # 7日ごとに折り返す
    rows = [days[i:i+7] for i in range(0, len(days), 7)]

    prev_month_date = first_day_of_month - timedelta(days=1)
    next_month_date = (first_day_of_month + timedelta(days=32)).replace(day=1)

    return render_template(
        'calendar.html',
        rows=rows,
        year=target_year,
        month=target_month,
        prev_year=prev_month_date.year,
        prev_month=prev_month_date.month,
        next_year=next_month_date.year,
        next_month=next_month_date.month
    )


@app.route('/scan', methods=['GET'])
def scan():
    jan_code = request.args.get("jan_code")
    item_info = None

    if jan_code:
        print(f"GETでjan_code={jan_code}を受信しました。")
        conn = sqlite3.connect('drink_history.db')
        c = conn.cursor()
        c.execute('''
            SELECT id, timestamp, product_name, volume, alcohol FROM drink_history
            WHERE jan_code = ?
            ORDER BY id DESC
            LIMIT 1
        ''', (jan_code,))
        row = c.fetchone()
        conn.close()

        if row:
            item_info = {
                "id": row[0],
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "name": row[2],
                "volume": row[3],
                "alcohol": row[4],
                "jan_code": jan_code
            }
            # APIから画像取得
            api_info = search_item_by_jan(jan_code)
            if api_info and api_info.get("image_url"):
                item_info["image_url"] = api_info.get("image_url")
            else:
                item_info["image_url"] = None

            return render_template('confirm_register.html', item=item_info)

        else:
            try:
                api_info = search_item_by_jan(jan_code)
                print("APIより取得情報:", api_info)
                if api_info:
                    item_info = {
                        "name": api_info.get("name"),
                        "volume": api_info.get("volume"),
                        "alcohol": api_info.get("alcohol"),
                        "image_url": api_info.get("image_url"),
                        "jan_code": jan_code,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                else:
                    item_info = {"name": "商品情報が取得できませんでした", "image_url": None}
            except Exception as e:
                print("商品情報取得エラー：", e)
                item_info = {"name": "商品情報が取得できませんでした", "image_url": None}
            return render_template('scan_result.html', item=item_info)

    return render_template('scan.html')


@app.route('/scan_camera')
def scan_camera():
    return render_template('scan_camera.html')


@app.route('/confirm_register_camera')
def confirm_register_camera():
    item_info = session.get('item_info')
    if not item_info:
        return redirect('/scan')
    
    return render_template('confirm_register.html', item=item_info)


@app.route('/scan_camera_action', methods=['POST'])
def scan_camera_action():
    data = request.get_json()
    jan_code = data.get("jancode")

    if not jan_code:
        return jsonify({"error": "JANコードがありません"}), 400
    
    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    c.execute('''
        SELECT id, timestamp, product_name, volume, alcohol FROM drink_history
        WHERE jan_code = ?
        ORDER BY id DESC
        LIMIT 1
    ''', (jan_code,))
    row = c.fetchone()
    conn.close()

    if row:
    # DB登録済みの場合は取り出し、
        item_info = {
            "id": row[0],
            "timestamp": row[1],
            "name": row[2],
            "volume": row[3],
            "alcohol": row[4],
            "jan_code": jan_code
        }
        item_info["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        api_info = search_item_by_jan(jan_code)
        if api_info and api_info.get("image_url"):
            item_info["image_url"] = api_info.get("image_url")
        else:
            item_info["image_url"] = None

        session['item_info'] = item_info

        return jsonify({"redirect": "/confirm_register_camera"})
    else:
        #新規処理へ
        #必要であれば直接confirm_registerへ飛ばす実装も可能
        return jsonify({"redirect": f"/scan_result?jan_code={jan_code}"})


@app.route('/scan_result', methods=['GET', 'POST'])
def scan_result():
    jan_code = request.args.get('jan_code')
    item_info = None

    if jan_code:
        api_info = search_item_by_jan(jan_code)
        if api_info:
            item_info = {
                "name": api_info.get("name"),
                "volume": api_info.get("volume"),
                "image_url": api_info.get("image_url"),
                "jan_code": jan_code
            }
        else:
            item_info = {
                "name": "商品情報が取得できませんでした",
                "volume": "",
                "image_url": "",
                "jan_code": jan_code
            }

    return render_template('scan_result.html', barcode=jan_code, item=item_info)


@app.route('/confirm_register_action', methods=['POST'])
def confirm_register_action():
    jan_code = request.form.get('jan_code')
    name = request.form.get('name')
    volume = request.form.get('volume')
    alcohol = request.form.get('alcohol')

    # 純アルコール計算
    pure_alcohol = 0.0
    try:
        vol = float(volume) if volume else 0
        alc = float(alcohol) if alcohol else 0
        pure_alcohol = (vol * alc / 100) * 0.8
    except Exception as e:
        print("純アルコール計算エラー", e)
        pure_alcohol = 0.0

    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO drink_history (timestamp, jan_code, product_name, volume, alcohol, pure_alcohol)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        jan_code,
        name,
        volume,
        alcohol,
        pure_alcohol
    ))
    conn.commit()
    conn.close()
    return redirect('/history')


@app.route('/history')
def history():
    page = request.args.get('page', default=1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    c.execute('''
              SELECT id, timestamp, jan_code, product_name, volume, alcohol
              FROM drink_history
              ORDER BY timestamp DESC
              LIMIT ? OFFSET ?
    ''', (per_page, offset))
    history = c.fetchall()

    c.execute('SELECT COUNT(*) FROM drink_history')
    total_count = c.fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page

    conn.close()
    return render_template('history.html', history=history, page=page, total_pages=total_pages)

@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        volume = request.form['volume']
        alcohol = request.form['alcohol']

        vol = float(volume) if volume else 0
        alc = float(alcohol) if alcohol else 0
        pure_alcohol = (vol * alc / 100) * 0.8

        c.execute("UPDATE drink_history SET product_name=?, volume=?, alcohol=?, pure_alcohol=? WHERE id=?", (name, volume, alcohol, pure_alcohol, item_id))
        conn.commit()
        conn.close()
        return redirect('/history')
    else:
        c.execute("SELECT * FROM drink_history WHERE id=?", (item_id,))
        item = c.fetchone()
        conn.close()
        return render_template('edit_item.html', item=item)
    
@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    c.execute("DELETE FROM drink_history WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return redirect('/history')

@app.route('/update_alcohol', methods=['POST'])
def update_alcohol():
    jan_code = request.form['jan_code']
    alcohol = request.form['alcohol']

    conn = sqlite3.connect('drink_history.db')
    c = conn.cursor()
    #更新対象の最新idを取得
    c.execute('''
        SELECT id, volume FROM drink_history
        WHERE jan_code = ?
        ORDER BY id DESC
        LIMIT 1
    ''', (jan_code,))
    row = c.fetchone()

    if row:
        item_id = row[0]
        volume = float(row[1]) if row[1] else 0
        alcohol_value = float(alcohol) if alcohol else 0
        pure_alcohol = (volume * alcohol_value / 100) * 0.8

        c.execute('''
            UPDATE drink_history
            SET alcohol = ?, pure_alcohol = ?
            WHERE id = ?
        ''', (alcohol_value, pure_alcohol, item_id))
    conn.commit()
    conn.close()
    return redirect('/history')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)