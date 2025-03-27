import logging
import json
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from ctpbee import CtpBee
from ctpbee.constant import (
    OrderRequest, 
    Direction, 
    Offset, 
    OrderType,
    Exchange
)
from database import DatabaseConnection
from position_manager import PositionManager
from market_data import MarketDataApi

logger = logging.getLogger(__name__)

class SignalMonitor:
    def __init__(self):
        self.app = CtpBee("signal_trader", __name__, refresh=True)
        self.market_api = MarketDataApi("market", self.app)
        self.app.add_extension(self.market_api)
        self.contract_specs = self.load_contract_specs()
        self.load_config()
        self.db = DatabaseConnection()
        self.position_manager = PositionManager(self.app)
        self.max_position = 2  # 添加最大持仓限制
        
    def load_contract_specs(self):
        """加载合约规格"""
        return {
            # 中金所
            'IF': {'size': 300, 'exchange': Exchange.CFFEX},   # 沪深300股指
            'IC': {'size': 200, 'exchange': Exchange.CFFEX},   # 中证500股指
            'IH': {'size': 300, 'exchange': Exchange.CFFEX},   # 上证50股指
            'IM': {'size': 200, 'exchange': Exchange.CFFEX},   # 中证1000股指
            
            # 上期所
            'FU': {'size': 10, 'exchange': Exchange.SHFE}, 
            'AG': {'size': 15, 'exchange': Exchange.SHFE},     # 白银
            'RU': {'size': 50, 'exchange': Exchange.SHFE},      # 橡胶
            'AL': {'size': 5, 'exchange': Exchange.SHFE},      # 铝
            'ZN': {'size': 5, 'exchange': Exchange.SHFE},      # 锌
            'AO': {'size': 20, 'exchange': Exchange.SHFE},      # 氧化铝
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
            symbols = ['ru2505']  # 默认合约
                
            # 只订阅尚未订阅的合约
            for symbol in symbols:
                full_symbol = f"{symbol}.{self.get_contract_info(symbol)['exchange'].value}"
                base_symbol = symbol.split('.')[0]  # 获取基础合约代码
                
                # 检查是否已经订阅
                if base_symbol not in self.market_api.subscribed_symbols:
                    self.app.subscribe(full_symbol)
                    logger.info(f"尝试订阅新合约: {full_symbol}")
                
        except Exception as e:
            logger.error(f"订阅合约行情失败: {str(e)}")
            
    def setup(self):
        """初始化交易系统"""
        try:
            self.app.config.from_mapping(self.config)
            self.db.init_database()
            
            # 启动应用
            self.app.start(log_output=True)
            
            # 等待行情接口初始化
            wait_count = 0
            while not self.market_api.inited and wait_count < 10:
                time.sleep(10)
                wait_count += 1
                logger.info("等待行情接口初始化...")
                
            if not self.market_api.inited:
                raise RuntimeError("行情接口初化超时")
                
            # 订阅合约行情
            self.subscribe_contracts()
            
            logger.info("交易系统启动成功")
        except Exception as e:
            logger.error(f"交易系统启动失败: {str(e)}")
            raise
            
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

    def create_order_request(self, symbol: str, price: float, volume: int, direction: str, 
                             force_offset: Optional[Offset] = None) -> Tuple[OrderRequest, Dict]:
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

    def execute_order(self, symbol: str, price: float, volume: int, direction: str, 
                     signal_id: int, force_offset: Optional[Offset] = None) -> bool:
        """执行下单操作"""
        try:
            # 检查当前持仓
            current_position = 0
            for pos in self.app.center.positions:
                if pos.symbol == symbol:
                    if (direction in ['BUY', 'SELL'] and  # 开仓操作
                        logger.info(f"当前持仓: {pos.symbol} {pos.direction} {pos.volume}")
                        ((direction == 'BUY' and pos.direction == Direction.LONG) or
                         (direction == 'SELL' and pos.direction == Direction.SHORT))):
                        current_position += pos.volume
            
            # 如果是开仓操作且会超过最大持仓限制，则拒绝订单
            if direction in ['BUY', 'SELL'] and current_position + volume > self.max_position:
                logger.warning(f"拒绝订单: {symbol} {direction} - 超过最大持仓限制 "
                             f"(当前:{current_position}, 最大:{self.max_position})")
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals 
                        SET status = 'rejected',
                            process_time = CURRENT_TIMESTAMP,
                            message = '超过最大持仓限制'
                        WHERE id = ?
                    ''', (signal_id,))
                return False
            
            use_price = price
            
            # 创建下单请求和获取合约信息，传入强制开平标志
            order_req, contract_info = self.create_order_request(
                symbol, use_price, volume, direction, force_offset
            )
            
            # 发送订单并获取结果
            order_result = self.app.send_order(order_req)
            # logger.info(f"订单发送结果: {order_result}")
            
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
            strategy = signal['strategy']
            price = float(signal['price'])
            signal_id = signal['id']
            volume = int(signal.get('volume', 1))

            if strategy.upper() == 'SHORT' and action == 'BUY':
                # 只平空
                close_action = 'BUY_CLOSE'
                close_success = True
                positions = self.app.center.positions
                for pos in positions:
                    if pos.symbol == symbol and pos.direction == Direction.SHORT:
                        if pos.yd_volume > 0:
                            logger.info(f"平昨仓: {symbol} {close_action} 数量:{pos.yd_volume}")
                            close_success &= self.execute_order(
                                symbol=symbol,
                                price=price,
                                volume=pos.yd_volume,
                                direction=close_action,
                                signal_id=signal_id,
                                force_offset=Offset.CLOSEYESTERDAY
                            )

                        today_volume = pos.volume - pos.yd_volume
                        if today_volume > 0:
                            logger.info(f"平今仓: {symbol} {close_action} 数量:{today_volume}")
                            close_success &= self.execute_order(
                                symbol=symbol,
                                price=price,
                                volume=today_volume,
                                direction=close_action,
                                signal_id=signal_id,
                                force_offset=Offset.CLOSETODAY
                            )

                status = 'processed' if close_success else 'failed'
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals
                        SET processed = TRUE, 
                            process_time = CURRENT_TIMESTAMP,
                            status = ?
                        WHERE id = ?
                    ''', (status, signal_id,))
                # return close_success

            elif strategy.upper() == 'LONG' and action == 'SELL':
                # 只平多
                close_action = 'SELL_CLOSE'
                close_success = True
                positions = self.app.center.positions
                for pos in positions:
                    if pos.symbol == symbol and pos.direction == Direction.LONG:
                        if pos.yd_volume > 0:
                            logger.info(f"平昨仓: {symbol} {close_action} 数量:{pos.yd_volume}")
                            close_success &= self.execute_order(
                                symbol=symbol,
                                price=price,
                                volume=pos.yd_volume,
                                direction=close_action,
                                signal_id=signal_id,
                                force_offset=Offset.CLOSEYESTERDAY
                            )

                        today_volume = pos.volume - pos.yd_volume
                        if today_volume > 0:
                            logger.info(f"平今仓: {symbol} {close_action} 数量:{today_volume}")
                            close_success &= self.execute_order(
                                symbol=symbol,
                                price=price,
                                volume=today_volume,
                                direction=close_action,
                                signal_id=signal_id,
                                force_offset=Offset.CLOSETODAY
                            )

                status = 'processed' if close_success else 'failed'
                with self.db.get_cursor() as c:
                    c.execute('''
                        UPDATE trading_signals
                        SET processed = TRUE, 
                            process_time = CURRENT_TIMESTAMP,
                            status = ?
                        WHERE id = ?
                    ''', (status, signal_id,))
                # return close_success

            # elif strategy.upper() == 'FLAT':
            # 开仓操作
            if action not in {'BUY', 'SELL'}:
                raise ValueError(f"无效的交易动作: {action}")
            return self.execute_order(symbol, price, volume, action, signal_id)

            # else:
            #     raise ValueError(f"无效的策略和动作组合: strategy={strategy}, action={action}")

        except Exception as e:
            logger.error(f"处理信号失败: {str(e)}")
            return False

    def monitor_signals(self):
        """监控交易信号"""
        logger.info("开始监控交易信号")
        last_subscribe_time = 0
        subscribe_interval = 60  # 订阅检查间隔（秒）
        processing_signals = set()  # 跟踪正在处理的信号
        
        while True:
            try:
                current_time = time.time()
                if current_time - last_subscribe_time >= subscribe_interval:
                    self.subscribe_contracts()
                    last_subscribe_time = current_time

                # 处理交易信号
                with self.db.get_cursor() as c:
                    # 只获取未处理且未提交的信号
                    c.execute('''
                        SELECT id, symbol, action, price, timestamp, 
                               volume, strategy, processed, status
                        FROM trading_signals
                        WHERE processed = FALSE 
                        AND status = 'pending'
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