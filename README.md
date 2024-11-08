# 交易信号监控系统

这是一个基于Vue 3 + Flask的实时交易信号监控系统，用于接收、显示和执行交易信号。

## 功能特点

- 实时接收TradingView的交易信号
- 可视化展示交易信号列表
- 自动执行交易指令
- 支持多种交易策略
- CTPBee期货交易接口集成

## 技术栈

### 前端
- Vue 3
- TypeScript
- Element Plus UI
- Vite
- Axios

### 后端
- Flask
- SQLite
- CTPBee (期货交易接口)
- Flask-CORS

## 系统架构

系统分为三个主要部分：
1. 前端界面：展示交易信号和状态
2. 后端API：处理信号接收和数据存储
3. 交易执行器：自动执行交易指令

## 快速开始

### 前端启动
```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 后端启动
```bash
# 进入后端目录
cd backend

# 安装Python依赖
pip install -r requirements.txt

# 启动Flask服务器
python app.py

# 启动交易执行器
python trade_executor.py
```

## 功能截图

![image](https://github.com/user-attachments/assets/4e27567c-c98d-4d93-af02-cd4fb4ccf565)
简单的一个列表页面，用来查看交易记录。

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
  "strategy": "策略名称"
}
```

### 2. 获取信号列表
- 端点：`/api/signals`
- 方法：GET
- 返回：所有交易信号列表

## 配置说明

交易配置文件位于 `backend/config_[sim|ctp].json`，包含：
- CTP连接信息
- 交易接口设置
- 行情和交易功能开关
- 刷新间隔设置

## 注意事项

1. 使用前请确保已配置正确的CTP账户信息
2. 建议在实盘交易前进行充分测试
3. 请确保网络环境稳定，以保证交易信号的及时接收和执行

## 免责声明
本项目开源仅作爱好，请谨慎使用，本人不对代码产生的任何使用后果负责。

## 其他
如果你喜欢我的项目，可以给我买杯咖啡：
<img src="https://github.com/user-attachments/assets/e75ef971-ff56-41e5-88b9-317595d22f81" alt="image" width="300" height="300">

## 开发计划

- [ ] 添加更多交易策略支持
- [ ] 实现信号回测功能
- [ ] 优化交易执行效率
- [ ] 添加风控模块

## 许可证

MIT License
