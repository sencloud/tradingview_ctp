from ctpbee import CtpBee, CtpbeeApi
import sqlite3
from sqlite3 import Connection
from contextlib import contextmanager
import time
import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from ctpbee.constant import (
    OrderRequest, 
    Direction, 
    Offset, 
    OrderType,
    Exchange,
    ContractData,
    TickData
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

class DatabaseConnection:
    """数据库连接管理器"""
    def __init__(self):
        self.conn: Optional[Connection] = None
        
    def get_connection(self) -> Connection:
        if self.conn is None:
            self.conn = sqlite3.connect('signals.db')
        return self.conn
        
    @contextmanager
    def get_cursor(self):
        try:
            cursor = self.get_connection().cursor()
            yield cursor
            self.conn.commit()
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            raise e

class PositionManager:
    """持仓管理器"""
    def __init__(self, app: CtpBee = None):
        self.positions: Dict[str, Dict] = {}
        self.max_position = 3
        self.app = app
        if app:
            self.init_positions()
        
    def init_positions(self):
        """从账户初始化持仓信息"""
        try:
            # 获取所有持仓数据
            positions = self.app.center.positions
            logger.info(f"获取到的持仓数据: {positions}")
            
            # 遍历持仓列表
            for position in positions:
                symbol = position.symbol
                if symbol not in self.positions:
                    self.positions[symbol] = {'LONG': 0, 'SHORT': 0}
                
                # 根据方向更新持仓
                direction = 'LONG' if position.direction == Direction.LONG else 'SHORT'
                # 使用 volume 和 yd_volume 的总和
                volume = position.volume + position.yd_volume
                
                self.positions[symbol][direction] = volume
                
                logger.info(f"初始化持仓: {symbol} {direction} "
                          f"今仓:{position.volume} 昨仓:{position.yd_volume} "
                          f"总量:{volume}")
                
        except Exception as e:
            logger.error(f"初始化持仓失败: {str(e)}")
            logger.exception("详细错误信息:")
            
    def refresh_positions(self):
        """刷新持仓信息"""
        if self.app:
            self.init_positions()
            
    def get_position(self, symbol: str, direction: str) -> int:
        """获取持仓"""
        # 每次获取持仓时都刷新一下
        self.refresh_positions()
        
        if symbol not in self.positions:
            return 0
            
        if direction in ['BUY', 'SELL_CLOSE']:
            pos_direction = 'LONG'
        elif direction in ['SELL', 'BUY_CLOSE']:
            pos_direction = 'SHORT'
        else:
            logger.error(f"无效的交易方向: {direction}")
            return 0
            
        position = self.positions[symbol][pos_direction]
        logger.info(f"获取持仓: {symbol} {pos_direction} 数量:{position}")
        return position
    
    def update_position(self, symbol: str, direction: str, volume: int):
        """更新持仓信息"""
        try:
            if symbol not in self.positions:
                self.positions[symbol] = {'LONG': 0, 'SHORT': 0}
            
            # 确定更新方向
            if direction == 'BUY':  # 开多
                self.positions[symbol]['LONG'] += volume
                logger.info(f"更新多头持仓: {symbol} +{volume} = {self.positions[symbol]['LONG']}")
            elif direction == 'SELL':  # 开空
                self.positions[symbol]['SHORT'] += volume
                logger.info(f"更新空头持仓: {symbol} +{volume} = {self.positions[symbol]['SHORT']}")
            elif direction == 'BUY_CLOSE':  # 平空
                self.positions[symbol]['SHORT'] = max(0, self.positions[symbol]['SHORT'] - volume)
                logger.info(f"更新空头持仓: {symbol} -{volume} = {self.positions[symbol]['SHORT']}")
            elif direction == 'SELL_CLOSE':  # 平多
                self.positions[symbol]['LONG'] = max(0, self.positions[symbol]['LONG'] - volume)
                logger.info(f"更新多头持仓: {symbol} -{volume} = {self.positions[symbol]['LONG']}")
            else:
                logger.error(f"无效的交易方向: {direction}")
                
        except Exception as e:
            logger.error(f"更新持仓失败: {str(e)}")
            logger.exception("详细错误信息:")
            raise

class MarketDataApi(CtpbeeApi):
    """行情API"""
    def __init__(self, name: str, app: CtpBee):
        super().__init__(name, app)
        self.ticks: Dict[str, TickData] = {}
        self.subscribed_symbols: set = set()  # 记录已订阅的合约
        self.inited = False
        logger.info("MarketDataApi initialized")
        
    def on_init(self, init: bool):
        """行情接口初始化回调"""
        self.inited = init
        logger.info(f"MarketDataApi on_init: {init}")
        
    def on_tick(self, tick: TickData) -> None:
        """处理TICK数据"""
        self.ticks[tick.symbol] = tick
        self.subscribed_symbols.add(tick.symbol)  # 记录收到TICK数据的合约
        # logger.info(f"收到TICK数据: {tick.symbol} 最新价: {tick.last_price}")
        
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """取最新价格"""
        if not self.inited:
            logger.warning("行情接口未就绪")
            return None
            
        tick = self.ticks.get(symbol)
        if tick:
            return tick.last_price
        logger.warning(f"未找到合约 {symbol} 的TICK数据")
        return None
        
    def on_account(self, account) -> None:
        """处理账户数据
        AccountData attributes:
        - accountid: str 账户号
        - balance: float 余额
        - frozen: float 冻结资金
        - available: float 可用资金
        """
        try:
            with DatabaseConnection().get_cursor() as c:
                c.execute('''
                    INSERT INTO account_info (balance, equity, available, position_profit)
                    VALUES (?, ?, ?, ?)
                ''', (
                    account.balance,                                    # 账户余额
                    account.balance + account.frozen,                   # 净值 = 余额 + 冻结资金
                    account.available,                                  # 可用资金
                    account.frozen                                      # 冻结资金
                ))
            # logger.info(f"账户数据更新: 余额={account.balance:.2f} "
            #            f"净值={account.balance + account.frozen:.2f} "
            #            f"可用={account.available:.2f} "
            #            f"冻结资金={account.frozen:.2f}")
        except Exception as e:
            logger.error(f"更新账户数据失败: {str(e)}")
            logger.exception("详细错误信息:")

class SignalMonitor:
    def __init__(self):
        self.app = CtpBee("signal_trader", __name__, refresh=True)
        self.market_api = MarketDataApi("market", self.app)
        self.app.add_extension(self.market_api)
        self.contract_specs = self.load_contract_specs()
        self.load_config()
        self.db = DatabaseConnection()
        self.position_manager = PositionManager(self.app)
        self.price_tolerance = 0.002  # 价格容忍度(0.2%)
        
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
            'BU': {'size': 10, 'exchange': Exchange.SHFE},     # 沥青
            'SP': {'size': 20, 'exchange': Exchange.SHFE},     # 纸浆
            'HC': {'size': 10, 'exchange': Exchange.SHFE},     # 热卷
            
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
    
    def subscribe_contracts(self):
        """订阅合约行情"""
        try:
            # 1. 获取需要订阅的合约列表
            with self.db.get_cursor() as c:
                c.execute('''
                    SELECT DISTINCT symbol 
                    FROM trading_signals 
                    WHERE processed = FALSE AND status = 'pending'
                ''')
                symbols = [row[0] for row in c.fetchall()]
            
            if not symbols:
                symbols = ['sp2501', 'rb2501', 'bu2501']  # 默认合约
                
            # 2. 只订阅尚未订阅的合约
            for symbol in symbols:
                full_symbol = f"{symbol}.{self.get_contract_info(symbol)['exchange'].value}"
                base_symbol = symbol.split('.')[0]  # 获取基础合约代码
                
                # 检查是否已经订阅
                if base_symbol not in self.market_api.subscribed_symbols:
                    self.app.subscribe(full_symbol)
                    logger.debug(f"尝试订阅新合约: {full_symbol}")
                
        except Exception as e:
            logger.error(f"订阅合约行情失败: {str(e)}")
            
    def setup(self):
        """初始化交易系统"""
        try:
            self.app.config.from_mapping(self.config)
            self.init_database()
            
            # 启动应用
            self.app.start(log_output=True)
            
            # 等待行情接口初始化
            wait_count = 0
            while not self.market_api.inited and wait_count < 10:
                time.sleep(10)
                wait_count += 1
                logger.info("等待行情接口初始化...")
                
            if not self.market_api.inited:
                raise RuntimeError("行情接口初始化超时")
                
            # 订阅合约行情
            self.subscribe_contracts()
            
            logger.info("交易系统启动成功")
        except Exception as e:
            logger.error(f"交易系统启动失败: {str(e)}")
            raise
            
    def init_database(self):
        """初始化数据库表"""
        try:
            with self.db.get_cursor() as c:
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
                logger.info("数据库初始化成功")
                
                # 添加账户数据表
                c.execute('''
                    CREATE TABLE IF NOT EXISTS account_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        balance REAL NOT NULL,           -- 账户余额
                        equity REAL NOT NULL,            -- 账户净值
                        available REAL NOT NULL,         -- 可用资金
                        position_profit REAL NOT NULL,   -- 持仓盈亏
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                logger.info("数据库初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
            raise
            
    def get_market_price(self, symbol: str) -> Optional[float]:
        """获取最新市场价格"""
        try:
            price = self.market_api.get_latest_price(symbol)
            logger.info(f"市场价格: {price}")
            return price
        except Exception as e:
            logger.error(f"获取市场价格失败: {str(e)}")
            return None
    
    def check_price_valid(self, symbol: str, price: float) -> bool:
        """检查价格是否在合理范围内"""
        market_price = self.get_market_price(symbol)
        if market_price is None:
            # 如果无法获取市场价格，暂时允许使用信号价格
            logger.warning(f"无法获取市场价格，使用信号价格: {symbol} {price}")
            return True
            
        price_diff = abs(price - market_price) / market_price
        valid = price_diff <= self.price_tolerance
        if not valid:
            logger.warning(f"价格超出容忍范围: {symbol} 信号价格:{price} 市场价格:{market_price} 差异:{price_diff:.2%}")
        return valid
    
    def get_contract_info(self, symbol: str) -> Dict:
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
        
    def generate_order_id(self) -> str:
        """生成唯一的订单ID"""
        return f"ORDER_{int(time.time()*1000)}_{int(time.perf_counter()*1000000)}"

    def create_order_request(self, symbol: str, price: float, volume: int, direction: str) -> Tuple[OrderRequest, Dict]:
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
            elif direction in ['BUY_CLOSE', 'SELL_CLOSE']:  # 平仓
                order_direction = Direction.SHORT if direction == 'SELL_CLOSE' else Direction.LONG
                # 获取持仓信息来决定平仓方式
                positions = self.app.center.positions
                for pos in positions:
                    if pos.symbol == symbol and (
                        (direction == 'SELL_CLOSE' and pos.direction == Direction.LONG) or
                        (direction == 'BUY_CLOSE' and pos.direction == Direction.SHORT)
                    ):
                        # 如果有昨仓，优先平昨
                        if pos.yd_volume > 0:
                            order_offset = Offset.CLOSEYESTERDAY
                            logger.info(f"使用平昨仓: {symbol} 昨仓数量:{pos.yd_volume}")
                        else:
                            order_offset = Offset.CLOSETODAY
                            logger.info(f"使用平今仓: {symbol} 今仓数量:{pos.volume}")
                        break
                else:
                    # 如果没找到对应持仓，使用普通平仓
                    order_offset = Offset.CLOSE
                    logger.info(f"使用普通平仓: {symbol}")
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
            logger.info(f"创建订单请求: {order_req}")
            return order_req, contract_info
            
        except Exception as e:
            logger.error(f"创建订单请求失败: {str(e)}")
            raise

    def execute_order(self, symbol: str, price: float, volume: int, direction: str, signal_id: int) -> bool:
        """执行下单操作"""
        try:
            # 检查是否会超过最大持仓限制(开仓时)
            if direction in ['BUY', 'SELL']:
                # 获取当前持仓
                pos_direction = 'LONG' if direction == 'BUY' else 'SHORT'
                current_pos = self.position_manager.get_position(symbol, direction)
                # 检查是否会超过限制
                if current_pos + volume > self.position_manager.max_position:
                    logger.error(f"开仓将超过最大限制: {symbol} {pos_direction} "
                               f"当前:{current_pos} 新增:{volume} "
                               f"最大:{self.position_manager.max_position}")
                    return False
            
            # 获取市场价格
            market_price = self.get_market_price(symbol)
            
            # 确定使用的价格
            use_price = market_price if market_price is not None else price
            
            # 检查持仓是否足够(平仓时)
            if direction in ['BUY_CLOSE', 'SELL_CLOSE']:
                current_pos = self.position_manager.get_position(symbol, direction)
                if current_pos < volume:
                    logger.error(f"持仓不足: {symbol} {direction} 当前持仓:{current_pos} 所需:{volume}")
                    return False
            
            # 创建下单请求和获取合约信息
            order_req, contract_info = self.create_order_request(symbol, use_price, volume, direction)
            success = False
            
            # 发送订单并获取结果
            order_result = self.app.send_order(order_req)
            logger.info(f"订单发送结果: {order_result}")
            
            # 判断订单是否成功
            if not isinstance(order_result, dict):
                success = True
                order_id = order_result
            elif not order_result.get('ErrorID'):
                success = True
                order_id = order_result
            else:
                success = False
                error_msg = order_result.get('ErrorMsg', '未知错误')
                logger.error(f"订单发送失败: {error_msg}")
            
            if success:
                logger.info(f"订单发送成功: {direction} {symbol} 价格:{use_price} 数量:{volume} "
                          f"订单ID:{order_id} 合约乘数:{contract_info['size']}")
                
                # 更新数据库中的订单状态
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals 
                        SET order_id = ?, status = 'submitted'
                        WHERE id = ?
                    ''', (order_id, signal_id))
                
                # 只有在订单真正成功时才更新持仓信息
                self.position_manager.update_position(symbol, direction, volume)
                return True
            else:
                # 更新数据库中的订单状态为失败
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals 
                        SET status = 'failed',
                            process_time = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (signal_id,))
                return False
                
        except Exception as e:
            logger.error(f"下单执行异常: {str(e)}")
            logger.error(f"订单信息: symbol={symbol}, price={price}, volume={volume}, "
                      f"direction={direction}")
            return False
    
    def process_signal(self, signal):
        """处理交易信号"""
        try:
            symbol = signal['symbol']
            action = signal['action'].upper()
            
            valid_actions = {'BUY', 'SELL', 'BUY_CLOSE', 'SELL_CLOSE'}
            if action not in valid_actions:
                raise ValueError(f"无效的交易动作: {action}")
            
            price = float(signal['price'])
            volume = int(signal.get('volume', 1))
            signal_id = signal['id']
            
            # 检查价格是否合理
            if not self.check_price_valid(symbol, price):
                logger.warning(f"价格超出容忍范围: {symbol} {price}")
                # 新信号状态为价格无效
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals
                        SET processed = TRUE, 
                            process_time = CURRENT_TIMESTAMP,
                            status = 'price_invalid'
                        WHERE id = ?
                    ''', (signal_id,))
                return False
            
            if self.execute_order(symbol, price, volume, action, signal_id):
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals
                        SET processed = TRUE, 
                            process_time = CURRENT_TIMESTAMP,
                            status = 'processed'
                        WHERE id = ?
                    ''', (signal_id,))
                
                logger.info(f"信号处理完成: ID={signal_id}")
            else:
                logger.error(f"信号处理失败: ID={signal_id}")
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals
                        SET status = 'failed'
                        WHERE id = ?
                    ''', (signal_id,))
            
        except Exception as e:
            logger.error(f"处理信号失败: {str(e)}")
            
    def monitor_signals(self):
        """监控交易信号"""
        logger.info("开始监控交易信号")
        last_subscribe_time = 0
        subscribe_interval = 60  # 订阅检查间隔（秒）
        
        while True:
            try:
                current_time = time.time()
                # 每隔一定时间检查一次订阅
                if current_time - last_subscribe_time >= subscribe_interval:
                    self.subscribe_contracts()
                    last_subscribe_time = current_time
                
                # 处理交易信号
                with self.db.get_cursor() as c:
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
                        
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"信号监控出错: {str(e)}")
                time.sleep(5)

def main():
    try:
        monitor = SignalMonitor()
        monitor.setup()
        monitor.monitor_signals()
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()