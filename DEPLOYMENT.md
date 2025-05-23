# PDF 分割工具 - Render 部署指南

這個 PDF 分割工具現在已經配置為可以在 Render 雲端平台上部署。

## 🚀 部署到 Render

### 1. 準備 GitHub 倉庫
1. 將代碼推送到 GitHub 倉庫
2. 確保所有文件都已提交

### 2. 在 Render 上創建服務
1. 登入 [Render](https://render.com)
2. 點擊 "New +" → "Web Service"
3. 連接您的 GitHub 倉庫
4. 選擇這個項目的倉庫

### 3. 配置部署設置
- **Name**: `pdf-splitter` (或您選擇的名稱)
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn --config gunicorn.conf.py app:app`
- **Instance Type**: `Free` (或選擇付費方案)

### 4. 設置環境變量
在 Render 的環境變量設置中添加：
- `SECRET_KEY`: 生成一個隨機密鑰 (Render 可以自動生成)
- `RENDER`: `true` (告訴應用它在生產環境中運行)

### 5. 部署
點擊 "Create Web Service" 開始部署

## 📁 文件結構說明

部署相關的關鍵文件：
- `requirements.txt` - Python 依賴項
- `gunicorn.conf.py` - Gunicorn 服務器配置
- `render.yaml` - Render 部署配置
- `Procfile` - 備用啟動配置

## ⚙️ 生產環境特性

### 臨時文件處理
- 使用 `/tmp` 目錄存儲臨時文件（Render 唯一可寫目錄）
- 自動清理過期文件
- 書籤數據使用臨時文件而非 session cookies

### 日誌記錄
- 生產環境使用控制台日誌（適合 Render）
- 結構化日誌格式便於調試

### 安全性
- 從環境變量讀取密鑰
- 適當的錯誤處理

## 🔧 本地開發

如果要在本地測試生產環境配置：

1. 安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```

2. 設置環境變量：
   ```bash
   export SECRET_KEY="your-secret-key"
   export RENDER="true"
   export PORT="5000"
   ```

3. 使用 Gunicorn 啟動：
   ```bash
   gunicorn --config gunicorn.conf.py app:app
   ```

## 📊 監控和維護

- Render 提供內建的日誌查看功能
- 應用會自動清理臨時文件
- 可以通過 Render 儀表板監控資源使用情況

## ⚠️ 注意事項

1. **文件大小限制**: 保持在 500MB 以內
2. **臨時存儲**: 文件在重啟後會丟失（正常行為）
3. **內存使用**: 處理大型 PDF 時注意內存限制
4. **超時設置**: Gunicorn 設置了 30 秒超時

## 🆘 故障排除

### 常見問題
1. **部署失敗**: 檢查 requirements.txt 和 Python 版本
2. **文件上傳錯誤**: 確保文件大小在限制內
3. **臨時文件錯誤**: 檢查 /tmp 目錄權限

### 查看日誌
在 Render 儀表板中：
1. 進入您的服務
2. 點擊 "Logs" 標籤
3. 查看實時日誌輸出 