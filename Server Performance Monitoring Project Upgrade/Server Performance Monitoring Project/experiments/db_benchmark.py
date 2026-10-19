import sqlite3
import time
import random
import statistics
import sys
from pathlib import Path
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

def benchmark_sqlite_scaling(scales: List[int] = [1000, 5000, 20000, 50000], iterations: int = 3):
    """Thực nghiệm 2: Đánh giá hiệu năng ghi và truy vấn tổng hợp chuỗi thời gian của SQLite (WAL Mode)
    theo quy mô bản ghi tăng dần (lặp lại 3 lượt để tính Mean ± Std).
    """
    random.seed(42)
    test_db = config.DB_DIR / "benchmark_test.db"
    if test_db.exists():
        try:
            test_db.unlink()
        except Exception:
            pass

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("""
    CREATE TABLE benchmark_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT,
        timestamp TEXT,
        cpu_usage REAL,
        ram_usage REAL,
        disk_usage REAL
    );
    """)
    cursor.execute("CREATE INDEX idx_bench_time ON benchmark_logs(agent_id, timestamp);")
    conn.commit()

    print("=" * 80)
    print("THỰC NGHIỆM 2: HIỆU NĂNG GHI & TRUY VẤN CỦA SQLITE THEO QUY MÔ BẢN GHI (WAL MODE)")
    print("Phương pháp: Phân bổ đều 10 node, đo Batch Insert và Aggregation Query (3 lượt chạy)")
    print("=" * 80)
    print(f"{'Quy mô (Rows)':<16}{'Insert Time (s)':<18}{'Throughput (rows/s)':<24}{'Query Time (ms)':<18}")
    print("-" * 80)

    total_inserted = 0
    results = {}

    for count in scales:
        rows_to_insert = count - total_inserted
        # Phân bổ đều cho 10 agent để agent-01 luôn có chính xác 10% dữ liệu
        data = [
            (
                f"agent-{((i % 10) + 1):02d}",
                f"2026-09-19 {(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}",
                round(random.uniform(15.0, 85.0), 2),
                round(random.uniform(30.0, 75.0), 2),
                round(random.uniform(40.0, 60.0), 2)
            )
            for i in range(rows_to_insert)
        ]

        # 1. Ghi dữ liệu
        t0 = time.perf_counter()
        cursor.executemany("""
        INSERT INTO benchmark_logs (agent_id, timestamp, cpu_usage, ram_usage, disk_usage)
        VALUES (?, ?, ?, ?, ?);
        """, data)
        conn.commit()
        t1 = time.perf_counter()
        insert_time = t1 - t0
        throughput = rows_to_insert / max(insert_time, 0.0001)

        # 2. Đo truy vấn phân tích (lặp iterations lần để tính trung bình)
        query_times = []
        for _ in range(iterations):
            t_q0 = time.perf_counter()
            cursor.execute("""
            SELECT AVG(cpu_usage), MAX(ram_usage), MIN(disk_usage), COUNT(*) 
            FROM benchmark_logs 
            WHERE agent_id = 'agent-01';
            """)
            cursor.fetchall()
            t_q1 = time.perf_counter()
            query_times.append((t_q1 - t_q0) * 1000)

        avg_query_ms = statistics.mean(query_times)
        std_query_ms = statistics.stdev(query_times) if len(query_times) > 1 else 0.0

        total_inserted = count
        q_str = f"{avg_query_ms:.2f} ± {std_query_ms:.2f}"
        print(f"{count:<16}{insert_time:<18.4f}{throughput:<24.1f}{q_str:<18}")

        results[count] = {
            "insert_time_sec": insert_time,
            "throughput_rps": throughput,
            "query_time_ms": avg_query_ms
        }

    conn.close()
    if test_db.exists():
        try:
            test_db.unlink()
        except Exception:
            pass

    print("=" * 80)
    return results

if __name__ == "__main__":
    benchmark_sqlite_scaling()
