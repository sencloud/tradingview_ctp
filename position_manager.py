from typing import Dict
import logging
from ctpbee import CtpBee
from ctpbee.constant import Direction

logger = logging.getLogger(__name__)

class PositionManager:
    """持仓管理器"""
    def __init__(self, app: CtpBee = None):
        self.positions: Dict[str, Dict] = {}
        self.max_position = 2
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
                volume = position.volume
                
                self.positions[symbol][direction] = volume
                
                logger.info(f"初始化持仓: {symbol} {direction} "
                          f"总量:{volume} 昨仓:{position.yd_volume}")
                
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
        
        # 修复：直接使用 LONG/SHORT 作为方向
        if direction in ['LONG', 'BUY', 'SELL_CLOSE']:
            pos_direction = 'LONG'
        elif direction in ['SHORT', 'SELL', 'BUY_CLOSE']:
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

    def check_position_limit(self, symbol: str, direction: str, volume: int) -> bool:
        """检查持仓限制和平仓条件"""
        # 平仓操作检查
        if direction == 'BUY_CLOSE':  # 买平，检查空头持仓
            current_pos = self.get_position(symbol, 'SHORT')
            if current_pos < volume:
                logger.warning(f"空头持仓不足: {symbol} 当前持仓:{current_pos} 平仓量:{volume}")
                return False
            return True
            
        elif direction == 'SELL_CLOSE':  # 卖平，检查多头持仓
            current_pos = self.get_position(symbol, 'LONG')
            if current_pos < volume:
                logger.warning(f"多头持仓不足: {symbol} 当前持仓:{current_pos} 平仓量:{volume}")
                return False
            return True
            
        # 开仓操作检查
        elif direction in ['BUY', 'SELL']:
            pos_direction = 'LONG' if direction == 'BUY' else 'SHORT'
            current_pos = self.get_position(symbol, direction)
            
            if current_pos + volume > self.max_position:
                logger.warning(f"持仓超过限制: {symbol} {pos_direction} "
                             f"当前持仓:{current_pos} 新增:{volume} "
                             f"最大限制:{self.max_position}")
                return False
            return True
            
        else:
            logger.error(f"未知交易方向: {direction}")
            return False 