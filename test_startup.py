"""启动验证测试：验证 memory_advanced 模块导入和数据库初始化正常。"""
import os
import tempfile


def test_import_and_init():
    """模块导入 + 数据库创建应正常完成。"""
    # 使用临时数据库隔离测试环境
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    old_env = os.environ.get("MEMORY_DB_PATH")
    os.environ["MEMORY_DB_PATH"] = db_path

    try:
        from memory_advanced import db, DB_PATH, EMBED_MODEL

        assert DB_PATH == db_path, f"DB_PATH 应为 {db_path}，实际为 {DB_PATH}"
        assert "memories" in db.table_names(), "memories 表应已创建"
        # EMBED_MODEL 可以为 None（未安装 sentence-transformers），不报错即通过
    finally:
        if old_env is None:
            del os.environ["MEMORY_DB_PATH"]
        else:
            os.environ["MEMORY_DB_PATH"] = old_env
        # 清理临时数据库
        try:
            os.unlink(db_path)
            os.rmdir(tmpdir)
        except OSError:
            pass


def test_db_schema():
    """验证表结构包含正确的列和类型。"""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    old_env = os.environ.get("MEMORY_DB_PATH")
    os.environ["MEMORY_DB_PATH"] = db_path

    try:
        from memory_advanced import db

        raw_cols = db["memories"].columns
        cols = {}
        for c in raw_cols:
            if isinstance(c, (list, tuple)):
                name, ctype = c[1], c[2]
            else:
                name, ctype = c.name, c.type
            cols[name] = ctype
        assert "id" in cols
        assert "content" in cols
        assert "category" in cols
        assert "timestamp" in cols
        assert "embedding" in cols
        assert cols["id"] == "INTEGER", "id 应为 INTEGER"
        assert cols["embedding"] == "BLOB", "embedding 应为 BLOB（编程铁律第11条）"
    finally:
        if old_env is None:
            del os.environ["MEMORY_DB_PATH"]
        else:
            os.environ["MEMORY_DB_PATH"] = old_env
        try:
            os.unlink(db_path)
            os.rmdir(tmpdir)
        except OSError:
            pass
