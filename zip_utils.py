"""
ZIP 壓縮工具模組
實現 PDF 檔案的 ZIP 壓縮功能
"""

import os
import time
import zipfile
import tempfile
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# 配置日誌記錄
logger = logging.getLogger(__name__)

class ZipCreationError(Exception):
    """ZIP 創建錯誤"""
    pass

def create_zip_from_files(file_paths: List[str], zip_filename: Optional[str] = None, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    從文件列表創建 ZIP 檔案
    
    Args:
        file_paths: 要壓縮的檔案路徑列表
        zip_filename: ZIP 檔案名稱，如果為 None 則自動生成
        output_dir: 輸出目錄，如果為 None 則使用臨時目錄
        
    Returns:
        Dict: 包含 ZIP 創建結果的字典
            - success: bool，是否成功
            - zip_path: str，ZIP 檔案路徑
            - zip_filename: str，ZIP 檔案名稱
            - total_files: int，壓縮的檔案數量
            - zip_size: int，ZIP 檔案大小（位元組）
            - compression_ratio: float，壓縮比率
            - processing_time: float，處理時間
            
    Raises:
        ZipCreationError: ZIP 創建過程中的錯誤
    """
    start_time = time.time()
    
    try:
        logger.info(f"開始創建 ZIP 檔案，包含 {len(file_paths)} 個檔案")
        
        # 驗證輸入檔案
        valid_files = []
        total_original_size = 0
        
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.warning(f"檔案不存在，跳過: {file_path}")
                continue
            
            if not os.access(file_path, os.R_OK):
                logger.warning(f"無法讀取檔案，跳過: {file_path}")
                continue
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.warning(f"檔案大小為零，跳過: {file_path}")
                continue
            
            valid_files.append(file_path)
            total_original_size += file_size
        
        if not valid_files:
            raise ZipCreationError("沒有有效的檔案可以壓縮")
        
        # 創建輸出目錄
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='zip_output_')
            logger.debug(f"創建臨時目錄: {output_dir}")
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        # 生成 ZIP 檔案名稱
        if zip_filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            zip_filename = f"pdf_split_{timestamp}.zip"
        
        # 確保檔案名稱有 .zip 副檔名
        if not zip_filename.lower().endswith('.zip'):
            zip_filename += '.zip'
        
        zip_path = os.path.join(output_dir, zip_filename)
        
        # 創建 ZIP 檔案
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            files_added = 0
            
            for file_path in valid_files:
                try:
                    # 獲取檔案名稱（僅文件名，不包含路徑）
                    filename = os.path.basename(file_path)
                    
                    # 確保 ZIP 內部的檔案名稱是唯一的
                    unique_filename = filename
                    counter = 1
                    while unique_filename in [info.filename for info in zipf.infolist()]:
                        name, ext = os.path.splitext(filename)
                        unique_filename = f"{name}_{counter}{ext}"
                        counter += 1
                    
                    # 添加檔案到 ZIP
                    zipf.write(file_path, unique_filename)
                    files_added += 1
                    logger.debug(f"添加檔案到 ZIP: {unique_filename}")
                    
                except Exception as e:
                    logger.warning(f"無法添加檔案 {file_path} 到 ZIP: {str(e)}")
                    continue
        
        if files_added == 0:
            raise ZipCreationError("沒有檔案成功添加到 ZIP")
        
        # 獲取 ZIP 檔案資訊
        zip_size = os.path.getsize(zip_path)
        compression_ratio = 1 - (zip_size / total_original_size) if total_original_size > 0 else 0
        processing_time = time.time() - start_time
        
        result = {
            'success': True,
            'zip_path': zip_path,
            'zip_filename': zip_filename,
            'total_files': files_added,
            'zip_size': zip_size,
            'zip_size_mb': round(zip_size / 1024 / 1024, 2),
            'original_total_size': total_original_size,
            'original_size_mb': round(total_original_size / 1024 / 1024, 2),
            'compression_ratio': round(compression_ratio * 100, 1),
            'processing_time': processing_time,
            'output_directory': output_dir
        }
        
        logger.info(f"ZIP 創建成功: {zip_filename}, {files_added} 個檔案, "
                   f"壓縮率 {result['compression_ratio']}%, 耗時 {processing_time:.2f} 秒")
        
        return result
        
    except ZipCreationError:
        # 重新拋出已知錯誤
        raise
        
    except Exception as e:
        logger.error(f"創建 ZIP 檔案時發生未預期錯誤: {str(e)}", exc_info=True)
        raise ZipCreationError(f"ZIP 創建失敗: {str(e)}")

def create_zip_from_pdf_split_result(split_result: Dict[str, Any], custom_filename: Optional[str] = None) -> Dict[str, Any]:
    """
    從 PDF 分割結果創建 ZIP 檔案
    
    Args:
        split_result: PDF 分割結果字典
        custom_filename: 自定義 ZIP 檔案名稱
        
    Returns:
        Dict: ZIP 創建結果
    """
    try:
        if not split_result.get('success', False):
            raise ZipCreationError("PDF 分割結果無效")
        
        split_files = split_result.get('split_files', [])
        if not split_files:
            raise ZipCreationError("沒有分割檔案可以壓縮")
        
        # 提取檔案路徑
        file_paths = [file_info['filepath'] for file_info in split_files]
        
        # 生成有意義的 ZIP 檔案名稱
        if custom_filename is None:
            original_filename = split_result.get('original_info', {}).get('filename', 'pdf_split')
            base_name = Path(original_filename).stem
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            custom_filename = f"{base_name}_split_{timestamp}.zip"
        
        # 使用分割結果的輸出目錄
        output_dir = split_result.get('output_directory')
        
        return create_zip_from_files(file_paths, custom_filename, output_dir)
        
    except Exception as e:
        logger.error(f"從 PDF 分割結果創建 ZIP 時發生錯誤: {str(e)}")
        raise ZipCreationError(f"無法從分割結果創建 ZIP: {str(e)}")

def validate_zip_file(zip_path: str) -> Dict[str, Any]:
    """
    驗證 ZIP 檔案的完整性
    
    Args:
        zip_path: ZIP 檔案路徑
        
    Returns:
        Dict: 驗證結果
    """
    try:
        if not os.path.exists(zip_path):
            return {
                'valid': False,
                'error': 'ZIP 檔案不存在'
            }
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # 測試 ZIP 檔案的完整性
            bad_file = zipf.testzip()
            
            if bad_file:
                return {
                    'valid': False,
                    'error': f'ZIP 檔案損壞，有問題的檔案: {bad_file}'
                }
            
            # 獲取 ZIP 檔案資訊
            file_count = len(zipf.infolist())
            total_size = sum(info.file_size for info in zipf.infolist())
            compressed_size = sum(info.compress_size for info in zipf.infolist())
            
            return {
                'valid': True,
                'file_count': file_count,
                'total_uncompressed_size': total_size,
                'compressed_size': compressed_size,
                'compression_ratio': round((1 - compressed_size / total_size) * 100, 1) if total_size > 0 else 0,
                'files': [info.filename for info in zipf.infolist()]
            }
            
    except zipfile.BadZipFile:
        return {
            'valid': False,
            'error': 'ZIP 檔案格式無效'
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f'驗證 ZIP 檔案時發生錯誤: {str(e)}'
        }

def get_zip_info(zip_path: str) -> Dict[str, Any]:
    """
    獲取 ZIP 檔案的詳細資訊
    
    Args:
        zip_path: ZIP 檔案路徑
        
    Returns:
        Dict: ZIP 檔案資訊
    """
    try:
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"ZIP 檔案不存在: {zip_path}")
        
        file_stats = os.stat(zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            files_info = []
            total_uncompressed = 0
            total_compressed = 0
            
            for info in zipf.infolist():
                files_info.append({
                    'filename': info.filename,
                    'file_size': info.file_size,
                    'compress_size': info.compress_size,
                    'compression_ratio': round((1 - info.compress_size / info.file_size) * 100, 1) if info.file_size > 0 else 0,
                    'date_time': info.date_time
                })
                total_uncompressed += info.file_size
                total_compressed += info.compress_size
            
            return {
                'zip_filename': os.path.basename(zip_path),
                'zip_path': zip_path,
                'zip_size': file_stats.st_size,
                'zip_size_mb': round(file_stats.st_size / 1024 / 1024, 2),
                'file_count': len(files_info),
                'total_uncompressed_size': total_uncompressed,
                'total_compressed_size': total_compressed,
                'overall_compression_ratio': round((1 - total_compressed / total_uncompressed) * 100, 1) if total_uncompressed > 0 else 0,
                'created_time': file_stats.st_ctime,
                'modified_time': file_stats.st_mtime,
                'files': files_info
            }
            
    except Exception as e:
        logger.error(f"獲取 ZIP 檔案資訊時發生錯誤: {str(e)}")
        raise ZipCreationError(f"無法獲取 ZIP 檔案資訊: {str(e)}") 