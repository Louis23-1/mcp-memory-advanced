"""简单启动测试：验证 memory_advanced.py 可以正常导入并初始化数据库。"""
import sys
sys.path.insert(0, ".")
from memory_advanced import db, DB_PATH, EMBED_MODEL

print(f"数据库路径: {DB_PATH}")
print(f"表列表: {db.table_names()}")
print(f"语义模型状态: {'已加载' if EMBED_MODEL else '未加载（关键词模式）'}")
print("启动测试通过 [OK]")
