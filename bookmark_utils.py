"""
PDF 書籤處理工具模組
包含書籤解析、過濾和分析功能
"""

import os
import re
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
import PyPDF2
from PyPDF2 import PdfReader
from PyPDF2.generic import Destination

# 配置日誌記錄
logger = logging.getLogger(__name__)

# 定義書籤過濾的正規表達式模式
NUMBERED_TITLE_PATTERN = r"^\d+\s+.+"  # 例如："1 Introduction"
HIERARCHICAL_TITLE_PATTERN = r"^\d+(\.\d+)+\s*.*"  # 例如："1.1 Overview", "2.3.4 Details"
CHAPTER_TITLE_PATTERN = r"^(Chapter|Part|Section)\s+\w+.*"  # 例如："Chapter 1", "Part A"

# 編譯正規表達式以提高效能
PATTERNS = {
    'numbered': re.compile(NUMBERED_TITLE_PATTERN, re.IGNORECASE),
    'hierarchical': re.compile(HIERARCHICAL_TITLE_PATTERN, re.IGNORECASE),
    'chapter': re.compile(CHAPTER_TITLE_PATTERN, re.IGNORECASE)
}

class BookmarkParsingError(Exception):
    """書籤解析錯誤"""
    pass

class PDFProcessingError(Exception):
    """PDF 處理錯誤"""
    pass

def validate_pdf_file(file_path: str) -> bool:
    """
    驗證 PDF 檔案是否存在且可讀取
    
    Args:
        file_path: PDF 檔案路徑
        
    Returns:
        bool: 檔案是否有效
        
    Raises:
        FileNotFoundError: 檔案不存在
        PermissionError: 無法讀取檔案
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF 檔案不存在: {file_path}")
    
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"無法讀取 PDF 檔案: {file_path}")
    
    # 檢查檔案大小
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        raise ValueError(f"PDF 檔案為空: {file_path}")
    
    logger.debug(f"PDF 檔案驗證成功: {file_path} (大小: {file_size} 位元組)")
    return True

def get_bookmarks_recursive(file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    遞迴解析 PDF 檔案中的書籤結構
    
    Args:
        file_path: PDF 檔案路徑
        
    Returns:
        Tuple[List[Dict], Dict]: (書籤列表, 解析統計資訊)
        
    Raises:
        BookmarkParsingError: 書籤解析失敗
        PDFProcessingError: PDF 處理失敗
    """
    start_time = time.time()
    
    try:
        # 驗證檔案
        validate_pdf_file(file_path)
        
        logger.info(f"開始解析 PDF 書籤: {file_path}")
        
        # 使用 PyPDF2 開啟 PDF
        with open(file_path, 'rb') as pdf_file:
            reader = PdfReader(pdf_file)
            
            # 獲取 PDF 基本資訊
            total_pages = len(reader.pages)
            logger.debug(f"PDF 總頁數: {total_pages}")
            
            # 檢查是否有書籤 - 添加錯誤處理
            try:
                outline = reader.outline
                has_outline = outline is not None and len(outline) > 0
            except (KeyError, AttributeError, IndexError, TypeError) as e:
                logger.warning(f"無法訪問 PDF 書籤結構: {str(e)}")
                logger.warning("此 PDF 可能有損壞的書籤或使用了不支援的書籤格式")
                return [], {
                    'total_bookmarks': 0,
                    'valid_bookmarks': 0,
                    'parsing_time': time.time() - start_time,
                    'total_pages': total_pages,
                    'has_bookmarks': False,
                    'error_count': 0,
                    'error_message': f'書籤結構損壞或不兼容: {str(e)}'
                }
            except Exception as e:
                logger.error(f"訪問書籤時發生未預期錯誤: {str(e)}")
                return [], {
                    'total_bookmarks': 0,
                    'valid_bookmarks': 0,
                    'parsing_time': time.time() - start_time,
                    'total_pages': total_pages,
                    'has_bookmarks': False,
                    'error_count': 1,
                    'error_message': f'書籤解析失敗: {str(e)}'
                }
            
            if not has_outline:
                logger.warning(f"PDF 檔案沒有書籤: {file_path}")
                return [], {
                    'total_bookmarks': 0,
                    'valid_bookmarks': 0,
                    'parsing_time': time.time() - start_time,
                    'total_pages': total_pages,
                    'has_bookmarks': False,
                    'error_count': 0
                }
            
            # 遞迴解析書籤
            bookmarks = []
            error_count = 0
            
            def parse_outline_item(item, level=0, parent_id=None):
                nonlocal error_count
                
                try:
                    if isinstance(item, Destination):
                        # 獲取書籤標題
                        title = str(item.title).strip()
                        
                        # 獲取頁碼 - 添加更強的錯誤處理
                        try:
                            page_num = reader.get_destination_page_number(item)
                            # PyPDF2 返回的是 0-based，轉換為 1-based
                            page_num += 1
                            
                            # 特殊處理：如果頁碼仍然是 0，可能是 PDF 的第一頁
                            if page_num == 0:
                                logger.warning(f"書籤 '{title}' 返回頁碼 0，設置為第 1 頁")
                                page_num = 1
                                
                        except (KeyError, IndexError, TypeError, AttributeError) as e:
                            logger.warning(f"無法獲取書籤 '{title}' 的頁碼 (兼容性問題): {str(e)}")
                            page_num = None
                            error_count += 1
                        except Exception as e:
                            logger.warning(f"無法獲取書籤 '{title}' 的頁碼: {str(e)}")
                            page_num = None
                            error_count += 1
                        
                        # 驗證頁碼有效性
                        if page_num is not None and (page_num < 1 or page_num > total_pages):
                            logger.warning(f"書籤 '{title}' 的頁碼 {page_num} 超出範圍 (1-{total_pages})")
                            page_num = None
                            error_count += 1
                        
                        # 創建書籤資料結構
                        bookmark = {
                            'id': len(bookmarks) + 1,
                            'title': title,
                            'page_num': page_num,
                            'level': level,
                            'parent_id': parent_id,
                            'valid': page_num is not None,
                            'matches_pattern': False  # 將在過濾階段設定
                        }
                        
                        bookmarks.append(bookmark)
                        logger.debug(f"解析書籤: Level {level}, '{title}' -> 頁面 {page_num}")
                        
                        return bookmark['id']
                    else:
                        logger.warning(f"未知的書籤項目類型: {type(item)}")
                        error_count += 1
                        return None
                        
                except Exception as e:
                    logger.error(f"解析書籤項目時發生錯誤: {str(e)}")
                    error_count += 1
                    return None
            
            def traverse_outline(outline, level=0, parent_id=None):
                """遞迴遍歷書籤結構 - 添加錯誤處理"""
                nonlocal error_count
                
                try:
                    for item in outline:
                        try:
                            if isinstance(item, list):
                                # 子書籤列表
                                traverse_outline(item, level + 1, parent_id)
                            else:
                                # 單個書籤
                                bookmark_id = parse_outline_item(item, level, parent_id)
                                
                                # 如果有子項目，繼續遍歷
                                if hasattr(item, 'outline') and item.outline:
                                    traverse_outline(item.outline, level + 1, bookmark_id)
                        except (KeyError, IndexError, TypeError, AttributeError) as e:
                            logger.warning(f"跳過損壞的書籤項目: {str(e)}")
                            error_count += 1
                            continue
                        except Exception as e:
                            logger.error(f"處理書籤項目時發生錯誤: {str(e)}")
                            error_count += 1
                            continue
                except Exception as e:
                    logger.error(f"遍歷書籤結構時發生錯誤: {str(e)}")
                    error_count += 1
            
            # 開始遍歷
            try:
                traverse_outline(outline)
            except Exception as e:
                logger.error(f"書籤遍歷過程中發生嚴重錯誤: {str(e)}")
                # 即使遍歷失敗，也嘗試返回已解析的書籤
            
            # 計算統計資訊
            valid_bookmarks = sum(1 for b in bookmarks if b['valid'])
            parsing_time = time.time() - start_time
            
            stats = {
                'total_bookmarks': len(bookmarks),
                'valid_bookmarks': valid_bookmarks,
                'parsing_time': parsing_time,
                'total_pages': total_pages,
                'has_bookmarks': len(bookmarks) > 0,
                'error_count': error_count
            }
            
            if error_count > 0:
                logger.warning(f"書籤解析完成但有 {error_count} 個錯誤")
            
            logger.info(f"書籤解析完成: 總計 {len(bookmarks)} 個書籤，有效 {valid_bookmarks} 個，耗時 {parsing_time:.2f} 秒")
            
            return bookmarks, stats
            
    except FileNotFoundError as e:
        logger.error(f"檔案不存在: {str(e)}")
        raise PDFProcessingError(f"檔案不存在: {str(e)}")
    
    except PermissionError as e:
        logger.error(f"權限錯誤: {str(e)}")
        raise PDFProcessingError(f"權限錯誤: {str(e)}")
        
    except PyPDF2.errors.PdfReadError as e:
        logger.error(f"PDF 讀取錯誤: {str(e)}")
        raise PDFProcessingError(f"PDF 檔案損壞或格式不正確: {str(e)}")
        
    except Exception as e:
        logger.error(f"書籤解析過程中發生未預期的錯誤: {str(e)}", exc_info=True)
        raise BookmarkParsingError(f"書籤解析失敗: {str(e)}")

def matches_any_pattern(title: str) -> Tuple[bool, Optional[str]]:
    """
    檢查書籤標題是否符合任何預定義模式
    
    Args:
        title: 書籤標題
        
    Returns:
        Tuple[bool, Optional[str]]: (是否匹配, 匹配的模式名稱)
    """
    if not title or not isinstance(title, str):
        return False, None
    
    title = title.strip()
    
    for pattern_name, pattern in PATTERNS.items():
        if pattern.match(title):
            logger.debug(f"書籤 '{title}' 匹配模式: {pattern_name}")
            return True, pattern_name
    
    return False, None

def filter_bookmarks(bookmarks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    根據預定義模式過濾書籤
    
    Args:
        bookmarks: 書籤列表
        
    Returns:
        Tuple[List[Dict], Dict]: (過濾後的書籤列表, 過濾統計資訊)
    """
    if not bookmarks:
        return bookmarks, {
            'total_processed': 0,
            'matched_bookmarks': 0,
            'pattern_counts': {'numbered': 0, 'hierarchical': 0, 'chapter': 0},
            'has_matches': False
        }
    
    logger.info(f"開始過濾 {len(bookmarks)} 個書籤")
    
    matched_count = 0
    pattern_counts = {'numbered': 0, 'hierarchical': 0, 'chapter': 0}
    
    # 為每個書籤檢查模式匹配
    for bookmark in bookmarks:
        if not bookmark.get('valid', False):
            continue
            
        title = bookmark.get('title', '')
        matches, pattern_name = matches_any_pattern(title)
        
        bookmark['matches_pattern'] = matches
        bookmark['matched_pattern'] = pattern_name if matches else None
        
        if matches:
            matched_count += 1
            if pattern_name in pattern_counts:
                pattern_counts[pattern_name] += 1
    
    # 建立過濾統計資訊
    filter_stats = {
        'total_processed': len(bookmarks),
        'matched_bookmarks': matched_count,
        'pattern_counts': pattern_counts,
        'has_matches': matched_count > 0,
        'match_percentage': (matched_count / len(bookmarks)) * 100 if bookmarks else 0
    }
    
    logger.info(f"書籤過濾完成: {matched_count}/{len(bookmarks)} 個書籤匹配模式 ({filter_stats['match_percentage']:.1f}%)")
    
    return bookmarks, filter_stats

def get_filtered_bookmarks_only(bookmarks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    獲取只包含匹配模式的書籤列表
    
    Args:
        bookmarks: 完整書籤列表
        
    Returns:
        List[Dict]: 只包含匹配模式的書籤
    """
    return [b for b in bookmarks if b.get('matches_pattern', False)]

def analyze_bookmark_structure(bookmarks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析書籤結構特徵
    
    Args:
        bookmarks: 書籤列表
        
    Returns:
        Dict: 結構分析結果
    """
    if not bookmarks:
        return {
            'max_level': 0,
            'level_distribution': {},
            'average_title_length': 0,
            'has_hierarchy': False
        }
    
    levels = [b.get('level', 0) for b in bookmarks]
    titles = [b.get('title', '') for b in bookmarks if b.get('title')]
    
    level_distribution = {}
    for level in levels:
        level_distribution[level] = level_distribution.get(level, 0) + 1
    
    analysis = {
        'max_level': max(levels) if levels else 0,
        'level_distribution': level_distribution,
        'average_title_length': sum(len(t) for t in titles) / len(titles) if titles else 0,
        'has_hierarchy': max(levels) > 0 if levels else False,
        'total_bookmarks': len(bookmarks),
        'title_length_range': (min(len(t) for t in titles), max(len(t) for t in titles)) if titles else (0, 0)
    }
    
    return analysis

def process_pdf_bookmarks(file_path: str) -> Dict[str, Any]:
    """
    完整處理 PDF 書籤：解析 + 過濾 + 分析
    
    Args:
        file_path: PDF 檔案路徑
        
    Returns:
        Dict: 完整的處理結果
    """
    try:
        # 解析書籤
        bookmarks, parse_stats = get_bookmarks_recursive(file_path)
        
        # 檢查是否因錯誤而沒有書籤
        if not bookmarks and parse_stats.get('error_count', 0) > 0:
            error_msg = parse_stats.get('error_message', '未知錯誤')
            logger.warning(f"書籤解析失敗: {error_msg}")
            
            # 即使解析失敗，也返回有用的信息
            return {
                'success': True,  # 技術上成功，但沒有可用書籤
                'bookmarks': [],
                'matched_bookmarks': [],
                'parse_stats': parse_stats,
                'filter_stats': {
                    'total_processed': 0,
                    'matched_bookmarks': 0,
                    'pattern_counts': {'numbered': 0, 'hierarchical': 0, 'chapter': 0},
                    'has_matches': False,
                    'match_percentage': 0
                },
                'structure_analysis': {
                    'max_level': 0,
                    'level_distribution': {},
                    'average_title_length': 0,
                    'has_hierarchy': False,
                    'total_bookmarks': 0,
                    'title_length_range': (0, 0)
                },
                'recommendations': [
                    f"此 PDF 的書籤結構有問題：{error_msg}",
                    "建議使用其他 PDF 分割方法（如按頁數分割）",
                    "或嘗試使用其他 PDF 工具修復書籤結構"
                ]
            }
        
        # 過濾書籤
        filtered_bookmarks, filter_stats = filter_bookmarks(bookmarks)
        
        # 分析結構
        structure_analysis = analyze_bookmark_structure(bookmarks)
        
        # 獲取匹配的書籤
        matched_bookmarks = get_filtered_bookmarks_only(filtered_bookmarks)
        
        # 生成建議，如果有錯誤則添加警告
        recommendations = generate_split_recommendations(matched_bookmarks, structure_analysis)
        
        if parse_stats.get('error_count', 0) > 0:
            recommendations.insert(0, f"注意：解析過程中遇到 {parse_stats['error_count']} 個錯誤，部分書籤可能丟失")
        
        # 組合結果
        result = {
            'success': True,
            'bookmarks': filtered_bookmarks,
            'matched_bookmarks': matched_bookmarks,
            'parse_stats': parse_stats,
            'filter_stats': filter_stats,
            'structure_analysis': structure_analysis,
            'recommendations': recommendations
        }
        
        return result
        
    except Exception as e:
        logger.error(f"處理 PDF 書籤時發生錯誤: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'bookmarks': [],
            'matched_bookmarks': [],
            'parse_stats': {'error': True, 'error_message': str(e)},
            'filter_stats': {'error': True},
            'structure_analysis': {'error': True},
            'recommendations': [
                f"處理失敗：{str(e)}",
                "建議檢查 PDF 文件是否損壞",
                "或嘗試使用其他 PDF 處理工具"
            ]
        }

def generate_split_recommendations(matched_bookmarks: List[Dict[str, Any]], structure_analysis: Dict[str, Any]) -> List[str]:
    """
    根據匹配的書籤生成分割建議
    
    Args:
        matched_bookmarks: 匹配模式的書籤列表
        structure_analysis: 結構分析結果
        
    Returns:
        List[str]: 建議列表
    """
    recommendations = []
    
    if not matched_bookmarks:
        recommendations.append("沒有找到符合常見模式的書籤，建議手動選擇分割點")
        return recommendations
    
    count = len(matched_bookmarks)
    
    if count == 1:
        recommendations.append("只找到一個匹配的書籤，可能需要尋找其他分割標準")
    elif count <= 5:
        recommendations.append(f"找到 {count} 個良好的分割點，適合進行分割")
    elif count <= 15:
        recommendations.append(f"找到 {count} 個分割點，建議檢查是否需要全部使用")
    else:
        recommendations.append(f"找到 {count} 個分割點，數量較多，建議選擇主要章節進行分割")
    
    # 結構建議
    if structure_analysis.get('has_hierarchy'):
        recommendations.append("檢測到階層式結構，可以選擇不同層級的書籤進行分割")
    
    return recommendations 