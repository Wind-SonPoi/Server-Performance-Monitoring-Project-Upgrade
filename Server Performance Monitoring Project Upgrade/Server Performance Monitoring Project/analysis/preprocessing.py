import sqlite3
from typing import Optional
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def load_logs_dataframe(agent_id: Optional[str] = None, 
                        limit: Optional[int] = None, 
                        db_path=config.DB_PATH):
    """Trích xuất dữ liệu nhật ký hiệu năng từ SQLite sang Pandas DataFrame."""
    if not PANDAS_AVAILABLE:
        raise ImportError("Thư viện pandas chưa được cài đặt.")

    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM performance_logs"
    params = []

    if agent_id:
        query += " WHERE agent_id = ?"
        params.append(agent_id)

    query += " ORDER BY timestamp ASC"

    if limit:
        query += f" LIMIT {limit}"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return clean_performance_data(df)

def clean_performance_data(df):
    """Tiền xử lý và làm sạch dữ liệu chuỗi thời gian (Data Cleaning)."""
    if df.empty:
        return df

    # 1. Chuyển đổi timestamp sang định dạng Datetime chuẩn
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 2. Xử lý giá trị trùng lặp (Duplicates)
    df = df.drop_duplicates(subset=["agent_id", "timestamp"]).copy()

    # 3. Lọc bỏ các giá trị dị biệt/bất thường do lỗi cảm biến hoặc phần cứng (Invalid Ranges)
    # CPU, RAM, Disk phải nằm trong khoảng [0, 100]%
    valid_mask = (
        (df["cpu_usage"] >= 0.0) & (df["cpu_usage"] <= 100.0) &
        (df["ram_usage"] >= 0.0) & (df["ram_usage"] <= 100.0) &
        (df["disk_usage"] >= 0.0) & (df["disk_usage"] <= 100.0) &
        (df["net_sent_mb"] >= 0.0) & (df["net_recv_mb"] >= 0.0) &
        (df["process_count"] >= 0)
    )
    df = df[valid_mask].copy()

    # 4. Sắp xếp lại theo chuỗi thời gian
    df = df.sort_values(by=["agent_id", "timestamp"]).reset_index(drop=True)

    return df
