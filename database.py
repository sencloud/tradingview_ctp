import sqlite3
from sqlite3 import Connection
from contextlib import contextmanager
import threading
import logging

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """数据库连接管理器"""
    def __init__(self):
        self._local = threading.local()
        
    def get_connection(self) -> Connection:
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect('signals.db', check_same_thread=False)
        return self._local.conn
        
    @contextmanager
    def get_cursor(self):
        try:
            cursor = self.get_connection().cursor()
            yield cursor
            self.get_connection().commit()
        except Exception as e:
            if hasattr(self._local, 'conn') and self._local.conn:
                self.get_connection().rollback()
            raise e
        finally:
            cursor.close()

    def init_database(self):
        """初始化数据库表"""
        try:
            with self.get_cursor() as c:
                c.execute('''
                    CREATE TABLE IF NOT EXISTS trading_signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        action TEXT NOT NULL,
                        price REAL NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        volume INTEGER DEFAULT 1,
                        strategy TEXT,
                        processed BOOLEAN DEFAULT FALSE,
                        process_time DATETIME,
                        order_id TEXT,
                        status TEXT DEFAULT 'pending',
                        message TEXT
                    )
                ''')
                logger.info("交易信号表初始化成功")
                
                # 添加账户数据表
                c.execute('''
                    CREATE TABLE IF NOT EXISTS account_info (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        balance REAL NOT NULL,           -- 账户余额
                        equity REAL NOT NULL,            -- 账户净值
                        available REAL NOT NULL,         -- 可用资金
                        position_profit REAL NOT NULL,   -- 持仓盈亏
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                logger.info("账户信息表初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {str(e)}")
            raise 