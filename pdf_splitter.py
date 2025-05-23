"""
PDF 分割工具模組
實現 PDF 檔案的分割功能
"""

import os
import time
import tempfile
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import PyPDF2
from PyPDF2 import PdfReader, PdfWriter

# 配置日誌記錄
logger = logging.getLogger(__name__)

class PDFSplittingError(Exception):
    """PDF 分割錯誤"""
    pass

class InvalidSplitPointError(Exception):
    """無效分割點錯誤"""
    pass

def validate_pdf_for_splitting(pdf_path: str) -> Dict[str, Any]:
    """
    驗證 PDF 檔案是否適合分割
    
    Args:
        pdf_path: PDF 檔案路徑
        
    Returns:
        Dict: 包含驗證結果和 PDF 資訊
        
    Raises:
        FileNotFoundError: 檔案不存在
        PermissionError: 無法讀取檔案
        PyPDF2.errors.PdfReadError: PDF 讀取錯誤
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF 檔案不存在: {pdf_path}")
    
    if not os.access(pdf_path, os.R_OK):
        raise PermissionError(f"無法讀取 PDF 檔案: {pdf_path}")
    
    try:
        with open(pdf_path, 'rb') as pdf_file:
            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            if total_pages == 0:
                raise ValueError(f"PDF 檔案沒有頁面: {pdf_path}")
            
            # 檢查是否可以讀取頁面
            try:
                first_page = reader.pages[0]
                logger.debug(f"PDF 檔案驗證成功: {total_pages} 頁")
            except Exception as e:
                raise PyPDF2.errors.PdfReadError(f"無法讀取 PDF 頁面: {str(e)}")
            
            return {
                'valid': True,
                'total_pages': total_pages,
                'file_size': os.path.getsize(pdf_path),
                'can_extract': True
            }
            
    except PyPDF2.errors.PdfReadError as e:
        logger.error(f"PDF 讀取錯誤: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"PDF 驗證時發生未預期錯誤: {str(e)}")
        raise PDFSplittingError(f"PDF 驗證失敗: {str(e)}")

def validate_split_points(split_points: List[int], total_pages: int) -> List[int]:
    """
    驗證和正規化分割點
    
    Args:
        split_points: 分割點列表（頁碼，1-based）
        total_pages: PDF 總頁數
        
    Returns:
        List[int]: 正規化後的分割點列表
        
    Raises:
        InvalidSplitPointError: 無效的分割點
    """
    if not split_points:
        raise InvalidSplitPointError("分割點列表不能為空")
    
    # 移除重複並排序
    unique_points = sorted(set(split_points))
    
    # 驗證分割點範圍
    for point in unique_points:
        if not isinstance(point, int):
            raise InvalidSplitPointError(f"分割點必須是整數: {point}")
        if point < 1 or point > total_pages:
            raise InvalidSplitPointError(f"分割點 {point} 超出頁面範圍 (1-{total_pages})")
    
    # 確保第一頁總是在分割點中（如果不存在則添加）
    if 1 not in unique_points:
        unique_points.insert(0, 1)
        logger.debug("自動添加第一頁作為分割點")
    
    logger.debug(f"正規化後的分割點: {unique_points}")
    return unique_points

def generate_split_filename(base_name: str, start_page: int, end_page: int, index: int) -> str:
    """
    生成分割檔案名稱
    
    Args:
        base_name: 原始檔案的基本名稱（無副檔名）
        start_page: 起始頁面
        end_page: 結束頁面
        index: 分割檔案索引
        
    Returns:
        str: 生成的檔案名稱
    """
    # 清理檔案名稱，移除可能有問題的字元
    safe_base_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_base_name:
        safe_base_name = "pdf_split"
    
    if start_page == end_page:
        filename = f"{safe_base_name}_part_{index:02d}_page_{start_page}.pdf"
    else:
        filename = f"{safe_base_name}_part_{index:02d}_pages_{start_page}-{end_page}.pdf"
    
    return filename

def split_pdf(pdf_path: str, split_points: List[int], output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    分割 PDF 檔案到指定的分割點
    
    Args:
        pdf_path: 原始 PDF 檔案路徑
        split_points: 分割點列表（頁碼，1-based）
        output_dir: 輸出目錄，如果為 None 則創建臨時目錄
        
    Returns:
        Dict: 包含分割結果的字典
            - success: bool，是否成功
            - split_files: List[Dict]，分割檔案資訊列表
            - output_directory: str，輸出目錄路徑
            - total_parts: int，總分割數量
            - processing_time: float，處理時間
            - original_info: Dict，原始檔案資訊
            
    Raises:
        PDFSplittingError: 分割過程中的錯誤
        InvalidSplitPointError: 無效的分割點
    """
    start_time = time.time()
    
    try:
        logger.info(f"開始分割 PDF: {pdf_path}")
        
        # 驗證 PDF 檔案
        pdf_info = validate_pdf_for_splitting(pdf_path)
        total_pages = pdf_info['total_pages']
        
        # 驗證分割點
        validated_split_points = validate_split_points(split_points, total_pages)
        
        # 創建輸出目錄
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='pdf_split_')
            logger.debug(f"創建臨時目錄: {output_dir}")
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        # 獲取原始檔案名稱（無副檔名）
        base_name = Path(pdf_path).stem
        
        # 開啟原始 PDF
        with open(pdf_path, 'rb') as pdf_file:
            reader = PdfReader(pdf_file)
            
            split_files = []
            
            # 為每個分割段創建 PDF
            for i, start_page in enumerate(validated_split_points):
                # 確定結束頁面
                if i + 1 < len(validated_split_points):
                    end_page = validated_split_points[i + 1] - 1
                else:
                    end_page = total_pages
                
                # 跳過空範圍
                if start_page > end_page:
                    continue
                
                # 創建新的 PDF 寫入器
                writer = PdfWriter()
                
                # 添加指定範圍的頁面
                pages_added = 0
                for page_num in range(start_page - 1, end_page):  # 轉換為 0-based
                    try:
                        page = reader.pages[page_num]
                        writer.add_page(page)
                        pages_added += 1
                    except Exception as e:
                        logger.warning(f"無法添加頁面 {page_num + 1}: {str(e)}")
                        continue
                
                if pages_added == 0:
                    logger.warning(f"分割段 {i + 1} 沒有成功添加任何頁面")
                    continue
                
                # 生成輸出檔案名稱
                output_filename = generate_split_filename(base_name, start_page, end_page, i + 1)
                output_path = os.path.join(output_dir, output_filename)
                
                # 寫入檔案
                try:
                    with open(output_path, 'wb') as output_file:
                        writer.write(output_file)
                    
                    # 獲取輸出檔案資訊
                    output_size = os.path.getsize(output_path)
                    
                    split_info = {
                        'index': i + 1,
                        'filename': output_filename,
                        'filepath': output_path,
                        'start_page': start_page,
                        'end_page': end_page,
                        'page_count': pages_added,
                        'file_size': output_size,
                        'size_mb': round(output_size / 1024 / 1024, 2)
                    }
                    
                    split_files.append(split_info)
                    logger.debug(f"創建分割檔案: {output_filename} ({pages_added} 頁)")
                    
                except Exception as e:
                    logger.error(f"寫入分割檔案時發生錯誤: {str(e)}")
                    raise PDFSplittingError(f"無法寫入分割檔案 {output_filename}: {str(e)}")
        
        processing_time = time.time() - start_time
        
        result = {
            'success': True,
            'split_files': split_files,
            'output_directory': output_dir,
            'total_parts': len(split_files),
            'processing_time': processing_time,
            'original_info': {
                'filename': os.path.basename(pdf_path),
                'total_pages': total_pages,
                'file_size': pdf_info['file_size'],
                'size_mb': round(pdf_info['file_size'] / 1024 / 1024, 2)
            },
            'split_summary': {
                'split_points': validated_split_points,
                'total_output_size': sum(f['file_size'] for f in split_files),
                'average_pages_per_part': round(sum(f['page_count'] for f in split_files) / len(split_files), 1) if split_files else 0
            }
        }
        
        logger.info(f"PDF 分割完成: 創建了 {len(split_files)} 個檔案，耗時 {processing_time:.2f} 秒")
        return result
        
    except (InvalidSplitPointError, FileNotFoundError, PermissionError):
        # 重新拋出已知錯誤
        raise
        
    except PyPDF2.errors.PdfReadError as e:
        logger.error(f"PDF 讀取錯誤: {str(e)}")
        raise PDFSplittingError(f"PDF 檔案損壞或格式不正確: {str(e)}")
        
    except Exception as e:
        logger.error(f"PDF 分割過程中發生未預期錯誤: {str(e)}", exc_info=True)
        raise PDFSplittingError(f"PDF 分割失敗: {str(e)}")

def get_split_preview(pdf_path: str, split_points: List[int]) -> Dict[str, Any]:
    """
    預覽分割結果而不實際分割檔案
    
    Args:
        pdf_path: PDF 檔案路徑
        split_points: 分割點列表
        
    Returns:
        Dict: 預覽資訊
    """
    try:
        # 驗證 PDF 檔案
        pdf_info = validate_pdf_for_splitting(pdf_path)
        total_pages = pdf_info['total_pages']
        
        # 驗證分割點
        validated_split_points = validate_split_points(split_points, total_pages)
        
        # 計算每個分割段的資訊
        preview_parts = []
        base_name = Path(pdf_path).stem
        
        for i, start_page in enumerate(validated_split_points):
            # 確定結束頁面
            if i + 1 < len(validated_split_points):
                end_page = validated_split_points[i + 1] - 1
            else:
                end_page = total_pages
            
            if start_page <= end_page:
                filename = generate_split_filename(base_name, start_page, end_page, i + 1)
                page_count = end_page - start_page + 1
                
                preview_parts.append({
                    'index': i + 1,
                    'filename': filename,
                    'start_page': start_page,
                    'end_page': end_page,
                    'page_count': page_count
                })
        
        return {
            'success': True,
            'total_parts': len(preview_parts),
            'parts': preview_parts,
            'original_pages': total_pages,
            'split_points': validated_split_points
        }
        
    except Exception as e:
        logger.error(f"預覽分割時發生錯誤: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'total_parts': 0,
            'parts': []
        } 