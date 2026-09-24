"""
database.py
職責：負責 SQLite 資料庫 (data.db) 的建立與管理，
      包含建立 TemperatureForecasts 資料表、批次寫入氣溫預報資料以及提供查詢介面。
遵循「單一職責原則 (SRP)」，專注於持久層 (Persistence Layer) 的資料庫操作與完整性維護。
"""

import os
import sys
import sqlite3
import argparse
from typing import List, Dict, Any, Optional

DB_FILE = "data.db"
TABLE_NAME = "TemperatureForecasts"

# 資料表 DDL (完全符合規格要求)
CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regionName TEXT,
    dataDate TEXT,
    minT REAL,
    maxT REAL,
    pop REAL DEFAULT 0,
    uvi REAL DEFAULT 5.0,
    ci TEXT DEFAULT '舒適'
);
"""

# 建立唯一性索引 (避免重複執行時同一區域與日期的數據重複插入)
CREATE_INDEX_SQL = f"""
CREATE UNIQUE INDEX IF NOT EXISTS idx_region_date ON {TABLE_NAME}(regionName, dataDate);
"""


def get_connection(db_path: str = DB_FILE) -> sqlite3.Connection:
    """
    建立並取得 SQLite 資料庫連線，並設定 row_factory 為 sqlite3.Row 便於字典化存取。
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_FILE) -> None:
    """
    初始化 SQLite 資料庫與 TemperatureForecasts 資料表。

    Args:
        db_path (str): 資料庫檔案路徑 (預設為 data.db)
    """
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(CREATE_INDEX_SQL)
            # 確保舊資料表具備 pop, uvi, ci 欄位 (向下相容自動遷移)
            cursor.execute(f"PRAGMA table_info({TABLE_NAME});")
            cols = [row["name"] for row in cursor.fetchall()]
            if "pop" not in cols:
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN pop REAL DEFAULT 0;")
            if "uvi" not in cols:
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN uvi REAL DEFAULT 5.0;")
            if "ci" not in cols:
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN ci TEXT DEFAULT '舒適';")
            conn.commit()
            print(f"[+] 資料庫初始化成功: {os.path.abspath(db_path)} (資料表: {TABLE_NAME})")
    except sqlite3.Error as e:
        print(f"[-] 資料庫初始化失敗: {e}", file=sys.stderr)
        raise


def save_forecasts(
    forecasts: List[Dict[str, Any]],
    db_path: str = DB_FILE,
    clear_existing: bool = True
) -> int:
    """
    將清洗後的氣溫、降雨、紫外線指數與舒適度資料存入 SQLite 資料庫中。
    使用批次操作 (executemany) 與 INSERT OR REPLACE 兼顧效能與防重入。

    Args:
        forecasts (List[Dict[str, Any]]): 氣象預報清單，每筆包含 regionName, dataDate, minT, maxT, pop, uvi, ci
        db_path (str): SQLite 資料庫路徑
        clear_existing (bool): 是否先清空既有紀錄

    Returns:
        int: 成功寫入或更新的總筆數
    """
    if not forecasts:
        print("[!] 警告: 傳入之氣象資料清單為空，未執行任何寫入。")
        return 0

    # 確保資料表已建立
    init_db(db_path)

    insert_sql = f"""
    INSERT OR REPLACE INTO {TABLE_NAME} (regionName, dataDate, minT, maxT, pop, uvi, ci)
    VALUES (?, ?, ?, ?, ?, ?, ?);
    """

    data_tuples = [
        (
            item["regionName"],
            item["dataDate"],
            float(item["minT"]),
            float(item["maxT"]),
            float(item.get("pop", 0.0)),
            float(item.get("uvi", 5.0)),
            str(item.get("ci", "舒適"))
        )
        for item in forecasts
    ]

    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            if clear_existing:
                cursor.execute(f"DELETE FROM {TABLE_NAME};")
                print(f"[*] 已清空 {TABLE_NAME} 原有資料。")

            cursor.executemany(insert_sql, data_tuples)
            conn.commit()
            total_saved = len(data_tuples)
            print(f"[+] 成功寫入/更新 {total_saved} 筆氣象預報資料至 {db_path}。")
            return total_saved

    except sqlite3.Error as e:
        print(f"[-] 資料存入 SQLite 失敗: {e}", file=sys.stderr)
        raise


def query_forecasts(
    db_path: str = DB_FILE,
    region: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    自 SQLite 資料庫查詢氣溫、降雨、紫外線指數與舒適度預報紀錄。

    Args:
        db_path (str): SQLite 資料庫路徑
        region (str, optional): 篩選指定區域
        start_date (str, optional): 起始日期 (YYYY-MM-DD)
        end_date (str, optional): 結束日期 (YYYY-MM-DD)

    Returns:
        List[Dict[str, Any]]: 查詢到的氣象預報紀錄字典清單
    """
    if not os.path.exists(db_path):
        return []

    conditions = []
    params = []

    if region:
        conditions.append("regionName = ?")
        params.append(region)
    if start_date:
        conditions.append("dataDate >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("dataDate <= ?")
        params.append(end_date)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
    SELECT id, regionName, dataDate, minT, maxT,
           COALESCE(pop, 0) AS pop,
           COALESCE(uvi, 5.0) AS uvi,
           COALESCE(ci, '舒適') AS ci
    FROM {TABLE_NAME}
    {where_clause}
    ORDER BY regionName ASC, dataDate ASC;
    """

    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[-] 查詢 SQLite 失敗: {e}", file=sys.stderr)
        return []


def main():
    parser = argparse.ArgumentParser(description="將清洗後氣象資料存入 SQLite (data.db)")
    parser.add_argument(
        "--db",
        type=str,
        default=DB_FILE,
        help=f"SQLite 資料庫檔案路徑 (預設: {DB_FILE})"
    )
    parser.add_argument(
        "--json-input",
        type=str,
        default="weather_raw.json",
        help="輸入之原始 JSON 檔案路徑 (預設: weather_raw.json)"
    )

    args = parser.parse_args()

    # 自動引入 parse_weather 模組進行解析與存入
    from parse_weather import parse_weather_json

    if not os.path.exists(args.json_input):
        print(f"[-] 找不到輸入檔案: {args.json_input}！請先執行 fetch_weather.py。", file=sys.stderr)
        sys.exit(1)

    print(f"[*] 正在從 {args.json_input} 解析資料並存入資料庫: {args.db} ...")
    records = parse_weather_json(args.json_input)
    save_forecasts(records, db_path=args.db)

    # 執行投影片要求的兩大驗證查詢
    print("=" * 62)
    print("【驗證查詢 1】列出所有地區名稱 (SELECT DISTINCT regionName FROM TemperatureForecasts;)")
    with get_connection(args.db) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT regionName FROM {TABLE_NAME};")
        distinct_regions = [row["regionName"] for row in cursor.fetchall()]
        print("  -> 地區名稱:", ", ".join(distinct_regions))

    print("\n【驗證查詢 2】查詢中部地區資料 (SELECT * FROM TemperatureForecasts WHERE regionName = '中部地區';)")
    with get_connection(args.db) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE regionName = '中部地區' ORDER BY dataDate ASC;")
        central_rows = cursor.fetchall()
        print(f"  -> 共 {len(central_rows)} 筆預報:")
        for r in central_rows:
            pop_val = r["pop"] if "pop" in r.keys() else 0
            uvi_val = r["uvi"] if "uvi" in r.keys() else 5.0
            ci_val = r["ci"] if "ci" in r.keys() else "舒適"
            print(f"     日期: {r['dataDate']} | 氣溫: {r['minT']:<4.1f}~{r['maxT']:<4.1f}°C | 降雨: {pop_val:<2.0f}% | 紫外線: {uvi_val:<4.1f} | 體感: {ci_val}")
    print("=" * 62)


if __name__ == "__main__":
    main()
