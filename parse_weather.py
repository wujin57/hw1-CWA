"""
parse_weather.py
職責：讀取 weather_raw.json，走訪 JSON 階層：
      records -> locations -> location[] -> weatherElement[] -> time[]
      提取台灣六大區域（北部地區、中部地區、南部地區、東北部地區、東部地區、東南部地區）
      每日最低氣溫 (MinT) 與最高氣溫 (MaxT)，並封裝為清洗後的 List of Dictionaries。
遵循「單一職責原則 (SRP)」，專注於資料解析、型態轉換與防呆驗證。
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
from collections import defaultdict

# 台灣六大目標提取區域 (維持固定順序)
TARGET_REGIONS = [
    "北部地區",
    "中部地區",
    "南部地區",
    "東北部地區",
    "東部地區",
    "東南部地區"
]

INPUT_FILE = "weather_raw.json"


def _extract_temp_value(time_entry: dict) -> Optional[float]:
    """
    從 CWA time entry 節點中萃取氣溫數值 (REAL/float)。
    支援 elementValue (陣列或物件)、parameter 字典或直接數值等多種常見格式。
    """
    if not isinstance(time_entry, dict):
        return None

    # 1. 檢查 elementValue (常見於現代 CWA REST API)
    if "elementValue" in time_entry:
        ev = time_entry["elementValue"]
        if isinstance(ev, list) and len(ev) > 0 and isinstance(ev[0], dict):
            val = ev[0].get("value") or ev[0].get("MinT") or ev[0].get("MaxT")
            if val is not None and str(val).strip() != "":
                try:
                    return float(val)
                except ValueError:
                    pass
        elif isinstance(ev, dict):
            val = ev.get("value")
            if val is not None and str(val).strip() != "":
                try:
                    return float(val)
                except ValueError:
                    pass

    # 2. 檢查 parameter (常見於 CWB 傳統 API)
    if "parameter" in time_entry:
        param = time_entry["parameter"]
        if isinstance(param, dict):
            val = param.get("parameterName") or param.get("parameterValue")
            if val is not None and str(val).strip() != "":
                try:
                    return float(val)
                except ValueError:
                    pass

    # 3. 檢查直接的 value 欄位
    if "value" in time_entry:
        val = time_entry["value"]
        if val is not None and str(val).strip() != "":
            try:
                return float(val)
            except ValueError:
                pass

    return None


def _extract_date(time_entry: dict) -> Optional[str]:
    """
    從 time entry 節點中擷取預報日期字串 (格式: YYYY-MM-DD)。
    """
    if not isinstance(time_entry, dict):
        return None
    time_str = (
        time_entry.get("startTime")
        or time_entry.get("dataTime")
        or time_entry.get("endTime")
    )
    if time_str and len(time_str) >= 10:
        # 截取前 10 碼即為 YYYY-MM-DD
        return time_str[:10]
    return None


def _get_locations_list(raw_data: dict) -> List[dict]:
    """
    走訪 records 節點，相容多種 CWA locations 階層形式：
    - records -> locations -> location[]
    - records -> locations[] -> location[]
    - records -> location[]
    """
    records = raw_data.get("records")
    if not isinstance(records, dict):
        raise ValueError("JSON 格式不符：找不到 'records' 字典節點。")

    # 階層 1: records -> locations
    locations = records.get("locations")
    if isinstance(locations, dict):
        loc_list = locations.get("location", [])
        if isinstance(loc_list, list):
            return loc_list
    elif isinstance(locations, list) and len(locations) > 0:
        all_locs = []
        for loc_obj in locations:
            if isinstance(loc_obj, dict):
                loc_sub = loc_obj.get("location", [])
                if isinstance(loc_sub, list):
                    all_locs.extend(loc_sub)
                elif "locationName" in loc_obj:
                    all_locs.append(loc_obj)
        if all_locs:
            return all_locs

    # 階層 2: records -> location
    direct_loc = records.get("location")
    if isinstance(direct_loc, list):
        return direct_loc

    raise ValueError("JSON 格式不符：無法定位到 'location' 區域陣列節點。")


def parse_weather_json(json_path: str = INPUT_FILE) -> List[Dict[str, Any]]:
    """
    讀取原始 JSON 檔案並清洗為結構化的氣溫預報清單。

    Args:
        json_path (str): weather_raw.json 檔案路徑

    Returns:
        List[Dict[str, Any]]: 清洗後的資料清單，每筆元素包含：
            - regionName (str): 區域名稱 (TEXT)
            - dataDate (str): 預報日期 (TEXT, YYYY-MM-DD)
            - minT (float): 最低氣溫 (REAL)
            - maxT (float): 最高氣溫 (REAL)
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"找不到檔案: {json_path}！請先執行 fetch_weather.py 取得資料。"
        )

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            raw_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"無法解析 JSON 檔案內容: {e}")

    # 走訪至 location[] 陣列
    location_nodes = _get_locations_list(raw_data)

    # 暫存結構：region_temps[region_name][date]["minT" / "maxT"] = [數值清單...]
    region_temps = defaultdict(lambda: defaultdict(lambda: {"minT": [], "maxT": []}))

    for loc in location_nodes:
        if not isinstance(loc, dict):
            continue

        loc_name = loc.get("locationName", "").strip()

        # 比對是否為六大指定區域之一 (優先完全比對，次之依字串長度由長至短比對，避免「東北部地區」誤匹配「北部地區」)
        matched_region = None
        if loc_name in TARGET_REGIONS:
            matched_region = loc_name
        else:
            for target in sorted(TARGET_REGIONS, key=len, reverse=True):
                if target in loc_name:
                    matched_region = target
                    break

        if not matched_region:
            continue

        # 走訪 weatherElement[]
        weather_elements = loc.get("weatherElement", [])
        if not isinstance(weather_elements, list):
            continue

        for elem in weather_elements:
            if not isinstance(elem, dict):
                continue

            elem_name = elem.get("elementName", "").strip()
            # 走訪 time[]
            time_list = elem.get("time", [])
            if not isinstance(time_list, list):
                continue

            if elem_name in ("MinT", "最低氣溫", "最低溫度"):
                for t in time_list:
                    d = _extract_date(t)
                    v = _extract_temp_value(t)
                    if d and v is not None:
                        region_temps[matched_region][d]["minT"].append(v)

            elif elem_name in ("MaxT", "最高氣溫", "最高溫度"):
                for t in time_list:
                    d = _extract_date(t)
                    v = _extract_temp_value(t)
                    if d and v is not None:
                        region_temps[matched_region][d]["maxT"].append(v)

    # 組合並整理成結構化的 List of Dictionaries
    cleaned_records: List[Dict[str, Any]] = []

    # 依六大區域順序輸出
    for region_name in TARGET_REGIONS:
        if region_name not in region_temps:
            print(f"[!] 警告: 資料中未發現區域: {region_name}", file=sys.stderr)
            continue

        dates = sorted(region_temps[region_name].keys())
        for d in dates:
            min_vals = region_temps[region_name][d]["minT"]
            max_vals = region_temps[region_name][d]["maxT"]

            if not min_vals and not max_vals:
                continue

            # 計算當日真正的最低與最高溫 (防範早晚分段預報)
            day_min = min(min_vals) if min_vals else (max(max_vals) if max_vals else 0.0)
            day_max = max(max_vals) if max_vals else (min(min_vals) if min_vals else 0.0)

            # 防呆校正：若出現 max < min
            if day_max < day_min:
                day_min, day_max = day_max, day_min

            record = {
                "regionName": str(region_name),
                "dataDate": str(d),
                "minT": float(round(day_min, 1)),
                "maxT": float(round(day_max, 1))
            }
            cleaned_records.append(record)

    return cleaned_records


def main():
    parser = argparse.ArgumentParser(description="分析 weather_raw.json 提取六大區域每日最低/最高氣溫")
    parser.add_argument(
        "--input",
        type=str,
        default=INPUT_FILE,
        help=f"輸入原始 JSON 檔案路徑 (預設: {INPUT_FILE})"
    )
    args = parser.parse_args()

    print(f"[*] 正在分析天氣預報資料: {args.input} ...")
    try:
        results = parse_weather_json(args.input)
        print(f"[+] 資料解析成功！共萃取出 {len(results)} 筆氣溫預報紀錄。\n")

        # 輸出預覽表格
        print(f"{'區域 (regionName)':<14} | {'日期 (dataDate)':<12} | {'最低溫 (minT)':<12} | {'最高溫 (maxT)':<12}")
        print("-" * 60)
        for row in results[:14]:  # 預覽前 14 筆
            print(f"{row['regionName']:<14} | {row['dataDate']:<12} | {row['minT']:<12.1f}°C | {row['maxT']:<12.1f}°C")
        if len(results) > 14:
            print(f"... 還有 {len(results) - 14} 筆資料 (共涵蓋 {len(set(r['regionName'] for r in results))} 個區域)")

    except Exception as e:
        print(f"[-] 解析過程發生錯誤: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
