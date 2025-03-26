import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import plotly.graph_objects as go

# 设置页面配置
st.set_page_config(
    page_title="交易信号仪表板",
    page_icon="📈",
    layout="wide"
)

# 数据库连接函数
def get_db_connection():
    conn = sqlite3.connect('signals.db')
    return conn

# 获取交易信号数据
def get_trading_signals():
    conn = get_db_connection()
    query = '''
    SELECT id, symbol, action, price, volume, timestamp, status, processed, process_time
    FROM trading_signals 
    ORDER BY timestamp DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 获取账户数据
def get_account_data():
    conn = get_db_connection()
    query = '''
    SELECT balance, equity, available, position_profit, timestamp
    FROM account_info
    ORDER BY timestamp DESC
    LIMIT 1
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# 主页面标题
st.title("📈 交易信号仪表板")

# 侧边栏过滤器
st.sidebar.header("筛选条件")
time_range = st.sidebar.selectbox(
    "时间范围",
    ["最近24小时", "最近7天", "最近30天", "全部时间"]
)

# 获取数据
signals_df = get_trading_signals()
account_df = get_account_data()

# 转换时间戳
signals_df['timestamp'] = pd.to_datetime(signals_df['timestamp'])

# 根据时间范围过滤数据
if time_range == "最近24小时":
    signals_df = signals_df[signals_df['timestamp'] > datetime.now() - timedelta(days=1)]
elif time_range == "最近7天":
    signals_df = signals_df[signals_df['timestamp'] > datetime.now() - timedelta(days=7)]
elif time_range == "最近30天":
    signals_df = signals_df[signals_df['timestamp'] > datetime.now() - timedelta(days=30)]

# 创建三列布局
col1, col2, col3 = st.columns(3)

# 账户信息卡片
with col1:
    if not account_df.empty:
        st.metric(
            label="账户余额",
            value=f"¥{account_df['balance'].iloc[0]:,.2f}",
            delta=f"¥{account_df['balance'].iloc[0] - 200000:,.2f}"
        )

with col2:
    if not account_df.empty:
        st.metric(
            label="可用资金",
            value=f"¥{account_df['available'].iloc[0]:,.2f}"
        )

with col3:
    if not account_df.empty:
        st.metric(
            label="持仓盈亏",
            value=f"¥{account_df['position_profit'].iloc[0]:,.2f}"
        )

# 交易信号统计
st.subheader("交易信号概览")
signal_stats = signals_df.groupby('action').size().reset_index(name='count')
fig = px.pie(signal_stats, values='count', names='action', title='信号分布')
st.plotly_chart(fig, use_container_width=True)

# 最近交易信号表格
st.subheader("最近交易信号")
st.dataframe(
    signals_df,
    column_config={
        "timestamp": st.column_config.DatetimeColumn(
            "信号时间",
            format="YYYY-MM-DD HH:mm:ss",
            timezone="Asia/Shanghai",  # 加8小时，使用北京时间
        ),
        "process_time": st.column_config.DatetimeColumn(
            "处理时间",
            format="YYYY-MM-DD HH:mm:ss",
            timezone="Asia/Shanghai",  # 加8小时，使用北京时间
        ),
        "symbol": "交易品种",
        "action": "交易动作",
        "price": st.column_config.NumberColumn(
            "价格",
            format="%.2f",
        ),
        "volume": "数量",
        "processed": "已处理?",
        "strategy": "方向",
        "status": "状态",
    },
    hide_index=True
)

# 时间序列图
st.subheader("信号时间线")
if not signals_df.empty:
    # 按30分钟重采样数据
    timeline_df = (signals_df
                  .set_index('timestamp')
                  .tz_localize('UTC')
                  .tz_convert('Asia/Shanghai')
                  .resample('30T')  # 改为30分钟('30T')而不是1小时('h')
                  .size()
                  .reset_index())
    timeline_df.columns = ['timestamp', 'count']
    
    # 创建时间线图
    fig = go.Figure()
    
    # 添加信号数量线
    fig.add_trace(go.Scatter(
        x=timeline_df['timestamp'],
        y=timeline_df['count'],
        mode='lines+markers',
        name='信号数量',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=6)
    ))
    
    # 更新布局
    fig.update_layout(
        title='信号随时间变化 (北京时间)',
        xaxis_title='时间',
        yaxis_title='信号数量',
        template='plotly_white',
        hovermode='x unified',
        xaxis=dict(
            tickformat='%Y-%m-%d %H:%M',
            tickangle=45
        ),
        showlegend=True
    )
    
    # 显示图表
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("当前时间段内没有交易信号数据") 