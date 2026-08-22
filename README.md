# Elderly Fall Detection MVP

使用固定相機與 Ultralytics YOLO11-Pose，在本機追蹤人體姿態；疑似倒地經確認後開始計時，持續 30 秒便發出本機及手機通知，並保存事件前後影片。

> 這是照護輔助原型，不是醫療器材，也不能保證偵測所有跌倒。請勿讓它成為唯一緊急求助方式，第一版也不會自動撥打 119。

## 功能

- USB、影片檔或 RTSP 相機輸入
- YOLO Pose 人體關節點與 ByteTrack 人物追蹤
- `normal → suspected → on_ground → alerted` 狀態機
- 預設倒地持續 30 秒後警報
- 在預覽視窗按 `C` 取消，按 `Q` 離開
- 保存警報前 10 秒、後 20 秒 MP4
- 選用 LINE Messaging API 文字通知
- 選用 Bark iOS 緊急推播，可設定 Critical Alert 與約 30 秒持續鈴聲

## 安裝

建議安裝 Anaconda 或 Miniconda，並建立獨立的 Python 3.12 環境：

```powershell
conda create --name fall-detection python=3.12 -y
conda activate fall-detection
python -m pip install -r requirements.txt
Copy-Item config.example.yaml config.yaml
```

`config.yaml` 保存相機、LINE 與 Bark 等本機設定，已被 `.gitignore` 排除。請勿將通知 Token 或裝置 Key 寫入 `config.example.yaml`。

首次執行會由 Ultralytics 下載模型。啟動 USB 相機：

```powershell
python app.py --config config.yaml
```

之後每次重新開啟 PowerShell，只需要：

```powershell
cd elderly-fall-detection-system
conda activate fall-detection
python app.py
```

確認目前使用正確的 Conda 環境：

```powershell
conda env list
python -c "import sys; print(sys.executable)"
```

Python 路徑應包含 `envs\fall-detection\python.exe`。要離開環境時執行 `conda deactivate`。

要先用錄好的影片測試，將 `config.yaml` 的 `camera.source` 改成影片路徑。RTSP 相機則填完整 RTSP URL。

## LINE 通知設定

1. 在 LINE Developers 建立 Provider、Messaging API channel 與 Official Account。
2. 讓接收通知的人加入該 Official Account。
3. 取得 channel access token 與接收者 user ID。
4. 在 `config.yaml` 設定 `line_enabled: true`，並填入 token。
5. `line_target: single` 只通知指定的 `line_user_id`；`broadcast` 會通知所有已加入官方帳號且未封鎖的好友，此時 `line_user_id` 可留空。

正式部署不應把 token 提交到版本控制；後續版本應改用環境變數或祕密管理服務。LINE 訊息目前只包含本機事件檔名，因為 Messaging API 的圖片 URL 必須能由 LINE 以 HTTPS 公開存取。

## Bark iOS 緊急推播

每台家人的 iPhone 安裝 Bark 後，從各自 App 取得並重新產生裝置 Key，直接填入本機 `config.yaml`，不要貼到聊天或提交版本控制：

```yaml
notification:
  bark_enabled: true
  bark_server: "https://api.day.app"
  bark_device_keys:
    - "第一台 iPhone 的新 Key"
    - "第二台 iPhone 的新 Key"
  bark_level: critical
  bark_volume: 10
  bark_sound: electronic
  bark_call: true
```

`critical` 需要在 iPhone/Bark 中允許重要通知；`bark_call: true` 會使用 Bark 的持續鈴聲模式。若不希望略過靜音或專注模式，可將層級改為 `timeSensitive` 或 `active`。LINE 與 Bark 可同時啟用，任一管道失敗不會阻止另一管道嘗試發送。

## 調整與實地驗證

每個房間的鏡頭高度、俯角、床和家具都不同，預設門檻只能當起點。請錄製且標記以下測試片段：

- 正常走路、坐下、起身、彎腰
- 躺床、躺沙發、坐地板
- 在保護措施與陪同下模擬慢速滑倒及快速倒地
- 人體部分遮擋、離開畫面與低光環境

優先調整 `horizontal_angle_degrees`、`bbox_aspect_ratio` 與 `confirmation_seconds`。實際評估應同時統計漏報率、誤報次數及從跌倒到通知的時間。

## 測試

核心狀態機不需要相機或模型即可測試：

```powershell
python -m unittest discover -s tests -v
```

## 已知限制

- 目前使用 2D 姿態規則，遮擋與鏡頭透視會影響結果。
- 目前按鍵取消需要預覽視窗；尚未加入語音、實體按鈕或手機回覆確認。
- LINE 尚未上傳圖片；事件影片只存在本機。
- 多房間、多相機、斷線重連及電話升級流程尚未實作。
