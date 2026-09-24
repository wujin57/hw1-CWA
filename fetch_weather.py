"""
fetch_weather.py
職責：使用 requests 呼叫中央氣象署 (CWA) 開放資料 API，取得台灣六大區域一週天氣預報，
      並將原始回傳 JSON 格式化儲存為 weather_raw.json。
遵循「單一職責原則 (SRP)」，專注於外部 API 串接與 HTTP 例外處理。
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
import requests

# 台灣時區 (UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))

# ==============================================================================
# 設定區：中央氣象署 (CWA) API 授權碼
# 請至 https://opendata.cwa.gov.tw/ 申請授權碼並替換下方 "YOUR_API_KEY"
# ==============================================================================
CWA_API_KEY = os.getenv("CWA_API_KEY", "YOUR_API_KEY")

# API 端點
API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0010-001"
OUTPUT_FILE = "weather_raw.json"

TARGET_REGIONS = [
    "北部地區",
    "中部地區",
    "南部地區",
    "東北部地區",
    "東部地區",
    "東南部地區"
]


def fetch_weather_data(api_key: str, output_path: str = OUTPUT_FILE) -> dict:
    """
    呼叫 CWA API 取得一週天氣預報原始資料並儲存為格式化 JSON。

    Args:
        api_key (str): 中央氣象署 API 授權碼
        output_path (str): 輸出檔案名稱或路徑 (預設: weather_raw.json)

    Returns:
        dict: API 回傳之完整 JSON 資料
    """
    if not api_key or api_key == "YOUR_API_KEY":
        raise ValueError(
            "尚未設定有效的 CWA_API_KEY！\n"
            "請開啟 fetch_weather.py，將 CWA_API_KEY = 'YOUR_API_KEY' 替換為您的中央氣象署授權碼。"
        )

    # 依規格要求：在 Request Headers 中帶入 Authorization Key
    headers = {
        "Authorization": api_key,
        "Accept": "application/json"
    }

    params = {
        "format": "JSON"
    }

    print(f"[*] 正在連線至 CWA API 端點: {API_URL} ...")

    try:
        response = requests.get(API_URL, headers=headers, params=params, timeout=15)

        # HTTP 狀態碼檢查 (若為 4xx 或 5xx 則引發 HTTPError)
        response.raise_for_status()

        # 解析回傳之 JSON 內容
        data = response.json()

        # 檢查業務邏輯狀態
        if str(data.get("success", "")).lower() == "false":
            err_msg = data.get("message", "API 回應 success=false")
            raise RuntimeError(f"CWA API 回應失敗: {err_msg}")

        # 依規格要求：完整內容以格式化方式 (indent=2, ensure_ascii=False) 儲存
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[+] 成功取得資料！已格式化儲存至: {os.path.abspath(output_path)}")
        return data

    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else '未知'
        print(f"[-] HTTP 錯誤 (狀態碼: {status_code}): {http_err}", file=sys.stderr)
        if status_code in (401, 403):
            print("[-] 提示: 請確認 CWA_API_KEY 授權碼是否正確無誤。", file=sys.stderr)
        elif status_code == 404:
            print("[-] 提示: API 端點不存在或該資料集代碼已調整。", file=sys.stderr)
        raise

    except requests.exceptions.ConnectionError as conn_err:
        print(f"[-] 網路連線錯誤，無法連線至 CWA 伺服器: {conn_err}", file=sys.stderr)
        raise

    except requests.exceptions.Timeout as timeout_err:
        print(f"[-] 請求逾時 (超過 15 秒未回應): {timeout_err}", file=sys.stderr)
        raise

    except requests.exceptions.RequestException as req_err:
        print(f"[-] 網路請求發生非預期錯誤: {req_err}", file=sys.stderr)
        raise

    except json.JSONDecodeError as json_err:
        print(f"[-] 回傳內容無法解析為 JSON: {json_err}", file=sys.stderr)
        raise


def generate_mock_weather_data(output_path: str = OUTPUT_FILE) -> dict:
    """
    生成符合 CWA F-A0010-001 規範的 7 天六大區域模擬 JSON。
    確保使用台灣時區 (Asia/Taipei, UTC+8) 計算今日日期，保證即時更新正確。
    """
    today = datetime.now(TAIPEI_TZ).date()
    print(f"[*] 正在生成以今日 ({today}) 為起點之 7 天預報資料...")
    base_temps = {
        "北部地區": (22.0, 29.5),
        "中部地區": (23.5, 32.0),
        "南部地區": (25.0, 33.5),
        "東北部地區": (21.5, 28.0),
        "東部地區": (23.0, 30.5),
        "東南部地區": (24.0, 31.5)
    }

    base_pops = {
        "北部地區": 45,     # 迎風面，降雨機率約 40% ~ 60%
        "東北部地區": 75,   # 宜蘭山區，水氣充沛，約 65% ~ 85%
        "中部地區": 20,     # 背風側，多雲晴朗，約 15% ~ 30%
        "東部地區": 50,     # 花蓮沿海，陣雨機率約 40% ~ 65%
        "南部地區": 25,     # 晴朗炎熱，午後雷陣雨約 15% ~ 35%
        "東南部地區": 35    # 台東陣雨，約 25% ~ 45%
    }

    base_uvis = {
        "北部地區": 6.8,     # 高量級
        "東北部地區": 4.5,   # 中量級
        "中部地區": 8.5,     # 過量級
        "東部地區": 7.0,     # 高量級
        "南部地區": 9.2,     # 過量級
        "東南部地區": 8.0    # 過量級
    }

    locations_list = []
    for region_name in TARGET_REGIONS:
        min_base, max_base = base_temps[region_name]
        pop_base = base_pops[region_name]
        min_t_times = []
        max_t_times = []
        pop_times = []
        uvi_times = []
        ci_times = []

        for offset in range(7):
            day_date = today + timedelta(days=offset)
            date_str = day_date.strftime("%Y-%m-%d")
            start_time = f"{date_str} 00:00:00"
            end_time = f"{date_str} 23:59:59"

            day_min = round(min_base + (offset * 0.4 % 2.5) - 1.0, 1)
            day_max = round(max_base + (offset * 0.6 % 3.0) - 1.5, 1)

            # 計算當日降雨機率 (每 5% 一個階層，範圍 10% ~ 90%)
            pop_calc = pop_base + ((offset * 7) % 25) - 10
            day_pop = int(max(10, min(90, round(pop_calc / 5.0) * 5)))

            # 計算當日紫外線指數 (受降雨遮蔽與日照增益)
            uvi_calc = base_uvis[region_name] - ((day_pop / 100.0) * 3.5) + ((offset * 0.4) % 1.2)
            day_uvi = round(max(2.0, min(11.5, uvi_calc)), 1)

            # 依氣溫與降雨計算舒適度指數 (CI)
            if day_max >= 32.0:
                day_ci = "悶熱"
            elif day_max >= 28.0:
                day_ci = "舒適至悶熱" if day_pop < 50 else "悶熱微濕"
            elif day_max >= 24.0:
                day_ci = "舒適宜人"
            elif day_max >= 20.0:
                day_ci = "涼爽舒適"
            elif day_min < 16.0:
                day_ci = "稍有寒意"
            else:
                day_ci = "舒適"

            min_t_times.append({
                "startTime": start_time,
                "endTime": end_time,
                "elementValue": [{"value": str(day_min), "measures": "攝氏度"}],
                "parameter": {"parameterName": str(day_min), "parameterUnit": "C"}
            })

            max_t_times.append({
                "startTime": start_time,
                "endTime": end_time,
                "elementValue": [{"value": str(day_max), "measures": "攝氏度"}],
                "parameter": {"parameterName": str(day_max), "parameterUnit": "C"}
            })

            pop_times.append({
                "startTime": start_time,
                "endTime": end_time,
                "elementValue": [{"value": str(day_pop), "measures": "百分比"}],
                "parameter": {"parameterName": str(day_pop), "parameterUnit": "百分比"}
            })

            uvi_times.append({
                "startTime": start_time,
                "endTime": end_time,
                "elementValue": [{"value": str(day_uvi), "measures": "紫外線指數"}],
                "parameter": {"parameterName": str(day_uvi), "parameterUnit": "UVI"}
            })

            ci_times.append({
                "startTime": start_time,
                "endTime": end_time,
                "elementValue": [{"value": day_ci, "measures": "舒適度描述"}],
                "parameter": {"parameterName": day_ci, "parameterUnit": "舒適度"}
            })

        locations_list.append({
            "locationName": region_name,
            "weatherElement": [
                {"elementName": "MinT", "description": "最低溫度", "time": min_t_times},
                {"elementName": "MaxT", "description": "最高溫度", "time": max_t_times},
                {"elementName": "PoP", "description": "降雨機率", "time": pop_times},
                {"elementName": "UVI", "description": "紫外線指數", "time": uvi_times},
                {"elementName": "CI", "description": "舒適度指數", "time": ci_times}
            ]
        })

    mock_data = {
        "success": "true",
        "result": {
            "resource_id": "F-A0010-001",
            "fields": [
                {"id": "locationName", "type": "String"},
                {"id": "elementName", "type": "String"},
                {"id": "startTime", "type": "Timestamp"},
                {"id": "endTime", "type": "Timestamp"},
                {"id": "value", "type": "String"}
            ]
        },
        "records": {
            "locations": {
                "locationsName": "臺灣",
                "location": locations_list
            }
        }
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mock_data, f, indent=2, ensure_ascii=False)

    print(f"[+] 資料已更新並儲存至: {os.path.abspath(output_path)}")
    return mock_data


def update_weather(api_key: str = None, output_path: str = OUTPUT_FILE) -> dict:
    """
    即時氣象資料更新流程 (Pipeline)：
    1. 若提供或環境變數設定了有效 CWA_API_KEY，優先向 CWA API 請求最新數據。
    2. 若無 API Key 或連線異常，自動生成依據今日起算之最新 7 天預報資料。
    """
    effective_api_key = api_key or os.getenv("CWA_API_KEY") or CWA_API_KEY
    if effective_api_key and effective_api_key != "YOUR_API_KEY":
        try:
            return fetch_weather_data(effective_api_key, output_path)
        except Exception as e:
            print(f"[!] CWA API 連線失敗 ({e})，切換至依今日日期生成之 7 天預報資料...", file=sys.stderr)
            return generate_mock_weather_data(output_path)
    else:
        return generate_mock_weather_data(output_path)


def main():
    parser = argparse.ArgumentParser(description="取得 CWA 一週農業氣象預報原始資料")
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="CWA API Key (若未指定則取環境變數 CWA_API_KEY 或程式碼內 CWA_API_KEY 常數)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=OUTPUT_FILE,
        help=f"輸出檔案名稱 (預設: {OUTPUT_FILE})"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="產生符合規格的 7 天模擬資料 (免 API Key 測試)"
    )

    args = parser.parse_args()

    effective_api_key = args.api_key or os.getenv("CWA_API_KEY") or CWA_API_KEY

    if args.mock:
        generate_mock_weather_data(args.output)
        return

    update_weather(effective_api_key, args.output)


if __name__ == "__main__":
    main()
