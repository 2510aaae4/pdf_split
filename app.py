import os
import tempfile
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, after_this_request
from datetime import datetime
from utils import get_bookmarks_recursive, split_pdf, create_zip_from_pdfs
from bookmark_filter import filter_bookmarks
from file_cleanup import register_temp_file, cleanup_files

app = Flask(__name__)

# 上傳設定
UPLOAD_FOLDER = tempfile.mkdtemp()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {'pdf'}
app.secret_key = 'supersecretkey'  # 用於 flash 與 session

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('未選擇檔案')
        return redirect(url_for('index'))
    file = request.files['file']
    if file.filename == '':
        flash('未選擇檔案')
        return redirect(url_for('index'))
    if not allowed_file(file.filename):
        flash('只允許上傳 PDF 檔案')
        return redirect(url_for('index'))
    if file.mimetype != 'application/pdf':
        flash('檔案類型錯誤，請選擇 PDF 檔案')
        return redirect(url_for('index'))
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        session['uploaded_file'] = {
            'original_filename': filename,
            'temp_path': filepath,
            'upload_time': datetime.now().isoformat(),
            'file_size': file_size
        }
        flash('檔案上傳成功')
        return redirect(url_for('parse_bookmarks'))
    except Exception as e:
        flash('檔案儲存失敗：' + str(e))
        return redirect(url_for('index'))

@app.route('/parse_bookmarks')
def parse_bookmarks():
    info = session.get('uploaded_file')
    if not info:
        return render_template('error.html', title='未上傳檔案', message='尚未上傳 PDF 檔案，請先回首頁上傳。')
    pdf_path = info['temp_path']
    bookmarks, status = get_bookmarks_recursive(pdf_path)
    if status.get('status') == 'file_not_found':
        return render_template('error.html', title='找不到檔案', message='找不到上傳的 PDF 檔案，請重新上傳。')
    if status.get('status') == 'error':
        err_msg = 'PDF 解析失敗，請確認檔案格式或內容。'
        if status.get('error'):
            err_msg += f"\n詳細錯誤：{status['error']}"
        return render_template('error.html', title='PDF 解析失敗', message=err_msg)
    filtered = filter_bookmarks(bookmarks)
    def count_matches(bms):
        count = 0
        for item in bms:
            if isinstance(item, list):
                count += count_matches(item)
            elif item.get('matches_pattern'):
                count += 1
        return count
    match_count = count_matches(filtered)
    status['match_count'] = match_count
    if not bookmarks or status.get('status') == 'no_bookmarks':
        return render_template('error.html', title='無書籤', message='此 PDF 沒有任何書籤，無法分割。')
    if match_count == 0:
        return render_template('error.html', title='無符合分割點', message='沒有任何書籤符合分割規則，請檢查書籤命名或手動選擇。')
    return render_template('bookmarks.html', bookmarks=filtered, status=status, fileinfo=info)

@app.route('/split_result')
def split_result():
    files = session.get('split_files')
    split_titles = session.get('split_titles')
    zip_path = session.get('zip_file')
    if not files:
        flash('尚未分割 PDF')
        return redirect(url_for('index'))
    zip_filename = os.path.basename(zip_path) if zip_path else None
    if not zip_path:
        try:
            from utils import create_zip_from_pdfs
            zip_path = create_zip_from_pdfs(files, split_titles)
            session['zip_file'] = zip_path
            zip_filename = os.path.basename(zip_path)
        except Exception as e:
            flash(f'建立 ZIP 失敗：{e}')
            zip_path = None
    return render_template('split_result.html', files=files, zip_filename=zip_filename)

@app.route('/select_bookmarks', methods=['GET', 'POST'])
def select_bookmarks():
    info = session.get('uploaded_file')
    pdf_path = info['temp_path'] if info else None
    bookmarks = None
    if pdf_path:
        from utils import get_bookmarks_recursive
        from bookmark_filter import filter_bookmarks
        bms, _ = get_bookmarks_recursive(pdf_path)
        bookmarks = filter_bookmarks(bms)
    if request.method == 'POST':
        selected = request.form.getlist('selected')
        if not selected:
            return render_template('select_bookmarks.html', bookmarks=bookmarks, error='請至少選擇一個分割點')
        split_points = []
        split_titles = []
        for val in selected:
            if '|' in val:
                page, title = val.split('|', 1)
            else:
                page, title = val, ''
            split_points.append(page)
            split_titles.append(title)
        session['selected_bookmarks'] = split_points
        try:
            split_files = split_pdf(pdf_path, split_points, bms, split_titles)
            session['split_files'] = split_files
            session['split_titles'] = split_titles
            flash(f'PDF 分割成功，共 {len(split_files)} 檔案')
            return redirect(url_for('split_result'))
        except Exception as e:
            return render_template('select_bookmarks.html', bookmarks=bookmarks, error=f'分割失敗：{e}')
    if not bookmarks:
        return render_template('select_bookmarks.html', bookmarks=[], error='找不到可用書籤，請先上傳並解析 PDF')
    return render_template('select_bookmarks.html', bookmarks=bookmarks)

@app.route('/download_split/<int:index>')
def download_split(index):
    files = session.get('split_files')
    if not files or index < 0 or index >= len(files):
        flash('找不到分割檔案')
        return redirect(url_for('split_result'))
    path = files[index]
    register_temp_file(path)
    @after_this_request
    def remove_file(response):
        cleanup_files()
        return response
    return send_file(path, as_attachment=True)

@app.route('/download/<filename>')
def download_zip(filename):
    zip_path = session.get('zip_file')
    if not zip_path or not os.path.exists(zip_path) or os.path.basename(zip_path) != filename:
        flash('找不到 ZIP 檔案')
        return redirect(url_for('split_result'))
    register_temp_file(zip_path)
    @after_this_request
    def remove_file(response):
        cleanup_files()
        return response
    return send_file(zip_path, as_attachment=True, mimetype='application/zip', download_name=filename)

# 錯誤處理
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(413)
def request_entity_too_large(e):
    return render_template('413.html', max_size='500MB'), 413

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Logging 設定
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 