#!/bin/bash

# 全局配置区
LOG_FILE="/root/tradingview_ctp/monitor.log"        # 监控日志
TRADING_LOG="/root/tradingview_ctp/trading.log"     # 交易日志
EXECUTOR_PATH="/root/tradingview_ctp/trade_executor.py"
CONDA_PATH="/root/miniconda3"
CONDA_ENV="py311"
ERROR_MSG="程序启动失败: 行情接口初化超时"          # 关键错误信息
MAX_RETRY=3                                        # 最大重试次数
RETRY_WAIT=5                                       # 初始重试间隔(秒)

# 初始化 conda
source "${CONDA_PATH}/etc/profile.d/conda.sh"

# 日志记录函数（优化自网页8）
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
}

# 进程清理函数（优化自网页5、网页9）
kill_process() {
    local process_name=$(basename $EXECUTOR_PATH)
    
    # 终止常规进程
    pkill -f "$process_name"
    sleep 2
    
    # 深度清理残留
    if pgrep -f "$process_name" >/dev/null; then
        log "WARN" "发现僵尸进程，强制清理..."
        pkill -9 -f "$process_name"
        sleep 1
    fi
}

# 重启服务函数（含指数退避重试机制）
restart_service() {
    local retry_count=0
    local current_wait=$RETRY_WAIT
    
    while [ $retry_count -lt $MAX_RETRY ]; do
        ((retry_count++))
        log "INFO" "开始第 ${retry_count} 次重启尝试"
        
        # 清理旧进程
        kill_process
        
        # 日志轮转（参考网页5）
        if [ $(du -k "$TRADING_LOG" | cut -f1) -gt 10240 ]; then
            mv "$TRADING_LOG" "${TRADING_LOG}.$(date +%Y%m%d%H%M)"
            touch "$TRADING_LOG"
        fi
        
        # 启动新进程
        cd $(dirname $EXECUTOR_PATH)
        conda activate $CONDA_ENV
        nohup python $EXECUTOR_PATH > trade_executor.log 2>&1 &
        
        # 验证启动
        sleep 10
        NEW_PID=$(pgrep -f "$EXECUTOR_PATH")
        if [ -n "$NEW_PID" ]; then
            log "INFO" "启动成功 (PID: $NEW_PID)"
            return 0
        else
            log "ERROR" "第 ${retry_count} 次启动失败"
            current_wait=$((current_wait * 2))
            sleep $current_wait
        fi
    done
    
    log "CRITICAL" "已达最大重试次数($MAX_RETRY)，停止尝试"
    exit 1
}

# 服务检查函数（含错误日志监控）
check_service() {
    # 进程状态检查
    if ! pgrep -f "$EXECUTOR_PATH" >/dev/null; then
        log "WARN" "服务进程不存在，触发重启"
        restart_service
        return
    fi
    
    # 错误日志监控（网页1、网页7方案）
    if grep -q "$ERROR_MSG" "$TRADING_LOG"; then
        log "ERROR" "检测到行情接口初始化超时，触发重启流程"
        > "$TRADING_LOG"  # 清空已处理错误
        restart_service
    fi
}

# 主循环（带计划任务功能）
while true; do
    # 计划重启时间
    if [ $(date +%H:%M) = "20:50" ]; then
        log "INFO" "触发计划重启"
        restart_service
        sleep 60
        continue
    fi
    
    # 常规检查
    check_service
    
    # 休眠周期
    sleep 60
done