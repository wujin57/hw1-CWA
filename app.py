"""
app.py
職責：Flask Web 應用程式 (Presentation & API Layer)。
      相容 Vercel Serverless Functions (唯讀檔案系統與 /tmp) 與本機端直接執行。
      從 SQLite 資料庫 (data.db) 查詢氣溫資料，提供地區下拉選單、
      最高/最低溫折線圖、一週資料表格以及進階台灣地圖視覺化展示。
      具備自動過期檢測與「即時更新 (Real-time Sync)」功能。
遵循「單一職責原則 (SRP)」，專注於展示層與 HTTP API 傳輸。
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
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

# 台灣時區 (Asia/Taipei, UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))

# 判斷是否運行於 Vercel Serverless 環境 (檔案系統唯讀，僅 /tmp 可寫入)
IS_VERCEL = bool(os.getenv("VERCEL"))
if IS_VERCEL:
    DB_PATH = "/tmp/data.db"
    RAW_JSON_PATH = "/tmp/weather_raw.json"
    REPO_DB = os.path.join(CURRENT_DIR, "data.db")
    REPO_JSON = os.path.join(CURRENT_DIR, "weather_raw.json")
    if not os.path.exists(DB_PATH) and os.path.exists(REPO_DB):
        try:
            shutil.copyfile(REPO_DB, DB_PATH)
        except Exception as e:
            print(f"[!] 複製初始 data.db 至 /tmp 失敗: {e}", file=sys.stderr)
    if not os.path.exists(RAW_JSON_PATH) and os.path.exists(REPO_JSON):
        try:
            shutil.copyfile(REPO_JSON, RAW_JSON_PATH)
        except Exception as e:
            print(f"[!] 複製初始 weather_raw.json 至 /tmp 失敗: {e}", file=sys.stderr)
else:
    DB_PATH = os.path.join(CURRENT_DIR, "data.db")
    RAW_JSON_PATH = os.path.join(CURRENT_DIR, "weather_raw.json")


def get_today_str() -> str:
    """取得台灣當前日期字串 (YYYY-MM-DD)。"""
    return datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")


def is_data_stale(records: list, today_str: str) -> bool:
    """
    檢查資料庫中的預報資料是否已過期：
    - 若無任何紀錄 -> 過期
    - 若最早日期早於今日 -> 過期 (需要滾動至今日為起點)
    - 若今日不在預報日期清單中 -> 過期
    """
    if not records:
        return True
    dates = sorted(set(r.get("dataDate", "") for r in records if "dataDate" in r))
    if not dates:
        return True
    # 最早的一天早於今天，即資料過期
    if dates[0] < today_str:
        return True
    # 今日尚未在預報範圍中
    if today_str not in dates:
        return True
    return False


def execute_pipeline_update() -> list:
    """
    執行完整的資料更新管線 (fetch -> parse -> database save)。
    更新為以今日為起始日之 7 天預報資料。
    """
    import fetch_weather
    print(f"[*] 執行即時資料更新管線 (目標: 今日 {get_today_str()} 起 7 天)...")
    fetch_weather.update_weather(output_path=RAW_JSON_PATH)
    cleaned = parse_weather.parse_weather_json(RAW_JSON_PATH)
    database.save_forecasts(cleaned, db_path=DB_PATH, clear_existing=True)
    return cleaned


def ensure_db_ready():
    """
    確保 SQLite 資料庫與氣溫預報資料備妥且為最新日期。
    """
    try:
        today_str = get_today_str()
        records = database.query_forecasts(db_path=DB_PATH)
        if is_data_stale(records, today_str):
            print(f"[*] 檢測到氣象資料需即時更新 (今日: {today_str})，正在執行管線...")
            execute_pipeline_update()
    except Exception as e:
        print(f"[!] 資料庫初始檢查警告: {e}", file=sys.stderr)


# 伺服器啟動時確保資料庫可用且即時
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
    若檢測到資料過期，自動即時更新為今日最新 7 天預報。
    支援依地區篩選：/api/forecasts?region=中部地區
    使用標準 SQL：SELECT id, regionName, dataDate, minT, maxT FROM TemperatureForecasts ...
    """
    region = request.args.get("region")
    today_str = get_today_str()

    try:
        records = database.query_forecasts(
            db_path=DB_PATH,
            region=region if region and region != "ALL" else None
        )

        # 檢查是否需要即時更新過期資料
        if is_data_stale(records, today_str):
            execute_pipeline_update()
            records = database.query_forecasts(
                db_path=DB_PATH,
                region=region if region and region != "ALL" else None
            )

        # 針對唯讀環境備援
        if not records and os.path.exists(RAW_JSON_PATH):
            records = parse_weather.parse_weather_json(RAW_JSON_PATH)
            if region and region != "ALL":
                records = [r for r in records if r["regionName"] == region]

        return jsonify({
            "status": "success",
            "count": len(records),
            "today": today_str,
            "data": records
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/refresh", methods=["GET", "POST"])
def refresh_data():
    """
    主動觸發氣象資料管線更新 (fetch -> parse -> database)。
    """
    try:
        cleaned = execute_pipeline_update()
        dates = sorted(set(r["dataDate"] for r in cleaned))
        date_range = f"{dates[0]} ~ {dates[-1]}" if dates else ""
        return jsonify({
            "status": "success",
            "message": f"氣象資料即時更新成功！預報區間: {date_range}，共儲存 {len(cleaned)} 筆紀錄。",
            "count": len(cleaned),
            "date_range": date_range,
            "today": get_today_str()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"即時更新失敗: {e}"
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    print(f"\n=======================================================")
    print(f"  HW1 Taiwan Weather Web App 啟動中...")
    print(f"  本地預覽網址: http://localhost:{port}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=True)
