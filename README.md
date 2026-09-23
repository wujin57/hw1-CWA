# HW10 - Taiwan Weather Forecast (從氣象資料到互動式天氣預報應用程式)

本專案依據單一職責原則 (Single Responsibility Principle, SRP) 實作，串接交通部中央氣象署 (CWA) 開放資料 API，擷取台灣六大區域一週氣溫預報，清洗萃取每日最高與最低氣溫存入 SQLite 資料庫，並採用 **Vercel Serverless 架構 (Flask + 現代化響應式前端)** 提供高質感視覺化儀表板。

---

## 專案結構與模組分工

```text
HW10_weather/
├── fetch_weather.py     # 模組 1：取得 CWA API 資料並儲存原始 JSON 檔案
├── parse_weather.py     # 模組 2：分析 JSON，提取 6 大區域每日最高與最低氣溫
├── database.py          # 模組 3：建立 SQLite 資料庫 (data.db) 並寫入氣溫資料
├── app.py               # 模組 4：Flask Web App (從 SQLite 讀取資料並視覺化)
├── api/
│   └── index.py         # Vercel Serverless Function 入口點 (導向 app.py)
├── vercel.json          # Vercel 路由設定檔
├── templates/
│   └── index.html       # 現代化 Web 儀表板 (含地區下拉選單、折線圖、一週表格與台灣地圖)
├── requirements.txt     # 依賴套件清單 (requests, Flask)
├── weather_raw.json     # 格式化原始氣溫預報 JSON
├── data.db              # SQLite 氣溫預報資料庫
└── README.md            # 專案說明文件
```

---

## 核心模組功能介紹

### 1. 取得 CWA API 資料 (`fetch_weather.py`)
- 使用 `requests` 呼叫中央氣象署開放資料 API (`F-A0010-001`)。
- 在 Request Headers 中帶入 Authorization Key：`CWA_API_KEY = "YOUR_API_KEY"`。
- 將回傳的 JSON 完整內容以格式化方式（`indent=2, ensure_ascii=False`）儲存為 `weather_raw.json`，並包含完整的 HTTP 錯誤處理機制與離線測試模式。

### 2. 分析 JSON，提取氣溫資料 (`parse_weather.py`)
- 讀取 `weather_raw.json`，走訪 JSON 階層：`records -> locations -> location[] -> weatherElement[] -> time[]`。
- 提取六大區域（北部地區、中部地區、南部地區、東北部地區、東部地區、東南部地區）每日最低氣溫 (`MinT`) 與最高氣溫 (`MaxT`)。
- 封裝成 List of Dictionaries，每筆結構包含：`regionName` (TEXT), `dataDate` (TEXT), `minT` (REAL), `maxT` (REAL)，精確覆蓋 7 天預報。

### 3. 存入 SQLite 資料庫 (`database.py`)
- 將清洗後的氣溫資料存入 SQLite 資料庫 `data.db`。
- 資料庫 Table 設計：
  ```sql
  CREATE TABLE IF NOT EXISTS TemperatureForecasts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      regionName TEXT,
      dataDate TEXT,
      minT REAL,
      maxT REAL
  );
  ```
- 內建兩大投影片指定驗證查詢：
  1. 列出所有地區名稱：`SELECT DISTINCT regionName FROM TemperatureForecasts;`
  2. 查詢中部地區資料：`SELECT * FROM TemperatureForecasts WHERE regionName = '中部地區';`

### 4. 氣溫預報 Web App (`app.py` & Vercel)
- 採用 Vercel Serverless 架構搭配 Flask，反應極速、冷啟動小於 100ms。
- **地區下拉選單**：支援切換六大區域。
- **SQLite 即時查詢**：後端透過標準 SQL 語法從 `data.db` 動態撈取所選地區之資料。
- **最高/最低溫折線圖**：動態繪製 MaxT（紅線）與 MinT（藍線）之氣溫變化趨勢。
- **一週資料表格**：對齊呈現 Date、MinT、MaxT，並附一鍵 CSV 下載。
- **進階：台灣地圖視覺化 (Optional)**：整合 Leaflet 互動地圖，依各區當日平均溫度自動著色（<20°C 藍、20-25°C 綠、25-30°C 黃、>30°C 紅），點擊標記即可聯動切換折線圖與表格！

---

## 本機執行指南

```bash
cd /Users/wujinsong/Desktop/AiOt/HW10_weather

# 1. 安裝套件
pip install -r requirements.txt

# 2. 執行資料管線 (一次即可)
python3 fetch_weather.py
python3 parse_weather.py
python3 database.py

# 3. 啟動 Web App
python3 app.py
```
啟動後開啟瀏覽器造訪 `http://localhost:3000` 即可預覽！

---

## 🚀 部署至 Vercel 步驟

1. 推送代碼至 GitHub：
   ```bash
   git add .
   git commit -m "feat: complete HW10 weather forecast with Vercel deployment"
   git push origin main
   ```
2. 登入 [Vercel 官網](https://vercel.com)，點擊 **"Add New..."** -> **"Project"**。
3. 匯入您的 GitHub 儲存庫 `hw1-CWA-`，點擊 **"Deploy"**，30 秒內即可上線！
