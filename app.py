import os
import tempfile
import logging
import atexit
import shutil
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from logging.handlers import RotatingFileHandler

# 導入書籤處理模組
from bookmark_utils import process_pdf_bookmarks, BookmarkParsingError, PDFProcessingError

# 導入 PDF 分割模組
from pdf_splitter import split_pdf, get_split_preview, PDFSplittingError, InvalidSplitPointError

# 導入 ZIP 處理模組
from zip_utils import create_zip_from_pdf_split_result, ZipCreationError

# 導入文件清理模組
from file_cleanup import (
    create_temp_directory, register_temp_file, cleanup_files_by_context,
    cleanup_expired_files, cleanup_after_request, cleanup_on_error,
    get_cleanup_stats
)

app = Flask(__name__)

# 設定密鑰用於 session 和 flash 訊息
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# **Render 雲端環境配置**
# 使用 /tmp 目錄作為臨時文件存儲（Render 唯一可寫的目錄）
TEMP_BASE_DIR = '/tmp' if os.path.exists('/tmp') else tempfile.gettempdir()
UPLOAD_FOLDER = create_temp_directory(prefix='pdf_upload_', context='app_global', max_age_minutes=120, base_dir=TEMP_BASE_DIR)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB 最大上傳檔案大小
ALLOWED_EXTENSIONS = {'pdf'}

# **環境檢測**
IS_PRODUCTION = os.environ.get('RENDER') is not None
PORT = int(os.environ.get('PORT', 5000))

def allowed_file(filename):
    """檢查檔案是否為允許的類型（PDF）"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_session_id():
    """獲取或生成會話 ID"""
    if 'session_id' not in session:
        import uuid
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

def cleanup_temp_files():
    """清理舊版本的臨時檔案（兼容性）"""
    try:
        # 新版本使用清理統計來清理過期文件
        cleaned_count = cleanup_expired_files()
        if cleaned_count > 0:
            app.logger.info(f'自動清理了 {cleaned_count} 個過期文件')
    except Exception as e:
        app.logger.error(f'清理過期檔案時發生錯誤: {str(e)}')

def cleanup_session_files():
    """清理 session 中記錄的臨時檔案"""
    try:
        session_id = session.get('session_id')
        if session_id:
            # 使用新的清理機制按會話清理
            cleaned_count = cleanup_files_by_context(session_id)
            if cleaned_count > 0:
                app.logger.info(f'清理了會話 {session_id} 的 {cleaned_count} 個文件')
        
        # 清理 session 資料
        session.pop('uploaded_file', None)
        session.pop('bookmark_data', None)  # 舊字段
        session.pop('bookmark_data_compressed', None)  # 舊字段
        session.pop('split_result', None)  # 舊字段
        session.pop('zip_result', None)    # 舊字段
        session.pop('selected_bookmarks', None)  # 舊字段
        # 清理新的 session 字段
        session.pop('bookmark_file_path', None)  # 新字段
        session.pop('bookmark_summary', None)   # 新字段
        session.pop('split_summary', None)
        session.pop('zip_info', None)
        session.pop('selected_split_points', None)
        session.pop('split_result_path', None)
    except Exception as e:
        app.logger.error(f'清理 session 檔案時發生錯誤: {str(e)}')

# 註冊應用程式結束時的清理函數
atexit.register(cleanup_temp_files)

@app.route('/')
def index():
    # 清理任何現有的 session 資料，開始新的上傳流程
    cleanup_session_files()
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
@cleanup_on_error()
def upload_file():
    """處理 PDF 檔案上傳"""
    try:
        # 獲取或創建會話 ID
        session_id = get_session_id()
        
        # 檢查請求中是否包含檔案部分
        if 'file' not in request.files:
            flash('沒有選擇檔案', 'error')
            app.logger.warning('上傳請求中沒有檔案部分')
            return redirect(url_for('index'))
        
        file = request.files['file']
        
        # 如果使用者沒有選擇檔案，瀏覽器也會提交一個空的檔案名稱
        if file.filename == '':
            flash('沒有選擇檔案', 'error')
            app.logger.warning('上傳的檔案名稱為空')
            return redirect(url_for('index'))
        
        # 檢查檔案類型是否正確
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # 註冊文件到清理系統
                file_id = register_temp_file(filepath, context=session_id, max_age_minutes=60)
                
                # 獲取文件資訊
                file_size = os.path.getsize(filepath)
                upload_time = datetime.now()
                
                # 將文件資訊儲存到 session 中
                session['uploaded_file'] = {
                    'original_filename': file.filename,
                    'secure_filename': filename,
                    'filepath': filepath,
                    'file_id': file_id,  # 添加文件 ID 用於清理
                    'file_size': file_size,
                    'upload_time': upload_time.isoformat(),
                    'mime_type': 'application/pdf'
                }
                
                # 記錄成功上傳
                app.logger.info(f'檔案上傳成功並儲存到 session: {filename}, 大小: {file_size} 位元組')
                
                # 重定向到上傳成功頁面
                return redirect(url_for('upload_success'))
                
            except Exception as e:
                app.logger.error(f'儲存檔案時發生錯誤: {str(e)}')
                flash('儲存檔案時發生錯誤，請重試', 'error')
                return redirect(url_for('index'))
        else:
            flash('只允許上傳 PDF 檔案', 'error')
            app.logger.warning(f'嘗試上傳非 PDF 檔案: {file.filename}')
            return redirect(url_for('index'))
            
    except Exception as e:
        app.logger.error(f'處理檔案上傳時發生未預期的錯誤: {str(e)}')
        flash('處理檔案時發生錯誤，請重試', 'error')
        return redirect(url_for('index'))

@app.route('/upload-success')
def upload_success():
    """顯示上傳成功頁面"""
    # 檢查 session 中是否有上傳的檔案資訊
    if 'uploaded_file' not in session:
        flash('沒有找到上傳的檔案資訊，請重新上傳', 'error')
        return redirect(url_for('index'))
    
    file_info = session['uploaded_file']
    
    # 驗證檔案是否仍然存在
    if not os.path.exists(file_info['filepath']):
        flash('上傳的檔案已遺失，請重新上傳', 'error')
        cleanup_session_files()
        return redirect(url_for('index'))
    
    return render_template('upload_success.html', file_info=file_info)

@app.route('/analyze-bookmarks')
def analyze_bookmarks():
    """分析 PDF 書籤並重定向到選擇頁面"""
    # 檢查 session 中是否有上傳的檔案資訊
    if 'uploaded_file' not in session:
        flash('沒有找到上傳的檔案資訊，請重新上傳', 'error')
        return redirect(url_for('index'))
    
    file_info = session['uploaded_file']
    filepath = file_info['filepath']
    
    # 驗證檔案是否仍然存在
    if not os.path.exists(filepath):
        flash('上傳的檔案已遺失，請重新上傳', 'error')
        cleanup_session_files()
        return redirect(url_for('index'))
    
    try:
        app.logger.info(f'開始分析 PDF 書籤: {file_info["original_filename"]}')
        
        # 處理書籤
        bookmark_result = process_pdf_bookmarks(filepath)
        
        if not bookmark_result['success']:
            flash(f'書籤解析失敗: {bookmark_result["error"]}', 'error')
            return redirect(url_for('upload_success'))
        
        # **新方案**：將書籤數據保存到臨時文件，而不是 session
        session_id = get_session_id()
        
        # 創建書籤數據臨時目錄
        bookmark_temp_dir = create_temp_directory(prefix='bookmarks_', context=f"{session_id}_bookmarks", max_age_minutes=60, base_dir=TEMP_BASE_DIR)
        
        # 保存完整書籤數據到 JSON 文件
        bookmark_data_path = os.path.join(bookmark_temp_dir, 'bookmark_data.json')
        with open(bookmark_data_path, 'w', encoding='utf-8') as f:
            json.dump(bookmark_result, f, ensure_ascii=False, indent=2)
        
        # 註冊文件到清理系統
        register_temp_file(bookmark_data_path, context=f"{session_id}_bookmarks", max_age_minutes=60)
        
        # **在 session 中只存儲文件路徑和基本統計**
        session['bookmark_file_path'] = bookmark_data_path
        session['bookmark_summary'] = {
            'total_bookmarks': len(bookmark_result.get('bookmarks', [])),
            'matched_bookmarks': len(bookmark_result.get('matched_bookmarks', [])),
            'has_bookmarks': len(bookmark_result.get('bookmarks', [])) > 0,
            'timestamp': datetime.now().isoformat()
        }
        
        app.logger.info(f'書籤數據已保存到臨時文件: 找到 {len(bookmark_result["bookmarks"])} 個書籤，'
                       f'其中 {len(bookmark_result["matched_bookmarks"])} 個匹配模式')
        
        # 重定向到書籤選擇頁面
        return redirect(url_for('select_bookmarks'))
        
    except (BookmarkParsingError, PDFProcessingError) as e:
        app.logger.error(f'書籤處理錯誤: {str(e)}')
        flash(f'處理 PDF 書籤時發生錯誤: {str(e)}', 'error')
        return redirect(url_for('upload_success'))
    
    except Exception as e:
        app.logger.error(f'分析書籤時發生未預期的錯誤: {str(e)}', exc_info=True)
        flash('分析書籤時發生未預期的錯誤，請重試', 'error')
        return redirect(url_for('upload_success'))

@app.route('/select-bookmarks')
def select_bookmarks():
    """顯示書籤選擇頁面"""
    # 檢查是否有書籤文件路徑
    if 'bookmark_file_path' not in session or 'bookmark_summary' not in session:
        flash('沒有找到書籤資料，請重新分析', 'warning')
        return redirect(url_for('upload_success'))
    
    try:
        # 從臨時文件讀取書籤數據
        bookmark_file_path = session['bookmark_file_path']
        
        # 檢查文件是否存在
        if not os.path.exists(bookmark_file_path):
            flash('書籤數據已過期，請重新分析', 'error')
            return redirect(url_for('upload_success'))
        
        # 讀取完整書籤數據
        with open(bookmark_file_path, 'r', encoding='utf-8') as f:
            bookmark_data = json.load(f)
        
        file_info = session.get('uploaded_file', {})
        
        app.logger.info(f'從臨時文件加載書籤數據: {len(bookmark_data.get("bookmarks", []))} 個書籤')
        
        return render_template('select_bookmarks.html', 
                             bookmark_data=bookmark_data, 
                             file_info=file_info)
                             
    except Exception as e:
        app.logger.error(f'讀取書籤數據時發生錯誤: {str(e)}')
        flash('讀取書籤數據失敗，請重新分析', 'error')
        return redirect(url_for('upload_success'))

@app.route('/process-split', methods=['POST'])
def process_split():
    """處理分割請求"""
    # 檢查是否有必要的資料
    if 'bookmark_file_path' not in session or 'uploaded_file' not in session:
        flash('會話資料遺失，請重新開始', 'error')
        return redirect(url_for('index'))
    
    # 獲取選中的書籤 ID
    selected_bookmark_ids = request.form.getlist('selected_bookmarks')
    
    if not selected_bookmark_ids:
        flash('請至少選擇一個書籤作為分割點', 'warning')
        return redirect(url_for('select_bookmarks'))
    
    try:
        # 轉換為整數
        selected_ids = [int(bid) for bid in selected_bookmark_ids]
        
        # 從臨時文件讀取書籤數據
        bookmark_file_path = session['bookmark_file_path']
        if not os.path.exists(bookmark_file_path):
            flash('書籤數據已過期，請重新分析', 'error')
            return redirect(url_for('upload_success'))
        
        with open(bookmark_file_path, 'r', encoding='utf-8') as f:
            bookmark_data = json.load(f)
        
        bookmarks = bookmark_data['bookmarks']
        
        # 找到選中的書籤
        selected_bookmarks = [b for b in bookmarks if b['id'] in selected_ids and b['valid']]
        
        if not selected_bookmarks:
            flash('所選書籤無效，請重新選擇', 'error')
            return redirect(url_for('select_bookmarks'))
        
        # 提取頁碼作為分割點
        split_points = [b['page_num'] for b in selected_bookmarks if b['page_num']]
        
        if not split_points:
            flash('選中的書籤沒有有效的頁碼', 'error')
            return redirect(url_for('select_bookmarks'))
        
        # 獲取原始 PDF 檔案路徑
        file_info = session['uploaded_file']
        pdf_path = file_info['filepath']
        
        # 驗證原始檔案是否仍然存在
        if not os.path.exists(pdf_path):
            flash('原始 PDF 檔案已遺失，請重新上傳', 'error')
            cleanup_session_files()
            return redirect(url_for('index'))
        
        app.logger.info(f'開始分割 PDF: {len(split_points)} 個分割點')
        
        # 執行 PDF 分割
        split_result = split_pdf(pdf_path, split_points)
        
        if not split_result['success']:
            flash('PDF 分割失敗，請重試', 'error')
            return redirect(url_for('select_bookmarks'))
        
        app.logger.info(f'PDF 分割成功: 創建了 {split_result["total_parts"]} 個檔案')
        
        # 自動創建 ZIP 檔案
        zip_result = None
        try:
            app.logger.info('開始創建 ZIP 檔案...')
            zip_result = create_zip_from_pdf_split_result(split_result)
            
            if zip_result['success']:
                app.logger.info(f'ZIP 創建成功: {zip_result["zip_filename"]}, '
                               f'壓縮率 {zip_result["compression_ratio"]}%')
            else:
                app.logger.warning('ZIP 創建失敗，但繼續提供單檔下載')
                
        except ZipCreationError as e:
            app.logger.error(f'ZIP 創建錯誤: {str(e)}')
            flash(f'ZIP 檔案創建失敗: {str(e)}，但您仍可以下載個別檔案', 'warning')
            
        except Exception as e:
            app.logger.error(f'ZIP 創建時發生未預期錯誤: {str(e)}')
            flash('ZIP 檔案創建時發生錯誤，但您仍可以下載個別檔案', 'warning')
        
        # 將分割結果和 ZIP 結果儲存到 session
        # 只保存必要的引用信息，避免 session 過大
        session['split_summary'] = {
            'success': True,
            'total_parts': split_result['total_parts'],
            'split_count': len(selected_bookmarks),
            'timestamp': datetime.now().isoformat()
        }
        
        # 只保存 ZIP 文件的關鍵信息
        if zip_result and zip_result.get('success'):
            session['zip_info'] = {
                'success': True,
                'zip_filename': zip_result['zip_filename'],
                'zip_path': zip_result['zip_path'],
                'compression_ratio': zip_result.get('compression_ratio', 0),
                # 為模板添加詳細字段
                'zip_size_mb': round(zip_result.get('zip_size', 0) / 1024 / 1024, 2),
                'total_files': len(split_result['split_files']),
                'original_size_mb': round(sum(f.get('file_size', 0) for f in split_result.get('split_files', [])) / 1024 / 1024, 2),
                'processing_time': zip_result.get('processing_time', 0)
            }
        else:
            session['zip_info'] = {'success': False}
        
        # 保存選中書籤的簡化信息
        session['selected_split_points'] = [
            {'title': b['title'][:30], 'page_num': b['page_num']} 
            for b in selected_bookmarks
        ]
        
        # 使用文件清理系統來存儲完整的分割結果引用
        session_id = get_session_id()
        
        # 註冊分割文件到清理系統
        for i, file_info in enumerate(split_result['split_files']):
            register_temp_file(
                file_info['filepath'], 
                context=f"{session_id}_split", 
                max_age_minutes=120
            )
        
        # 註冊 ZIP 文件
        if zip_result and zip_result.get('success'):
            register_temp_file(
                zip_result['zip_path'], 
                context=f"{session_id}_zip", 
                max_age_minutes=120
            )
        
        # 暫時存儲完整結果用於下載（不放在 session 中）
        # 使用 session_id 作為鍵來存儲到臨時位置
        temp_dir = create_temp_directory(prefix='split_results_', context=session_id, max_age_minutes=120, base_dir=TEMP_BASE_DIR)
        
        # 保存分割結果到臨時文件
        split_result_path = os.path.join(temp_dir, 'split_result.json')
        with open(split_result_path, 'w', encoding='utf-8') as f:
            # 包含模板需要的完整信息
            download_info = {
                'split_files': split_result['split_files'],
                'total_parts': split_result['total_parts'],
                'success': split_result['success'],
                # 為模板添加必要的字段
                'original_info': split_result.get('original_info', {
                    'filename': file_info.get('original_filename', ''),
                    'total_pages': 0,  # 這個信息可能不在 split_result 中
                    'size_mb': round(file_info.get('file_size', 0) / 1024 / 1024, 2)
                }),
                'split_summary': split_result.get('split_summary', {
                    'total_output_size': sum(f.get('file_size', 0) for f in split_result.get('split_files', []))
                }),
                'processing_time': split_result.get('processing_time', 0)
            }
            json.dump(download_info, f, ensure_ascii=False, indent=2)
        
        register_temp_file(split_result_path, context=session_id, max_age_minutes=120)
        session['split_result_path'] = split_result_path
        
        # 重定向到結果頁面
        return redirect(url_for('split_results'))
        
    except (PDFSplittingError, InvalidSplitPointError) as e:
        app.logger.error(f'PDF 分割錯誤: {str(e)}')
        flash(f'PDF 分割失敗: {str(e)}', 'error')
        return redirect(url_for('select_bookmarks'))
        
    except ValueError:
        flash('選擇的書籤格式無效', 'error')
        return redirect(url_for('select_bookmarks'))
    
    except Exception as e:
        app.logger.error(f'處理分割請求時發生錯誤: {str(e)}', exc_info=True)
        flash('處理分割請求時發生錯誤，請重試', 'error')
        return redirect(url_for('select_bookmarks'))

@app.route('/split-results')
def split_results():
    """顯示分割結果頁面"""
    # 檢查是否有分割結果摘要
    if 'split_summary' not in session or 'split_result_path' not in session:
        flash('沒有找到分割結果，請重新進行分割', 'warning')
        return redirect(url_for('select_bookmarks'))
    
    try:
        # 從臨時文件讀取完整的分割結果
        split_result_path = session['split_result_path']
        if not os.path.exists(split_result_path):
            flash('分割結果已過期，請重新分割', 'error')
            return redirect(url_for('select_bookmarks'))
        
        import json
        with open(split_result_path, 'r', encoding='utf-8') as f:
            split_result = json.load(f)
        
        # 從 session 獲取其他信息
        zip_info = session.get('zip_info', {'success': False})
        file_info = session.get('uploaded_file', {})
        selected_split_points = session.get('selected_split_points', [])
        
        return render_template('split_results.html', 
                             split_result=split_result,
                             zip_result=zip_info,  # 使用 zip_info 而不是 zip_result
                             file_info=file_info,
                             selected_bookmarks=selected_split_points)  # 使用簡化的分割點信息
                             
    except Exception as e:
        app.logger.error(f'讀取分割結果時發生錯誤: {str(e)}')
        flash('讀取分割結果失敗，請重新分割', 'error')
        return redirect(url_for('select_bookmarks'))

@app.route('/download-file/<int:file_index>')
def download_file(file_index):
    """下載單個分割檔案"""
    # 檢查是否有分割結果
    if 'split_result_path' not in session:
        flash('沒有找到分割結果，請重新進行分割', 'error')
        return redirect(url_for('index'))
    
    try:
        # 從臨時文件讀取分割結果
        split_result_path = session['split_result_path']
        if not os.path.exists(split_result_path):
            flash('分割結果已過期，請重新分割', 'error')
            return redirect(url_for('split_results'))
        
        import json
        with open(split_result_path, 'r', encoding='utf-8') as f:
            split_result = json.load(f)
        
        split_files = split_result['split_files']
        
        # 驗證檔案索引
        if file_index < 1 or file_index > len(split_files):
            flash('無效的檔案索引', 'error')
            return redirect(url_for('split_results'))
        
        # 獲取指定的檔案
        file_info = split_files[file_index - 1]
        file_path = file_info['filepath']
        
        # 檢查檔案是否存在
        if not os.path.exists(file_path):
            flash(f'檔案 {file_info["filename"]} 已遺失', 'error')
            return redirect(url_for('split_results'))
        
        # 使用 Flask 的 send_file 發送檔案
        from flask import send_file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_info['filename'],
            mimetype='application/pdf'
        )
        
    except Exception as e:
        app.logger.error(f'下載檔案時發生錯誤: {str(e)}')
        flash('下載檔案時發生錯誤，請重試', 'error')
        return redirect(url_for('split_results'))

@app.route('/download-zip')
def download_zip():
    """下載 ZIP 檔案"""
    # 檢查是否有 ZIP 結果
    if 'zip_info' not in session:
        flash('沒有找到 ZIP 檔案，請重新進行分割', 'error')
        return redirect(url_for('split_results'))
    
    zip_info = session['zip_info']
    
    # 檢查 ZIP 是否創建成功
    if not zip_info.get('success', False):
        flash('ZIP 檔案創建失敗', 'error')
        return redirect(url_for('split_results'))
    
    zip_path = zip_info['zip_path']
    
    # 檢查 ZIP 檔案是否存在
    if not os.path.exists(zip_path):
        flash(f'ZIP 檔案 {zip_info["zip_filename"]} 已遺失', 'error')
        return redirect(url_for('split_results'))
    
    try:
        # 使用 Flask 的 send_file 發送 ZIP 檔案
        from flask import send_file
        
        app.logger.info(f'開始下載 ZIP 檔案: {zip_info["zip_filename"]}')
        
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=zip_info['zip_filename'],
            mimetype='application/zip'
        )
    except Exception as e:
        app.logger.error(f'下載 ZIP 檔案時發生錯誤: {str(e)}')
        flash('下載 ZIP 檔案時發生錯誤，請重試', 'error')
        return redirect(url_for('split_results'))

@app.route('/preview-split', methods=['POST'])
def preview_split():
    """預覽分割結果（不實際分割檔案）"""
    # 檢查是否有必要的資料
    if 'bookmark_file_path' not in session or 'uploaded_file' not in session:
        return {'success': False, 'error': '會話資料遺失'}
    
    try:
        # 獲取選中的書籤 ID
        data = request.get_json()
        selected_bookmark_ids = data.get('selected_bookmarks', [])
        
        if not selected_bookmark_ids:
            return {'success': False, 'error': '請至少選擇一個書籤'}
        
        # 從臨時文件讀取書籤數據
        bookmark_file_path = session['bookmark_file_path']
        if not os.path.exists(bookmark_file_path):
            return {'success': False, 'error': '書籤數據已過期'}
        
        with open(bookmark_file_path, 'r', encoding='utf-8') as f:
            bookmark_data = json.load(f)
        
        bookmarks = bookmark_data['bookmarks']
        
        # 找到選中的書籤
        selected_bookmarks = [b for b in bookmarks if b['id'] in selected_bookmark_ids and b['valid']]
        split_points = [b['page_num'] for b in selected_bookmarks if b['page_num']]
        
        # 獲取原始 PDF 檔案路徑
        file_info = session['uploaded_file']
        pdf_path = file_info['filepath']
        
        # 生成預覽
        preview_result = get_split_preview(pdf_path, split_points)
        return preview_result
        
    except Exception as e:
        app.logger.error(f'預覽分割時發生錯誤: {str(e)}')
        return {'success': False, 'error': '預覽失敗'}

@app.route('/clear-session')
def clear_session():
    """清理 session 並返回首頁"""
    cleanup_session_files()
    flash('已清理上傳資料', 'success')
    return redirect(url_for('index'))

@app.route('/cleanup-stats')
def cleanup_stats():
    """顯示文件清理統計（僅在開發模式下可用）"""
    if not app.debug:
        return "Not available in production", 403
    
    stats = get_cleanup_stats()
    return {
        'cleanup_stats': stats,
        'message': 'File cleanup statistics'
    }

@app.route('/force-cleanup')
def force_cleanup():
    """強制清理過期文件（僅在開發模式下可用）"""
    if not app.debug:
        return "Not available in production", 403
    
    try:
        cleaned_count = cleanup_expired_files()
        return {
            'success': True,
            'cleaned_files': cleaned_count,
            'message': f'Successfully cleaned {cleaned_count} expired files'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': 'Failed to clean expired files'
        }

# 定期清理任務
import threading
import time as time_module

def periodic_cleanup():
    """定期清理過期文件的後台任務"""
    while True:
        try:
            # 每 30 分鐘清理一次過期文件
            time_module.sleep(30 * 60)  # 30 分鐘
            
            with app.app_context():
                cleaned_count = cleanup_expired_files()
                if cleaned_count > 0:
                    app.logger.info(f'定期清理: 清理了 {cleaned_count} 個過期文件')
                    
        except Exception as e:
            if app:
                app.logger.error(f'定期清理任務發生錯誤: {str(e)}')

# 啟動定期清理線程
cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()

# 錯誤處理器
@app.errorhandler(404)
def page_not_found(e):
    """404 錯誤處理器"""
    app.logger.warning(f'404 錯誤: {request.url}')
    return render_template('404.html'), 404

@app.errorhandler(413)
def request_entity_too_large(e):
    """413 錯誤處理器（檔案過大）"""
    app.logger.warning(f'413 錯誤: 檔案過大 - {request.url}')
    return render_template('413.html', max_size='500MB'), 413

@app.errorhandler(500)
def internal_server_error(e):
    """500 錯誤處理器"""
    app.logger.error(f'500 錯誤: {str(e)} - {request.url}')
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """通用異常處理器"""
    app.logger.error(f'未處理的異常: {str(e)} - {request.url}', exc_info=True)
    return render_template('500.html'), 500

# 設定日誌記錄
def setup_logging():
    """設定應用程式日誌記錄"""
    if IS_PRODUCTION:
        # 生產環境：只使用控制台日誌
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        console_handler.setLevel(logging.INFO)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('PDF 分割工具應用程式啟動（生產環境）')
    else:
        # 開發環境：嘗試文件日誌，失敗則使用控制台
        try:
            # 創建 logs 目錄（如果不存在）
            logs_dir = os.path.join(TEMP_BASE_DIR, 'logs')
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            
            # 設定檔案處理器進行日誌記錄
            file_handler = RotatingFileHandler(
                os.path.join(logs_dir, 'app.log'), 
                maxBytes=5120,  # 5KB
                backupCount=3,
                encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            
            app.logger.setLevel(logging.INFO)
            app.logger.info('PDF 分割工具應用程式啟動（開發環境）')
        except (PermissionError, OSError):
            # 如果無法寫入文件，使用控制台日誌
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s'
            ))
            console_handler.setLevel(logging.INFO)
            app.logger.addHandler(console_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.warning('無法寫入日誌文件，使用控制台日誌')

if __name__ == '__main__':
    # 設定日誌記錄
    setup_logging()
    
    # 記錄啟動資訊
    app.logger.info(f'臨時目錄: {UPLOAD_FOLDER}')
    app.logger.info(f'最大檔案大小: {app.config["MAX_CONTENT_LENGTH"]} 位元組')
    app.logger.info(f'運行環境: {"生產" if IS_PRODUCTION else "開發"}')
    app.logger.info(f'監聽端口: {PORT}')
    
    # 啟動應用
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=not IS_PRODUCTION
    ) 