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
            status TEXT DEFAULT 'pending',
            message TEXT
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
            data['action'].upper(),
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
                'profit': row[0] - 200000,
                'timestamp': row[4]
            }
            return jsonify({'success': True, 'data': account_data})
        else:
            return jsonify({'success': False, 'error': 'No account data available'}), 404
            
    except Exception as e:
        logger.error(f"Error fetching account data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/profits', methods=['GET'])
def get_profits():
    try:
        conn = sqlite3.connect('signals.db')
        c = conn.cursor()
        
        # 加载合约规格
        contract_specs = {
            # 中金所
            'IF': {'size': 300, 'fee': {'open': 0, 'close': 0}},   # 沪深300股指
            'IC': {'size': 200, 'fee': {'open': 0, 'close': 0}},   # 中证500股指
            'IH': {'size': 300, 'fee': {'open': 0, 'close': 0}},   # 上证50股指
            'IM': {'size': 200, 'fee': {'open': 0, 'close': 0}},   # 中证1000股指
            
            # 上期所
            'AU': {'size': 1000, 'fee': {'open': 0, 'close': 0}},  # 黄金
            'AG': {'size': 15, 'fee': {'open': 0, 'close': 0}},    # 白银
            'CU': {'size': 5, 'fee': {'open': 0, 'close': 0}},     # 铜
            'AL': {'size': 5, 'fee': {'open': 0, 'close': 0}},     # 铝
            'ZN': {'size': 5, 'fee': {'open': 0, 'close': 0}},     # 锌
            'AO': {'size': 5, 'fee': {'open': 24.17, 'close': 23.99}},     # 氧化铝
            'RB': {'size': 10, 'fee': {'open': 3.35, 'close': 3.36}},    # 螺纹钢，按手数收费
            'BU': {'size': 10, 'fee': {'open': 1.67, 'close': 0.01}},    # 沥青，按手数收费
            'SP': {'size': 20, 'fee': {'open': 2.92, 'close': 0.01}},    # 纸浆，按手数收费
            'HC': {'size': 10, 'fee': {'open': 0, 'close': 0}},    # 热卷
            
            # 大商所
            'M': {'size': 10},     # 豆粕
            'Y': {'size': 10},     # 豆油
            'C': {'size': 10},     # 玉米
            'I': {'size': 100},    # 铁矿石
            'PP': {'size': 5},     # 聚丙烯
            
            # 郑商所
            'SR': {'size': 10},    # 白糖
            'MA': {'size': 10},    # 甲醇
            'TA': {'size': 5},     # PTA
            'AP': {'size': 10},    # 苹果
            'CF': {'size': 5},     # 棉花
        }
        
        # 按时间顺序获取所有交易信号
        c.execute('''
            SELECT id, symbol, action, price, timestamp, strategy, status, volume
            FROM trading_signals 
            WHERE status = 'filled'  -- 只查询已成交的订单
            ORDER BY timestamp ASC
        ''')
        rows = c.fetchall()
        
        profits = []
        open_positions = {}  # 用于跟踪开仓状态: {symbol: {direction, price, time, volume}}
        
        for row in rows:
            id, symbol, action, price, timestamp, strategy, status, volume = row
            
            # 获取合约基础代码（去除月份）
            base_symbol = ''.join(filter(str.isalpha, symbol.upper()))
            contract_info = contract_specs.get(base_symbol, {'size': 1, 'fee': {'open': 0, 'close': 0}})
            contract_size = contract_info['size']
            
            if action.upper() in ['BUY', 'LONG']:
                if symbol not in open_positions:
                    # 开多仓
                    fee = contract_info['fee']['open'] * volume  # 计算开仓手续费
                    open_positions[symbol] = {
                        'direction': 'LONG',
                        'price': price,
                        'time': timestamp,
                        'id': id,
                        'volume': volume,
                        'open_fee': fee
                    }
                    
            elif action.upper() in ['SELL', 'SHORT']:
                if symbol not in open_positions:
                    # 开空仓
                    fee = contract_info['fee']['open'] * volume  # 计算开仓手续费
                    open_positions[symbol] = {
                        'direction': 'SHORT',
                        'price': price,
                        'time': timestamp,
                        'id': id,
                        'volume': volume,
                        'open_fee': fee
                    }
                    
            elif action.upper() in ['CLOSE_LONG', 'CLOSE_SHORT', 'SELL_CLOSE', 'BUY_CLOSE']:
                if symbol in open_positions:
                    # 计算盈亏
                    open_pos = open_positions[symbol]
                    point_profit = 0
                    
                    if open_pos['direction'] == 'LONG':
                        point_profit = price - open_pos['price']
                    else:  # SHORT
                        point_profit = open_pos['price'] - price
                    
                    # 计算平仓手续费
                    close_fee = contract_info['fee']['close'] * open_pos['volume']
                    total_fee = open_pos['open_fee'] + close_fee
                    
                    # 计算实际盈亏 = 点数 * 合约规模 * 手数 - 总手续费
                    actual_profit = (point_profit * contract_size * open_pos['volume']) - total_fee
                        
                    # 添加到盈亏列表
                    profits.append({
                        'id': open_pos['id'],
                        'symbol': symbol,
                        'direction': open_pos['direction'],
                        'openTime': open_pos['time'],
                        'closeTime': timestamp,
                        'openPrice': open_pos['price'],
                        'closePrice': price,
                        'volume': open_pos['volume'],
                        'pointProfit': round(point_profit, 2),
                        'fee': round(total_fee, 2),
                        'profit': round(actual_profit, 2)
                    })
                    
                    # 清除开仓记录
                    del open_positions[symbol]
        
        return jsonify({
            'success': True,
            'data': profits
        })
        
    except Exception as e:
        logger.error(f"Error calculating profits: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=80, debug=True)
