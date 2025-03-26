from typing import Dict, Optional
import logging
from ctpbee import CtpBee, CtpbeeApi
from ctpbee.constant import (
    OrderRequest, 
    Direction, 
    Offset, 
    OrderType,
    Exchange,
    ContractData,
    TickData
)
from database import DatabaseConnection

logger = logging.getLogger(__name__)

class MarketDataApi(CtpbeeApi):
    """行情API"""
    def __init__(self, name: str, app: CtpBee):
        super().__init__(name, app)
        self.ticks: Dict[str, TickData] = {}
        self.subscribed_symbols: set = set()  # 记录已订阅的合约
        self.inited = False
        self.db = DatabaseConnection()
        logger.info("MarketDataApi initialized")
        
    def on_init(self, init: bool):
        """行情接口初始化回调"""
        self.inited = init
        logger.info(f"MarketDataApi on_init: {init}")
        
    def on_tick(self, tick: TickData) -> None:
        """处理TICK数据"""
        self.ticks[tick.symbol] = tick
        self.subscribed_symbols.add(tick.symbol)  # 记录收到TICK数据的合约
        
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
        """处理账户数据"""
        try:
            # 计算所有持仓的浮动盈亏
            total_float_pnl = 0
            positions = self.app.center.positions
            for pos in positions:
                total_float_pnl += pos.float_pnl if pos.float_pnl is not None else 0

            with DatabaseConnection().get_cursor() as c:
                c.execute('''
                    INSERT INTO account_info (balance, equity, available, position_profit)
                    VALUES (?, ?, ?, ?)
                ''', (
                    account.balance,                    # 账户余额
                    account.balance + total_float_pnl,  # 净值 = 余额 + 浮动盈亏
                    account.available,                  # 可用资金
                    total_float_pnl                     # 持仓盈亏（使用浮动盈亏）
                ))
        except Exception as e:
            logger.error(f"更新账户数据失败: {str(e)}")
            logger.exception("详细错误信息:")

    def on_order(self, order) -> None:
        """处理订单状态更新"""
        try:
            # 映射订单状态到我们的状态系统
            status_map = {
                "SUBMITTING": "pending",      # 提交中
                "NOTTRADED": "pending",       # 未成交
                "PARTTRADED": "partial",      # 部分成交
                "ALLTRADED": "filled",        # 全部成交
                "CANCELLED": "cancelled",     # 已撤销
                "REJECTED": "rejected",       # 已拒绝
                "UNKNOWN": "failed"            # 未知状态
            }
            
            # 获取状态字符串
            order_status = str(order.status).replace('Status.', '')
            current_status = status_map.get(order_status, "error")
            
            logger.info(f"订单状态: {order.status}")
            
            # 更新数据库中的订单状态
            with self.db.get_cursor() as c:
                c.execute('''
                    UPDATE trading_signals 
                    SET status = ?,
                        process_time = CASE 
                            WHEN status IN ('filled', 'cancelled', 'rejected', 'failed') 
                            THEN CURRENT_TIMESTAMP 
                            ELSE process_time 
                        END,
                        processed = CASE 
                            WHEN status IN ('filled', 'cancelled', 'rejected', 'failed') 
                            THEN TRUE 
                            ELSE processed 
                        END
                    WHERE order_id = ?
                ''', (current_status, "ctp."+order.order_id))

            # 记录状态变化
            logger.info(f"订单状态更新: ID={order.order_id} "
                       f"状态={current_status} "
                       f"总量={order.volume} "
                       f"已成交={order.traded}")

            # 如果订单完成（成交、拒绝、撤销、错误），记录详细信息
            if current_status in ['filled', 'rejected', 'cancelled', 'failed']:
                logger.info(f"订单完成: ID=ctp.{order.order_id} "
                          f"最终状态={current_status} "
                          f"成交量={order.traded}/{order.volume}")

        except Exception as e:
            logger.error(f"处理订单状态更新失败: {str(e)}")
            logger.exception("详细错误信息:")

    def on_trade(self, trade) -> None:
        """处理成交回报"""
        try:
            logger.info(f"收到成交回报: 订单ID={trade.order_id} "
                       f"价格={trade.price} "
                       f"数量={trade.volume} "
                       f"方向={trade.direction} "
                       f"开平={trade.offset}")

        except Exception as e:
            logger.error(f"处理成交回报失败: {str(e)}")
            logger.exception("详细错误信息:") 