// PDF 分割工具 - 主要 JavaScript 檔案

document.addEventListener('DOMContentLoaded', function() {
    console.log('PDF 分割工具已載入');
    
    // 初始化應用程式
    initializeApp();
});

/**
 * 初始化應用程式
 */
function initializeApp() {
    // 設定通用事件監聽器
    setupEventListeners();
    
    // 檢查當前頁面並初始化對應功能
    initializePageSpecificFeatures();
}

/**
 * 根據當前頁面初始化特定功能
 */
function initializePageSpecificFeatures() {
    // 檢查是否為首頁（有檔案上傳功能）
    const fileInput = document.getElementById('file');
    const fileLabel = document.querySelector('.file-label');
    const form = document.querySelector('.upload-form');
    
    if (fileInput && fileLabel && form) {
        // 首頁：設定檔案上傳功能
        setupFileUpload();
        console.log('首頁檔案上傳功能已初始化');
    } else {
        // 其他頁面：僅顯示頁面載入訊息
        console.log('非首頁，跳過檔案上傳功能初始化');
    }
    
    // 顯示歡迎訊息（所有頁面通用）
    showWelcomeMessage();
}

/**
 * 設定事件監聽器
 */
function setupEventListeners() {
    // 自動隱藏 Flash 訊息
    setupFlashMessages();
    
    console.log('事件監聽器已設定');
}

/**
 * 顯示歡迎訊息
 */
function showWelcomeMessage() {
    console.log('歡迎使用 PDF 分割工具！');
    
    // 檢查瀏覽器是否支援 File API（僅在有檔案上傳功能的頁面檢查）
    const hasFileUpload = document.getElementById('file');
    if (hasFileUpload) {
        if (window.File && window.FileReader && window.FileList && window.Blob) {
            console.log('瀏覽器支援檔案 API');
        } else {
            console.warn('瀏覽器不完全支援檔案 API，某些功能可能無法正常運作');
            showError('您的瀏覽器不完全支援檔案上傳功能，建議使用較新版本的瀏覽器');
        }
    }
}

/**
 * 設定檔案上傳功能
 */
function setupFileUpload() {
    const fileInput = document.getElementById('file');
    const fileLabel = document.querySelector('.file-label');
    const form = document.querySelector('.upload-form');
    
    // 檔案選擇事件
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        const fileText = document.querySelector('.file-text');
        
        if (file) {
            // 檢查檔案類型
            if (file.type !== 'application/pdf') {
                showError('請選擇 PDF 檔案');
                fileInput.value = '';
                return;
            }
            
            // 檢查檔案大小（500MB 限制）
            const maxSize = 500 * 1024 * 1024; // 500MB in bytes
            if (file.size > maxSize) {
                showError('檔案大小超過 500MB 限制');
                fileInput.value = '';
                return;
            }
            
            // 更新顯示文字
            fileText.textContent = `已選擇: ${file.name} (${formatFileSize(file.size)})`;
            console.log('檔案選擇成功:', file.name, formatFileSize(file.size));
        }
    });
    
    // 拖放功能
    fileLabel.addEventListener('dragover', function(e) {
        e.preventDefault();
        fileLabel.classList.add('drag-over');
    });
    
    fileLabel.addEventListener('dragleave', function(e) {
        e.preventDefault();
        fileLabel.classList.remove('drag-over');
    });
    
    fileLabel.addEventListener('drop', function(e) {
        e.preventDefault();
        fileLabel.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            fileInput.dispatchEvent(new Event('change'));
        }
    });
    
    // 表單提交驗證
    form.addEventListener('submit', function(e) {
        const file = fileInput.files[0];
        
        if (!file) {
            e.preventDefault();
            showError('請先選擇一個 PDF 檔案');
            return;
        }
        
        if (file.type !== 'application/pdf') {
            e.preventDefault();
            showError('只允許上傳 PDF 檔案');
            return;
        }
        
        // 顯示載入狀態
        showLoading('正在上傳並處理檔案...');
    });
}

/**
 * 設定 Flash 訊息功能
 */
function setupFlashMessages() {
    // 自動隱藏成功訊息
    const successMessages = document.querySelectorAll('.flash-success');
    successMessages.forEach(message => {
        setTimeout(() => {
            if (message.parentElement) {
                message.remove();
            }
        }, 5000); // 5秒後自動隱藏
    });
}

/**
 * 格式化檔案大小
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 工具函數：顯示載入狀態
 */
function showLoading(message = '處理中...') {
    console.log('載入狀態：', message);
    
    // 禁用上傳按鈕
    const uploadBtn = document.querySelector('.btn-upload');
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = `<span class="btn-icon">⏳</span> ${message}`;
    }
}

/**
 * 工具函數：隱藏載入狀態
 */
function hideLoading() {
    console.log('載入完成');
    
    // 恢復上傳按鈕
    const uploadBtn = document.querySelector('.btn-upload');
    if (uploadBtn) {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<span class="btn-icon">📤</span> 上傳並處理';
    }
}

/**
 * 工具函數：顯示資訊訊息
 */
function showInfo(message) {
    console.log('資訊：', message);
    
    // 創建並顯示資訊訊息
    const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
    const infoDiv = document.createElement('div');
    infoDiv.className = 'flash-message flash-info';
    infoDiv.innerHTML = `
        <span class="flash-text">${message}</span>
        <button type="button" class="flash-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    flashContainer.appendChild(infoDiv);
    
    // 3秒後自動移除
    setTimeout(() => {
        if (infoDiv.parentElement) {
            infoDiv.remove();
        }
    }, 3000);
}

/**
 * 工具函數：顯示錯誤訊息
 */
function showError(message) {
    console.error('錯誤：', message);
    
    // 創建並顯示錯誤訊息
    const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
    const errorDiv = document.createElement('div');
    errorDiv.className = 'flash-message flash-error';
    errorDiv.innerHTML = `
        <span class="flash-text">${message}</span>
        <button type="button" class="flash-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    flashContainer.appendChild(errorDiv);
    
    // 5秒後自動移除
    setTimeout(() => {
        if (errorDiv.parentElement) {
            errorDiv.remove();
        }
    }, 5000);
}

/**
 * 工具函數：顯示成功訊息
 */
function showSuccess(message) {
    console.log('成功：', message);
    
    // 創建並顯示成功訊息
    const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
    const successDiv = document.createElement('div');
    successDiv.className = 'flash-message flash-success';
    successDiv.innerHTML = `
        <span class="flash-text">${message}</span>
        <button type="button" class="flash-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    flashContainer.appendChild(successDiv);
    
    // 5秒後自動移除
    setTimeout(() => {
        if (successDiv.parentElement) {
            successDiv.remove();
        }
    }, 5000);
}

/**
 * 創建 Flash 訊息容器
 */
function createFlashContainer() {
    const header = document.querySelector('header');
    const main = document.querySelector('main');
    
    const flashContainer = document.createElement('div');
    flashContainer.className = 'flash-messages';
    
    if (header && main) {
        header.parentNode.insertBefore(flashContainer, main);
    } else {
        document.body.appendChild(flashContainer);
    }
    
    return flashContainer;
} 