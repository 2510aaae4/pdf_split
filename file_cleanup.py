import tempfile
import shutil
import os
import logging
from typing import List

_temp_dirs = []
_temp_files = []

def create_temp_dir() -> str:
    d = tempfile.mkdtemp()
    _temp_dirs.append(d)
    logging.getLogger("file_cleanup").info(f"建立暫存目錄: {d}")
    return d

def register_temp_file(path: str):
    if os.path.exists(path):
        _temp_files.append(path)
        logging.getLogger("file_cleanup").info(f"註冊暫存檔案: {path}")

def cleanup_files():
    logger = logging.getLogger("file_cleanup")
    # 刪除檔案
    for f in _temp_files:
        try:
            if os.path.exists(f):
                os.remove(f)
                logger.info(f"已刪除暫存檔案: {f}")
        except Exception as e:
            logger.warning(f"刪除檔案失敗: {f}, {e}")
    _temp_files.clear()
    # 刪除目錄
    for d in _temp_dirs:
        try:
            if os.path.exists(d):
                shutil.rmtree(d)
                logger.info(f"已刪除暫存目錄: {d}")
        except Exception as e:
            logger.warning(f"刪除目錄失敗: {d}, {e}")
    _temp_dirs.clear() 