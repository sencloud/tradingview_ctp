import sqlite3
import os

def clean_database(db_path='signals.db'):
    """
    清空指定的 SQLite 数据库中的所有表数据
    
    Args:
        db_path (str): 数据库文件路径，默认为 'signals.db'
    """
    try:
        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            print(f"数据库文件 {db_path} 不存在")
            return

        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        # 删除每个表中的所有数据
        for table in tables:
            table_name = table[0]
            cursor.execute(f"DELETE FROM {table_name}")

        # 提交更改
        conn.commit()
        print("数据库已清空")

    except sqlite3.Error as e:
        print(f"清空数据库时发生错误: {e}")

    finally:
        # 关闭数据库连接
        if conn:
            conn.close()

if __name__ == "__main__":
    clean_database()
