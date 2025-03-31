# 交易信号监控系统

这是一个基于Streamlit + Flask的实时交易信号监控系统，用于接收、显示和执行交易信号。

## 功能特点

- 实时接收TradingView的交易信号
- 可视化展示交易信号列表和统计
- 自动执行交易指令
- 支持多种交易策略
- CTPBee期货交易接口集成
- 实时账户资金和持仓监控
- 交易信号回测功能
- 支持多品种期货合约
- 自动平仓和风控功能

## 技术栈

### 前端
- Streamlit (数据可视化)

### 后端
- Flask
- SQLite
- CTPBee (期货交易接口)
- Flask-CORS
- NumExpr (高性能计算)

## 系统架构

系统分为三个主要部分：
1. 数据可视化：使用Streamlit展示交易统计和图表
2. 后端API：处理信号接收和数据存储
3. 交易执行器：自动执行交易指令

## 快速开始

### 启动系统
```bash

# 安装Python依赖
pip install -r requirements.txt

# 启动Flask服务器
python app.py

# 启动交易执行器
python trade_executor.py

# 启动数据可视化
streamlit run streamlit_app.py
```

## 功能截图

![image](https://github.com/user-attachments/assets/4885cd52-b9c6-4b2f-8d63-ecb88b8fa1f5)


## API接口

### 1. 接收交易信号
- 端点：`/webhook`
- 方法：POST
- 数据格式：
```json
{
  "symbol": "交易品种",
  "action": "BUY/SELL",
  "price": 价格,
  "strategy": "前一个动作名称（long/short/flat）",
  "volume": 交易数量
}
```

### 2. 获取信号列表
- 端点：`/api/signals`
- 方法：GET
- 返回：所有交易信号列表

### 3. 获取账户信息
- 端点：`/api/profits`
- 方法：GET
- 返回：账户余额、可用资金、持仓盈亏等信息

## 配置说明

交易配置文件位于 `backend/config_[sim|ctp].json`，包含：
- CTP连接信息
- 交易接口设置
- 行情和交易功能开关
- 刷新间隔设置
- 最大持仓限制
- 合约规格信息

## 数据库结构

### trading_signals 表
- id: 信号ID
- symbol: 交易品种
- action: 交易动作
- price: 价格
- timestamp: 时间戳
- volume: 交易数量
- strategy: 策略名称
- processed: 处理状态
- process_time: 处理时间
- order_id: 订单ID
- status: 订单状态
- message: 消息说明

### account_info 表
- id: 记录ID
- balance: 账户余额
- equity: 账户净值
- available: 可用资金
- position_profit: 持仓盈亏
- timestamp: 时间戳

## 注意事项

1. 使用前请确保已配置正确的CTP账户信息
2. 建议在实盘交易前进行充分测试
3. 请确保网络环境稳定，以保证交易信号的及时接收和执行
4. 系统默认最大持仓限制为2手，可在配置文件中修改
5. 支持自动区分平今仓和平昨仓
6. 使用NumExpr优化计算性能，默认最大线程数为8

## 免责声明
本项目开源仅作爱好，请谨慎使用，本人不对代码产生的任何使用后果负责。

## 其他
如果你喜欢我的项目，可以给我买杯咖啡：
<img src="https://github.com/user-attachments/assets/e75ef971-ff56-41e5-88b9-317595d22f81" alt="image" width="300" height="300">

## 许可证

MIT License
