import os
import logging
import time
from PyPDF2 import PdfReader
import zipfile
import random
import string
from datetime import datetime
import re

class BookmarkParseError(Exception):
    pass

def get_bookmarks_recursive(pdf_path):
    """
    遞迴解析 PDF 書籤，回傳結構化清單。
    :param pdf_path: PDF 檔案路徑
    :return: (bookmarks, status) tuple
    """
    logger = logging.getLogger("bookmark_parser")
    start_time = time.time()
    if not os.path.exists(pdf_path):
        logger.error(f"檔案不存在: {pdf_path}")
        return [], {'status': 'file_not_found'}
    try:
        reader = PdfReader(pdf_path)
        # PyPDF2 3.x: 用 outline 取代 outlines
        outlines = getattr(reader, 'outline', None) or getattr(reader, 'outlines', None)
        if not outlines:
            logger.info(f"PDF 無書籤: {pdf_path}")
            return [], {'status': 'no_bookmarks'}
        def parse_outline(outlines):
            bookmarks = []
            for item in outlines:
                if isinstance(item, list):
                    bookmarks.append(parse_outline(item))
                else:
                    try:
                        title = getattr(item, 'title', str(item))
                        page_num = reader.get_destination_page_number(item) + 1
                        bookmarks.append({'title': title, 'page': page_num})
                    except Exception as e:
                        logger.warning(f"書籤解析失敗: {e}")
                        bookmarks.append({'title': str(item), 'page': None, 'error': str(e)})
            return bookmarks
        bookmarks = parse_outline(outlines)
        elapsed = time.time() - start_time
        logger.info(f"書籤解析完成: {pdf_path}, 共 {len(bookmarks)} 筆, 花費 {elapsed:.2f}s")
        return bookmarks, {'status': 'ok', 'count': len(bookmarks), 'elapsed': elapsed}
    except Exception as e:
        logger.error(f"PDF 解析失敗: {e}")
        return [], {'status': 'error', 'error': str(e)}

def safe_filename(name):
    # 只保留中英文、數字、底線、破折號，其他轉為底線
    return re.sub(r'[^\w\u4e00-\u9fff-]+', '_', name)[:50]

def split_pdf(pdf_path: str, split_points: list[str], bookmarks: list[dict] = None, split_titles: list[str] = None) -> list[str]:
    import tempfile
    from PyPDF2 import PdfReader, PdfWriter
    logger = logging.getLogger("pdf_splitter")
    if not os.path.exists(pdf_path):
        logger.error(f"檔案不存在: {pdf_path}")
        raise FileNotFoundError(pdf_path)
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        # 直接用使用者勾選順序，不排序不去重
        points = [int(p) - 1 for p in split_points if str(p).isdigit() and 1 <= int(p) <= total_pages]
        if not points or points[0] != 0:
            points = [0] + points
            if split_titles:
                split_titles = ['開始'] + split_titles
        points.append(total_pages)
        out_dir = tempfile.mkdtemp()
        result_files = []
        for i in range(len(points) - 1):
            start, end = points[i], points[i + 1]
            writer = PdfWriter()
            for p in range(start, end):
                writer.add_page(reader.pages[p])
            if split_titles and i < len(split_titles):
                base = safe_filename(split_titles[i])
            else:
                base = f'split_{start+1}-{end}'
            out_path = os.path.join(out_dir, f'{base}_{start+1}-{end}.pdf')
            with open(out_path, 'wb') as f:
                writer.write(f)
            result_files.append(out_path)
        logger.info(f"PDF 分割完成: {pdf_path} -> {len(result_files)} 檔案")
        return result_files
    except Exception as e:
        logger.error(f"PDF 分割失敗: {e}")
        raise

def create_zip_from_pdfs(pdf_files: list[str], bookmark_titles: list[str] = None) -> str:
    """
    將多個 PDF 壓縮成一個 ZIP，回傳 ZIP 檔案路徑。
    :param pdf_files: PDF 檔案路徑清單
    :param bookmark_titles: 書籤標題清單，若有則用於壓縮包內檔名
    :return: ZIP 檔案路徑
    """
    import tempfile
    logger = logging.getLogger("zip_creator")
    try:
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        zip_name = f"split_{ts}_{rand}.zip"
        out_dir = tempfile.mkdtemp()
        zip_path = os.path.join(out_dir, zip_name)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for idx, f in enumerate(pdf_files):
                if os.path.exists(f):
                    if bookmark_titles and idx < len(bookmark_titles):
                        arcname = f"{safe_filename(bookmark_titles[idx])}.pdf"
                    else:
                        arcname = os.path.basename(f)
                    zf.write(f, arcname=arcname)
        logger.info(f"ZIP 建立完成: {zip_path}")
        return zip_path
    except Exception as e:
        logger.error(f"ZIP 建立失敗: {e}")
        raise 