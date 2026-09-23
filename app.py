"""
app.py
職責：Flask Web 應用程式 (Presentation & API Layer)。
      相容 Vercel Serverless Functions 與本機端直接執行。
      從 SQLite 資料庫 (data.db) 查詢氣溫資料，提供地區下拉選單、
      最高/最低溫折線圖、一週資料表格以及進階台灣地圖視覺化展示。
遵循「單一職責原則 (SRP)」，專注於展示層與 HTTP API 傳輸。
"""

import os
import sys
import sqlite3
from flask import Flask, render_template, jsonify, request

# 設定專案路徑
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import database
import parse_weather

app = Flask(
    __name__,
    template_folder=os.path.join(CURRENT_DIR, "templates"),
    static_folder=os.path.join(CURRENT_DIR, "static")
)

DB_PATH = os.path.join(CURRENT_DIR, "data.db")
RAW_JSON_PATH = os.path.join(CURRENT_DIR, "weather_raw.json")


def ensure_db_ready():
    """
    確保 SQLite 資料庫與氣溫預報資料備妥。
    若 data.db 為空，自動由 weather_raw.json 進行解析與初始化。
    """
    try:
        records = database.query_forecasts(db_path=DB_PATH)
        if not records:
            if os.path.exists(RAW_JSON_PATH):
                print("[*] 正在從 weather_raw.json 導入初始氣象資料至 data.db ...")
                cleaned = parse_weather.parse_weather_json(RAW_JSON_PATH)
                database.save_forecasts(cleaned, db_path=DB_PATH)
            else:
                import fetch_weather
                print("[*] 產生預設 7 天氣溫預報資料...")
                fetch_weather.generate_mock_weather_data(RAW_JSON_PATH)
                cleaned = parse_weather.parse_weather_json(RAW_JSON_PATH)
                database.save_forecasts(cleaned, db_path=DB_PATH)
    except Exception as e:
        print(f"[!] 資料庫初始檢查警告: {e}", file=sys.stderr)


# 伺服器啟動時確保資料庫可用
ensure_db_ready()


@app.route("/")
def index():
    """
    首頁：呈現互動式天氣預報應用程式 (折線圖、一週表格與台灣地圖)。
    """
    return render_template("index.html")


@app.route("/api/forecasts", methods=["GET"])
def get_forecasts():
    """
    從 SQLite 資料庫 (data.db) 查詢氣溫預報資料。
    支援依地區篩選：/api/forecasts?region=中部地區
    使用標準 SQL：SELECT id, regionName, dataDate, minT, maxT FROM TemperatureForecasts ...
    """
    region = request.args.get("region")

    try:
        records = database.query_forecasts(
            db_path=DB_PATH,
            region=region if region and region != "ALL" else None
        )

        # 針對 Vercel Serverless 唯讀檔案系統之備援機制
        if not records and os.path.exists(RAW_JSON_PATH):
            records = parse_weather.parse_weather_json(RAW_JSON_PATH)
            if region and region != "ALL":
                records = [r for r in records if r["regionName"] == region]

        return jsonify({
            "status": "success",
            "count": len(records),
            "data": records
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/refresh", methods=["POST"])
def refresh_data():
    """
    觸發氣象資料管線更新 (fetch -> parse -> database)。
    """
    try:
        import fetch_weather
        fetch_weather.main()
        records = parse_weather.parse_weather_json(RAW_JSON_PATH)
        count = database.save_forecasts(records, db_path=DB_PATH)

        return jsonify({
            "status": "success",
            "message": f"氣象資料更新成功！共儲存 {count} 筆預報紀錄。",
            "count": count
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"更新失敗: {e}"
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"\n=======================================================")
    print(f"  HW10 Taiwan Weather Web App 啟動中...")
    print(f"  本地預覽網址: http://localhost:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=True)
