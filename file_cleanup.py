"""
文件清理工具模組
實現臨時文件的生命週期管理和清理機制
"""

import os
import shutil
import time
import tempfile
import logging
import threading
from typing import Dict, List, Set, Optional, Callable
from pathlib import Path
from functools import wraps

# 配置日誌記錄
logger = logging.getLogger(__name__)

class FileCleanupError(Exception):
    """文件清理錯誤"""
    pass

class FileTracker:
    """文件追蹤器 - 用於追蹤臨時文件和目錄"""
    
    def __init__(self):
        self._tracked_files: Dict[str, Dict] = {}
        self._tracked_dirs: Dict[str, Dict] = {}
        self._lock = threading.Lock()
    
    def register_file(self, file_path: str, context: str = "default", 
                     max_age_minutes: int = 60) -> str:
        """
        註冊一個臨時文件
        
        Args:
            file_path: 文件路徑
            context: 文件上下文（例如：session_id, process_name）
            max_age_minutes: 最大保留時間（分鐘）
            
        Returns:
            str: 文件的唯一識別碼
        """
        with self._lock:
            file_id = f"{context}_{int(time.time())}_{os.path.basename(file_path)}"
            self._tracked_files[file_id] = {
                'path': file_path,
                'context': context,
                'created_time': time.time(),
                'max_age_minutes': max_age_minutes,
                'access_count': 0,
                'last_access': time.time()
            }
            logger.debug(f"註冊臨時文件: {file_id} -> {file_path}")
            return file_id
    
    def register_directory(self, dir_path: str, context: str = "default",
                          max_age_minutes: int = 60) -> str:
        """
        註冊一個臨時目錄
        
        Args:
            dir_path: 目錄路徑
            context: 目錄上下文
            max_age_minutes: 最大保留時間（分鐘）
            
        Returns:
            str: 目錄的唯一識別碼
        """
        with self._lock:
            dir_id = f"{context}_dir_{int(time.time())}_{os.path.basename(dir_path)}"
            self._tracked_dirs[dir_id] = {
                'path': dir_path,
                'context': context,
                'created_time': time.time(),
                'max_age_minutes': max_age_minutes,
                'access_count': 0,
                'last_access': time.time()
            }
            logger.debug(f"註冊臨時目錄: {dir_id} -> {dir_path}")
            return dir_id
    
    def access_file(self, file_id: str) -> Optional[str]:
        """
        訪問文件（更新訪問時間和計數）
        
        Args:
            file_id: 文件識別碼
            
        Returns:
            Optional[str]: 文件路徑，如果文件不存在則返回 None
        """
        with self._lock:
            if file_id in self._tracked_files:
                self._tracked_files[file_id]['last_access'] = time.time()
                self._tracked_files[file_id]['access_count'] += 1
                return self._tracked_files[file_id]['path']
            return None
    
    def get_expired_files(self, current_time: Optional[float] = None) -> List[Dict]:
        """
        獲取已過期的文件列表
        
        Args:
            current_time: 當前時間（秒），如果為 None 則使用系統時間
            
        Returns:
            List[Dict]: 已過期文件的資訊列表
        """
        if current_time is None:
            current_time = time.time()
        
        expired_files = []
        
        with self._lock:
            for file_id, info in self._tracked_files.items():
                age_minutes = (current_time - info['created_time']) / 60
                if age_minutes > info['max_age_minutes']:
                    expired_files.append({
                        'id': file_id,
                        'path': info['path'],
                        'context': info['context'],
                        'age_minutes': age_minutes,
                        'type': 'file'
                    })
            
            for dir_id, info in self._tracked_dirs.items():
                age_minutes = (current_time - info['created_time']) / 60
                if age_minutes > info['max_age_minutes']:
                    expired_files.append({
                        'id': dir_id,
                        'path': info['path'],
                        'context': info['context'],
                        'age_minutes': age_minutes,
                        'type': 'directory'
                    })
        
        return expired_files
    
    def unregister_file(self, file_id: str) -> bool:
        """
        取消註冊文件
        
        Args:
            file_id: 文件識別碼
            
        Returns:
            bool: 是否成功取消註冊
        """
        with self._lock:
            if file_id in self._tracked_files:
                del self._tracked_files[file_id]
                logger.debug(f"取消註冊文件: {file_id}")
                return True
            if file_id in self._tracked_dirs:
                del self._tracked_dirs[file_id]
                logger.debug(f"取消註冊目錄: {file_id}")
                return True
            return False
    
    def cleanup_by_context(self, context: str) -> List[str]:
        """
        清理指定上下文的所有文件
        
        Args:
            context: 上下文名稱
            
        Returns:
            List[str]: 已清理的文件路徑列表
        """
        cleaned_paths = []
        
        with self._lock:
            # 收集要清理的文件
            files_to_clean = []
            dirs_to_clean = []
            
            for file_id, info in self._tracked_files.items():
                if info['context'] == context:
                    files_to_clean.append((file_id, info['path']))
            
            for dir_id, info in self._tracked_dirs.items():
                if info['context'] == context:
                    dirs_to_clean.append((dir_id, info['path']))
        
        # 清理文件
        for file_id, file_path in files_to_clean:
            if safe_remove_file(file_path):
                cleaned_paths.append(file_path)
                self.unregister_file(file_id)
        
        # 清理目錄
        for dir_id, dir_path in dirs_to_clean:
            if safe_remove_directory(dir_path):
                cleaned_paths.append(dir_path)
                self.unregister_file(dir_id)
        
        return cleaned_paths
    
    def get_stats(self) -> Dict:
        """
        獲取追蹤器統計資訊
        
        Returns:
            Dict: 統計資訊
        """
        with self._lock:
            return {
                'total_files': len(self._tracked_files),
                'total_directories': len(self._tracked_dirs),
                'contexts': list(set([info['context'] for info in self._tracked_files.values()] + 
                                   [info['context'] for info in self._tracked_dirs.values()]))
            }

# 全局文件追蹤器實例
_global_tracker = FileTracker()

def safe_remove_file(file_path: str) -> bool:
    """
    安全刪除文件
    
    Args:
        file_path: 文件路徑
        
    Returns:
        bool: 是否成功刪除
    """
    try:
        if os.path.exists(file_path):
            if os.access(file_path, os.W_OK):
                os.remove(file_path)
                logger.debug(f"成功刪除文件: {file_path}")
                return True
            else:
                logger.warning(f"無權限刪除文件: {file_path}")
                return False
        else:
            logger.debug(f"文件不存在，跳過刪除: {file_path}")
            return True
    except PermissionError:
        logger.error(f"權限錯誤，無法刪除文件: {file_path}")
        return False
    except Exception as e:
        logger.error(f"刪除文件時發生錯誤 {file_path}: {str(e)}")
        return False

def safe_remove_directory(dir_path: str) -> bool:
    """
    安全刪除目錄
    
    Args:
        dir_path: 目錄路徑
        
    Returns:
        bool: 是否成功刪除
    """
    try:
        if os.path.exists(dir_path):
            if os.access(dir_path, os.W_OK):
                shutil.rmtree(dir_path)
                logger.debug(f"成功刪除目錄: {dir_path}")
                return True
            else:
                logger.warning(f"無權限刪除目錄: {dir_path}")
                return False
        else:
            logger.debug(f"目錄不存在，跳過刪除: {dir_path}")
            return True
    except PermissionError:
        logger.error(f"權限錯誤，無法刪除目錄: {dir_path}")
        return False
    except Exception as e:
        logger.error(f"刪除目錄時發生錯誤 {dir_path}: {str(e)}")
        return False

def create_temp_directory(prefix: str = "temp_", context: str = "default",
                         max_age_minutes: int = 60, base_dir: str = None) -> str:
    """
    創建臨時目錄並註冊追蹤
    
    Args:
        prefix: 目錄名稱前綴
        context: 上下文名稱
        max_age_minutes: 最大保留時間（分鐘）
        base_dir: 基礎目錄路徑，如果為 None 則使用系統默認
        
    Returns:
        str: 目錄路徑
    """
    temp_dir = tempfile.mkdtemp(prefix=prefix, dir=base_dir)
    _global_tracker.register_directory(temp_dir, context, max_age_minutes)
    logger.info(f"創建臨時目錄: {temp_dir}")
    return temp_dir

def register_temp_file(file_path: str, context: str = "default",
                      max_age_minutes: int = 60) -> str:
    """
    註冊臨時文件
    
    Args:
        file_path: 文件路徑
        context: 上下文名稱
        max_age_minutes: 最大保留時間（分鐘）
        
    Returns:
        str: 文件識別碼
    """
    return _global_tracker.register_file(file_path, context, max_age_minutes)

def cleanup_files_by_context(context: str) -> int:
    """
    按上下文清理文件
    
    Args:
        context: 上下文名稱
        
    Returns:
        int: 清理的文件數量
    """
    cleaned_paths = _global_tracker.cleanup_by_context(context)
    logger.info(f"按上下文 '{context}' 清理了 {len(cleaned_paths)} 個文件/目錄")
    return len(cleaned_paths)

def cleanup_expired_files() -> int:
    """
    清理已過期的文件
    
    Returns:
        int: 清理的文件數量
    """
    expired_files = _global_tracker.get_expired_files()
    cleaned_count = 0
    
    for file_info in expired_files:
        if file_info['type'] == 'file':
            if safe_remove_file(file_info['path']):
                _global_tracker.unregister_file(file_info['id'])
                cleaned_count += 1
        elif file_info['type'] == 'directory':
            if safe_remove_directory(file_info['path']):
                _global_tracker.unregister_file(file_info['id'])
                cleaned_count += 1
    
    if cleaned_count > 0:
        logger.info(f"清理了 {cleaned_count} 個過期文件/目錄")
    
    return cleaned_count

def get_cleanup_stats() -> Dict:
    """
    獲取清理統計資訊
    
    Returns:
        Dict: 統計資訊
    """
    stats = _global_tracker.get_stats()
    expired_count = len(_global_tracker.get_expired_files())
    stats['expired_count'] = expired_count
    return stats

# Flask 裝飾器
def cleanup_after_request(context: Optional[str] = None):
    """
    Flask 裝飾器：在請求完成後清理文件
    
    Args:
        context: 要清理的上下文，如果為 None 則使用 session ID
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import session, after_this_request
            
            # 確定清理上下文
            cleanup_context = context or session.get('session_id', 'unknown')
            
            # 註冊清理回調
            @after_this_request
            def cleanup(response):
                try:
                    cleanup_files_by_context(cleanup_context)
                except Exception as e:
                    logger.error(f"請求後清理失敗: {str(e)}")
                return response
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cleanup_on_error(context: Optional[str] = None):
    """
    錯誤時清理文件的裝飾器
    
    Args:
        context: 要清理的上下文
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cleanup_context = context
            if not cleanup_context:
                try:
                    from flask import session
                    cleanup_context = session.get('session_id', 'error_cleanup')
                except:
                    cleanup_context = 'error_cleanup'
            
            try:
                return f(*args, **kwargs)
            except Exception as e:
                # 發生錯誤時清理
                try:
                    cleanup_files_by_context(cleanup_context)
                    logger.info(f"錯誤時清理了上下文 '{cleanup_context}' 的文件")
                except Exception as cleanup_error:
                    logger.error(f"錯誤清理失敗: {str(cleanup_error)}")
                raise e
        return decorated_function
    return decorator 