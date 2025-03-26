#!/bin/bash

# 设置日志文件路径
LOG_FILE="/root/tradingview_ctp/monitor.log"
EXECUTOR_PATH="/root/tradingview_ctp/trade_executor.py"

# 设置 conda 环境
CONDA_PATH="/root/miniconda3"  # 修改为你的 conda 安装路径
CONDA_ENV="py311"             # 你的 conda 环境名称

# 初始化 conda
source "${CONDA_PATH}/etc/profile.d/conda.sh"

# 记录日志的函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 重启服务的函数
restart_service() {
    log "准备重启 trade_executor 服务..."
    
    # 查找并终止现有的进程
    OLD_PID=$(ps -ef | grep "python trade_executor.py" | grep -v grep | awk '{print $2}')
    if [ ! -z "$OLD_PID" ]; then
        log "终止旧进程 (PID: $OLD_PID)"
        kill $OLD_PID
        sleep 5
        
        # 检查进程是否仍在运行，如果是则强制终止
        if ps -p $OLD_PID > /dev/null; then
            log "进程未响应，强制终止"
            kill -9 $OLD_PID
            sleep 2
        fi
    else
        log "未发现运行中的进程"
    fi
    
    # 切换到正确的目录
    cd $(dirname $EXECUTOR_PATH)
    
    # 激活 conda 环境并启动新进程
    log "激活 conda 环境 ${CONDA_ENV}..."
    conda activate ${CONDA_ENV}
    
    log "启动新进程..."
    nohup python trade_executor.py > trade_executor.log 2>&1 &
    
    # 检查新进程是否成功启动
    NEW_PID=$(ps -ef | grep "python trade_executor.py" | grep -v grep | awk '{print $2}')
    if [ ! -z "$NEW_PID" ]; then
        log "服务成功重启 (新 PID: $NEW_PID)"
    else
        log "服务启动失败"
    fi
}

# 检查服务是否在运行的函数
check_service() {
    PID=$(ps -ef | grep "python trade_executor.py" | grep -v grep | awk '{print $2}')
    if [ -z "$PID" ]; then
        log "服务未运行，正在重启..."
        restart_service
    fi
}

# 主循环
while true; do
    # 获取当前时间
    CURRENT_HOUR=$(date +%H)
    CURRENT_MIN=$(date +%M)
    
    # 在 20:50 重启服务
    if [ "$CURRENT_HOUR" = "20" ] && [ "$CURRENT_MIN" = "50" ]; then
        log "达到计划重启时间"
        restart_service
        sleep 60  # 等待1分钟，避免在同一分钟内多次重启
    fi
    
    # 检查服务是否在运行
    check_service
    
    # 每分钟检查一次
    sleep 60
done 
