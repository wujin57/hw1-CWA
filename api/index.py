"""
api/index.py
Vercel Serverless Function 入口點。
將所有 HTTP 請求導入 app.py 的 Flask 實例。
"""

import os
import sys

# 將專案根目錄加入模組搜尋路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app

# Vercel 尋找名為 app 的 WSGI callable
