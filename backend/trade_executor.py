import os
import logging
from signal_monitor import SignalMonitor

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
