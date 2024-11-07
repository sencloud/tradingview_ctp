from ctpbee import CtpBee
import sqlite3
import time
import logging
import json
import os
from datetime import datetime
from pathlib import Path
from ctpbee.constant import (
    OrderRequest, 
    Direction, 
    Offset, 
    OrderType,
    Exchange,
    ContractData
)

# 设置NumExpr线程数
os.environ["NUMEXPR_MAX_THREADS"] = "8"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SignalMonitor:
    def __init__(self):
        self.app = CtpBee("signal_trader", __name__, refresh=True)
        self.contract_specs = self.load_contract_specs()
        self.load_config()
        
    def load_contract_specs(self):
        """加载合约规格"""
        return {
            # 中金所
            'IF': {'size': 300, 'exchange': Exchange.CFFEX},   # 沪深300股指
            'IC': {'size': 200, 'exchange': Exchange.CFFEX},   # 中证500股指
            'IH': {'size': 300, 'exchange': Exchange.CFFEX},   # 上证50股指
            'IM': {'size': 200, 'exchange': Exchange.CFFEX},   # 中证1000股指
            
            # 上期所
            'AU': {'size': 1000, 'exchange': Exchange.SHFE},   # 黄金
            'AG': {'size': 15, 'exchange': Exchange.SHFE},     # 白银
            'CU': {'size': 5, 'exchange': Exchange.SHFE},      # 铜
            'AL': {'size': 5, 'exchange': Exchange.SHFE},      # 铝
            'ZN': {'size': 5, 'exchange': Exchange.SHFE},      # 锌
            'RB': {'size': 10, 'exchange': Exchange.SHFE},     # 螺纹钢
            
            # 大商所
            'M': {'size': 10, 'exchange': Exchange.DCE},       # 豆粕
            'Y': {'size': 10, 'exchange': Exchange.DCE},       # 豆油
            'C': {'size': 10, 'exchange': Exchange.DCE},       # 玉米
            'I': {'size': 100, 'exchange': Exchange.DCE},      # 铁矿石
            'PP': {'size': 5, 'exchange': Exchange.DCE},       # 聚丙烯
            
            # 郑商所
            'SR': {'size': 10, 'exchange': Exchange.CZCE},     # 白糖
            'MA': {'size': 10, 'exchange': Exchange.CZCE},     # 甲醇
            'TA': {'size': 5, 'exchange': Exchange.CZCE},      # PTA
            'AP': {'size': 10, 'exchange': Exchange.CZCE},     # 苹果
            'CF': {'size': 5, 'exchange': Exchange.CZCE},      # 棉花
        }
    
    def load_config(self):
        """加载配置文件"""
        try:
            config_path = Path(__file__).parent / 'config_sim.json'
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info("成功加载配置文件")
            
            # 验证必要的配置项
            required_keys = ['CONNECT_INFO', 'INTERFACE', 'TD_FUNC', 'MD_FUNC']
            for key in required_keys:
                if key not in self.config:
                    raise KeyError(f"配置文件缺少必要的配置项: {key}")
                    
            # 验证连接信息
            required_connect_info = ['userid', 'password', 'brokerid', 'md_address', 'td_address']
            for key in required_connect_info:
                if key not in self.config['CONNECT_INFO']:
                    raise KeyError(f"连接配置缺少必要的配置项: {key}")
                    
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            raise
        
    def setup(self):
        """初始化交易系统"""
        try:
            self.app.config.from_mapping(self.config)
            # 确保数据库表存在
            self.init_database()
            # 启动交易系统
            self.app.start(log_output=True)
            logger.info("交易系统启动成功")
        except Exception as e:
            logger.error(f"交易系统启动失败: {str(e)}")
            raise
            
    def init_database(self):
        """初始化数据库表"""
        try:
            with sqlite3.connect('signals.db') as conn:
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
                logger.info("数据库初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
            raise

    def get_contract_info(self, symbol):
        """获取合约信息"""
        # 提取合约品种代码（去除月份）
        product_code = ''.join(filter(str.isalpha, symbol.upper()))
        
        if product_code in self.contract_specs:
            contract_info = self.contract_specs[product_code].copy()
            contract_info['product_code'] = product_code
            return contract_info
        else:
            logger.warning(f"未找到合约 {symbol} 的规格信息，使用默认值")
            return {
                'size': 10, 
                'exchange': Exchange.SHFE,
                'product_code': product_code
            }

    def create_order_request(self, symbol, price, volume, direction):
        """创建标准化的下单请求"""
        try:
            # 获取合约信息
            contract_info = self.get_contract_info(symbol)
            
            # 扩展方向和开平映射
            if direction == 'BUY':  # 开多
                order_direction = Direction.LONG
                order_offset = Offset.OPEN
            elif direction == 'SELL':  # 开空
                order_direction = Direction.SHORT
                order_offset = Offset.OPEN
            elif direction == 'BUY_CLOSE':  # 平空
                order_direction = Direction.LONG
                order_offset = Offset.CLOSETODAY  # 先尝试平今
            elif direction == 'SELL_CLOSE':  # 平多
                order_direction = Direction.SHORT
                order_offset = Offset.CLOSETODAY  # 先尝试平今
            else:
                raise ValueError(f"不支持的交易方向: {direction}")
            
            # 创建订单请求
            order_req = OrderRequest(
                symbol=symbol,
                exchange=contract_info['exchange'],
                price=price,
                volume=volume,
                direction=order_direction,
                offset=order_offset,
                type=OrderType.LIMIT,
                order_id=self.generate_order_id()
            )
            return order_req, contract_info
            
        except Exception as e:
            logger.error(f"创建订单请求失败: {str(e)}")
            raise

    def generate_order_id(self):
        """生成唯一的订单ID"""
        return f"ORDER_{int(time.time()*1000)}_{int(time.perf_counter()*1000000)}"

    def execute_order(self, symbol, price, volume, direction, signal_id):
        """执行下单操作"""
        try:
            # 创建下单请求和获取合约信息
            order_req, contract_info = self.create_order_request(symbol, price, volume, direction)
            
            # 发送订单
            order_id = self.app.send_order(order_req)
            
            # 如果是平仓订单且失败了，可能需要尝试平昨仓
            if not order_id and direction in ['BUY_CLOSE', 'SELL_CLOSE']:
                logger.info(f"平今仓失败，尝试平昨仓...")
                # 修改为平昨仓
                order_req.offset = Offset.CLOSEYESTERDAY
                order_id = self.app.send_order(order_req)
                
                # 如果平昨仓也失败，最后尝试普通平仓
                if not order_id:
                    logger.info(f"平昨仓失败，尝试普通平仓...")
                    order_req.offset = Offset.CLOSE
                    order_id = self.app.send_order(order_req)
            
            if order_id:
                logger.info(f"订单发送成功: {direction} {symbol} 价格:{price} 数量:{volume} "
                          f"订单ID:{order_id} 合约乘数:{contract_info['size']}")
                
                # 更新数据库中的订单ID
                with sqlite3.connect('signals.db') as conn:
                    c = conn.cursor()
                    c.execute('''
                        UPDATE trading_signals 
                        SET order_id = ?, status = 'submitted'
                        WHERE id = ?
                    ''', (order_id, signal_id))
                    conn.commit()
                
                return True
            else:
                logger.error("订单发送失败")
                return False
                
        except Exception as e:
            logger.error(f"下单执行异常: {str(e)}")
            logger.error(f"订单信息: symbol={symbol}, price={price}, volume={volume}, "
                      f"direction={direction}")
            return False
        
    def process_signal(self, signal):
        """处理交易信号"""
        try:
            # 从信号中提取交易参数
            symbol = signal['symbol']
            action = signal['action'].upper()  # 确保动作是大写
            
            # 验证交易动作
            valid_actions = {'BUY', 'SELL', 'BUY_CLOSE', 'SELL_CLOSE'}
            if action not in valid_actions:
                raise ValueError(f"无效的交易动作: {action}，支持的动作: {valid_actions}")
            
            price = float(signal['price'])
            volume = int(signal.get('volume', 1))
            signal_id = signal['id']
            
            # 执行订单
            if self.execute_order(symbol, price, volume, action, signal_id):
                # 更新信号状态为已处理
                with sqlite3.connect('signals.db') as conn:
                    c = conn.cursor()
                    c.execute('''
                        UPDATE trading_signals
                        SET processed = TRUE, 
                            process_time = CURRENT_TIMESTAMP,
                            status = 'processed'
                        WHERE id = ?
                    ''', (signal_id,))
                    conn.commit()
                
                logger.info(f"信号处理完成: ID={signal_id}")
            else:
                logger.error(f"信号处理失败: ID={signal_id}")
                # 更新信号状态为失败
                with sqlite3.connect('signals.db') as conn:
                    c = conn.cursor()
                    c.execute('''
                        UPDATE trading_signals
                        SET status = 'failed'
                        WHERE id = ?
                    ''', (signal_id,))
                    conn.commit()
            
        except Exception as e:
            logger.error(f"处理信号失败: {str(e)}")
            
    def monitor_signals(self):
        """监控交易信号"""
        logger.info("开始监控交易信号")
        while True:
            try:
                with sqlite3.connect('signals.db') as conn:
                    c = conn.cursor()
                    
                    # 获取未处理的信号
                    c.execute('''
                        SELECT id, symbol, action, price, timestamp, 
                               volume, strategy, processed, status
                        FROM trading_signals
                        WHERE processed = FALSE AND status = 'pending'
                        ORDER BY timestamp ASC
                    ''')
                    
                    signals = c.fetchall()
                    for signal in signals:
                        signal_dict = {
                            'id': signal[0],
                            'symbol': signal[1],
                            'action': signal[2],
                            'price': signal[3],
                            'timestamp': signal[4],
                            'volume': signal[5] if signal[5] is not None else 1,
                            'strategy': signal[6],
                            'status': signal[8]
                        }
                        self.process_signal(signal_dict)
                        
                time.sleep(1)  # 每秒检查一次新信号
                
            except Exception as e:
                logger.error(f"信号监控出错: {str(e)}")
                time.sleep(5)  # 发生错误时等待更长时间

def main():
    """主函数"""
    try:
        monitor = SignalMonitor()
        monitor.setup()
        monitor.monitor_signals()
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()