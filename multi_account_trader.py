import streamlit as st
import json
import glob
import atexit
from pathlib import Path
from ctpbee import CtpBee, CtpbeeApi
from ctpbee.constant import OrderRequest, Direction, Offset, OrderType, Exchange
import pandas as pd
import time
from queue import Queue
from threading import Lock

# 全局订单记录队列
order_queue = Queue()
trade_queue = Queue()
records_lock = Lock()
all_records = []

# 初始化session state
if 'account_manager' not in st.session_state:
    st.session_state['account_manager'] = None
    
if 'order_records' not in st.session_state:
    st.session_state['order_records'] = []

# 合约规格信息
CONTRACT_SPECS = {    
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

class TraderApi(CtpbeeApi):
    def __init__(self, name, account_name):
        super().__init__(name)
        self.account_name = account_name
        
    def on_order(self, order):
        """订单回报"""
        record = {
            'account': self.account_name,
            'order_id': order.order_id,
            'symbol': order.symbol,
            'direction': "买入" if order.direction == Direction.LONG else "卖出",
            'offset': "开仓" if order.offset == Offset.OPEN else "平仓",
            'price': order.price,
            'volume': order.volume,
            'traded': order.traded,
            'status': order.status.value,
            'time': time.strftime("%H:%M:%S"),
        }
        order_queue.put(record)
        print(f"订单回报 - {self.account_name}: {record}")
        
    def on_trade(self, trade):
        """成交回报"""
        record = {
            'account': self.account_name,
            'trade_id': trade.trade_id,
            'order_id': trade.order_id,
            'symbol': trade.symbol,
            'direction': "买入" if trade.direction == Direction.LONG else "卖出",
            'offset': "开仓" if trade.offset == Offset.OPEN else "平仓",
            'price': trade.price,
            'volume': trade.volume,
            'time': time.strftime("%H:%M:%S"),
        }
        trade_queue.put(record)
        print(f"成交回报 - {self.account_name}: {record}")

class AccountManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AccountManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if not self.initialized:
            self.accounts = {}
            self.load_accounts()
            atexit.register(self.cleanup)
            self.initialized = True
            
    def cleanup(self):
        """清理所有连接"""
        for account_name in list(self.accounts.keys()):
            self.disconnect_account(account_name)
            
    def load_accounts(self):
        """加载所有配置文件"""
        config_files = glob.glob('config*.json')
        for config_file in config_files:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    account_name = Path(config_file).stem
                    self.accounts[account_name] = {
                        'config': config,
                        'app': None,
                        'connected': False
                    }
            except Exception as e:
                st.error(f"加载配置文件 {config_file} 失败: {str(e)}")
                
    def connect_account(self, account_name):
        """连接指定账户"""
        if account_name not in self.accounts:
            st.error(f"账户 {account_name} 不存在")
            return False
            
        account = self.accounts[account_name]
        if account['app'] is not None:
            # 如果已经有实例，先断开
            st.info(f"账户 {account_name} 已存在实例，正在断开...")
            self.disconnect_account(account_name)
            
        try:
            # 使用账户名作为唯一标识
            unique_name = f"trader_{account_name}_{int(time.time())}"
            st.info(f"正在创建交易实例: {unique_name}")
            
            app = CtpBee(unique_name, __name__, refresh=True)
            
            # 添加交易API
            trader_api = TraderApi("trader", account_name)
            app.add_extension(trader_api)
            
            # 使用原始配置
            config = account['config'].copy()
            # 只添加必要的配置
            config.update({
                "INTERFACE": "ctp",
                "TD_FUNC": True,
                "MD_FUNC": True
            })
            
            st.info(f"正在配置账户 {account_name}...")
            
            app.config.from_mapping(config)
            account['app'] = app
            
            # 启动实例
            st.info(f"正在启动账户 {account_name}...")
            app.start()
            
            # 等待行情和交易接口连接成功
            st.info(f"等待账户 {account_name} 连接...")
            for i in range(30):
                md_connected = app.center.md_status
                td_connected = app.center.td_status
                
                if md_connected and td_connected:
                    account['connected'] = True
                    st.success(f"{account_name} - 连接成功!")
                    st.info(f"{account_name} - 行情接口: {'已连接' if md_connected else '未连接'}")
                    st.info(f"{account_name} - 交易接口: {'已连接' if td_connected else '未连接'}")
                    return True
                
                if i % 5 == 0:  # 每5秒显示一次状态
                    st.info(f"{account_name} - 正在连接... ({i+1}/30)")
                time.sleep(1)
                
            # 连接超时，显示具体状态
            md_status = app.center.md_status
            td_status = app.center.td_status
            st.error(f"{account_name} - 连接超时! 行情接口: {'已连接' if md_status else '未连接'}, 交易接口: {'已连接' if td_status else '未连接'}")
            self.disconnect_account(account_name)
            return False
            
        except Exception as e:
            import traceback
            st.error(f"{account_name} - 连接失败: {str(e)}")
            print(f"详细错误信息: {traceback.format_exc()}")  # 打印详细错误信息
            self.disconnect_account(account_name)
            return False
            
    def disconnect_account(self, account_name):
        """断开指定账户"""
        if account_name not in self.accounts:
            return False
            
        account = self.accounts[account_name]
        if account['app'] is not None:
            try:
                print("断开连接")
                account['app'].release()  # 使用 release() 释放资源
                time.sleep(1)  # 等待资源释放
            except Exception as e:
                st.error(f"断开连接时发生错误: {str(e)}")
            finally:
                account['app'] = None
                account['connected'] = False
        return True
        
    def place_order(self, account_name, symbol, direction, offset, price, volume):
        """下单"""
        if not self.accounts[account_name]['connected']:
            return False, "账户未连接"
            
        app = self.accounts[account_name]['app']
        if app is None:
            return False, "交易实例不存在"
            
        try:
            # 获取合约信息
            product_code = ''.join(filter(str.isalpha, symbol.upper()))
            if product_code not in CONTRACT_SPECS:
                return False, f"未知合约品种: {product_code}"
                
            contract_info = CONTRACT_SPECS[product_code]
            
            # 构建订单请求
            req = OrderRequest(
                symbol=symbol,
                exchange=contract_info['exchange'],
                direction=Direction.LONG if direction == "买入" else Direction.SHORT,
                offset=Offset.OPEN if offset == "开仓" else Offset.CLOSE,
                type=OrderType.LIMIT,
                price=float(price),
                volume=int(volume),
                gateway_name="ctp"
            )
            
            # 发送订单
            order_id = app.send_order(req)
            return True, f"订单已发送，订单号: {order_id}"
        except Exception as e:
            return False, f"下单失败: {str(e)}"

    def connect_all_accounts(self):
        """连接所有账户"""
        results = []
        for account_name in self.accounts.keys():
            success = self.connect_account(account_name)
            results.append((account_name, success))
        return results
            
    def place_order_all(self, symbol, direction, offset, price, volume):
        """对所有已连接账户同时下单"""
        results = []
        for account_name, account in self.accounts.items():
            if account['connected']:
                success, message = self.place_order(account_name, symbol, direction, offset, price, volume)
                results.append((account_name, success, message))
        return results

# 初始化账户管理器（使用session state）
if st.session_state['account_manager'] is None:
    st.session_state['account_manager'] = AccountManager()
account_manager = st.session_state['account_manager']

# 页面标题
st.title("多账户快速下单系统")

# 处理订单和成交记录队列
def process_queues():
    # 处理订单记录
    while not order_queue.empty():
        record = order_queue.get()
        with records_lock:
            all_records.append(record)
            
    # 处理成交记录
    while not trade_queue.empty():
        record = trade_queue.get()
        with records_lock:
            all_records.append(record)

# 定期处理队列
process_queues()

# 账户连接控制
col1, col2 = st.columns(2)
with col1:
    if st.button("连接所有账户"):
        results = account_manager.connect_all_accounts()
        for account_name, success in results:
            if success:
                st.success(f"账户 {account_name} 连接成功")
            else:
                st.error(f"账户 {account_name} 连接失败")
                
with col2:
    if st.button("断开所有连接"):
        for account_name in list(account_manager.accounts.keys()):
            if account_manager.disconnect_account(account_name):
                st.info(f"账户 {account_name} 已断开连接")

# 检查是否有任何账户已连接
any_account_connected = any(account['connected'] for account in account_manager.accounts.values())

# 下单表单
if any_account_connected:
    st.subheader("下单信息")
    col1, col2 = st.columns(2)

    with col1:
        symbol = st.text_input("合约代码", "m2505")
        direction = st.selectbox("方向", ["买入", "卖出"])
        offset = st.selectbox("开平", ["开仓", "平仓"])

    with col2:
        price = st.number_input("价格", min_value=0.0, value=3000.0, step=1.0)
        volume = st.number_input("数量", min_value=1, value=1, step=1)

    # 下单按钮
    if st.button("所有账户同时下单"):
        results = account_manager.place_order_all(symbol, direction, offset, price, volume)
        for account_name, success, message in results:
            if success:
                st.success(f"{account_name}: {message}")
            else:
                st.error(f"{account_name}: {message}")

# 显示账户状态
st.subheader("账户状态")
for account_name, account in account_manager.accounts.items():
    status = "已连接" if account['connected'] else "未连接"
    st.text(f"{account_name}: {status}")

# 显示订单记录
if all_records:
    st.subheader("订单记录")
    with records_lock:
        df = pd.DataFrame(all_records)
    st.dataframe(df) 