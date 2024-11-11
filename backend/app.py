from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import logging

app = Flask(__name__)

# 更新CORS配置
CORS(app, resources={r"/*": {"origins": "*"}})

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('signals.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS trading_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            volume INTEGER DEFAULT 1,
            strategy TEXT,
            processed BOOLEAN DEFAULT FALSE,
            process_time DATETIME,
            order_id TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

@app.after_request
def apply_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        
        # 验证必要字段
        required_fields = ['symbol', 'action', 'price', 'strategy']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        conn = sqlite3.connect('signals.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO trading_signals (symbol, action, price, volume, strategy, processed, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['symbol'],
            data['action'],
            data['price'],
            1,
            data['strategy'],
            False,
            'pending'
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Received signal: {json.dumps(data)}")
        return jsonify({'success': True, 'message': 'Signal received'})
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/signals', methods=['GET'])
def get_signals():
    try:
        conn = sqlite3.connect('signals.db')
        c = conn.cursor()
        
        c.execute('SELECT id, symbol, action, price, timestamp, volume, strategy, processed, status FROM trading_signals ORDER BY timestamp DESC')
        rows = c.fetchall()
        
        signals = []
        for row in rows:
            signals.append({
                'id': row[0],
                'symbol': row[1], 
                'action': row[2],
                'price': row[3],
                'timestamp': row[4],
                'volume': row[5],
                'strategy': row[6],
                'processed': bool(row[7]),
                'status': row[8]
            })
        
        return jsonify({'success': True, 'data': signals})
        
    except Exception as e:
        logger.error(f"Error fetching signals: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        # 读取最后100行日志
        with open('trading.log', 'r') as f:
            logs = f.readlines()[-100:]
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/account', methods=['GET'])
def get_account():
    try:
        conn = sqlite3.connect('signals.db')
        c = conn.cursor()
        
        # 获取最新的账户数据
        c.execute('''
            SELECT balance, equity, available, position_profit, timestamp
            FROM account_info
            ORDER BY timestamp DESC
            LIMIT 1
        ''')
        row = c.fetchone()
        
        if row:
            account_data = {
                'balance': row[0],
                'equity': row[1],
                'available': row[2],
                'profit': row[3],
                'timestamp': row[4]
            }
            return jsonify({'success': True, 'data': account_data})
        else:
            return jsonify({'success': False, 'error': 'No account data available'}), 404
            
    except Exception as e:
        logger.error(f"Error fetching account data: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=80, debug=True)
