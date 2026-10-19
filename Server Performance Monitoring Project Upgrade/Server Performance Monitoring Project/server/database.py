import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
import config

def get_connection(db_path=config.DB_PATH) -> sqlite3.Connection:
    """Tạo kết nối tới SQLite Database với chế độ WAL để tăng tốc ghi và đọc đa luồng."""
    conn = sqlite3.connect(db_path, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path=config.DB_PATH) -> None:
    """Khởi tạo cấu trúc bảng SQLite và các chỉ mục (Indexes) phục vụ truy vấn chuỗi thời gian."""
    conn = get_connection(db_path)
    with conn:
        cursor = conn.cursor()
        
        # 1. Bảng lưu danh mục máy chủ giám sát (Agents)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT UNIQUE NOT NULL,
            hostname TEXT,
            ip_address TEXT,
            os TEXT,
            cpu_cores INTEGER,
            total_ram_gb REAL,
            status TEXT DEFAULT 'ONLINE',
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Bảng lưu log hiệu năng chuỗi thời gian (Performance Logs)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            cpu_usage REAL NOT NULL,
            ram_usage REAL NOT NULL,
            disk_usage REAL NOT NULL,
            net_sent_mb REAL DEFAULT 0.0,
            net_recv_mb REAL DEFAULT 0.0,
            net_sent_speed_mbps REAL DEFAULT 0.0,
            net_recv_speed_mbps REAL DEFAULT 0.0,
            process_count INTEGER DEFAULT 0,
            FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
        );
        """)

        # 3. Bảng lưu các sự kiện bất thường đã phát hiện (Anomalies)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            metric TEXT NOT NULL,
            metric_value REAL NOT NULL,
            threshold_used REAL,
            detection_method TEXT NOT NULL,
            severity TEXT DEFAULT 'WARNING',
            description TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(agent_id) ON DELETE CASCADE
        );
        """)

        # 4. Bảng lưu cấu hình cài đặt lâu dài (Settings Persistence)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Tạo Index cho tối ưu truy vấn chuỗi thời gian theo agent_id và timestamp
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_agent_time ON performance_logs(agent_id, timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_time ON performance_logs(timestamp);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_time ON anomalies(timestamp);")

        # Cài đặt ngưỡng mặc định vào settings nếu chưa có
        cursor.execute("""
        INSERT OR IGNORE INTO settings (key, value) VALUES 
        ('cpu_threshold', ?),
        ('ram_threshold', ?),
        ('disk_threshold', ?),
        ('z_score_threshold', ?),
        ('moving_avg_window', ?);
        """, (
            str(config.CPU_THRESHOLD_PERCENT),
            str(config.RAM_THRESHOLD_PERCENT),
            str(config.DISK_THRESHOLD_PERCENT),
            str(config.Z_SCORE_THRESHOLD),
            str(config.MOVING_AVG_WINDOW)
        ))

        # Tự động di trú cột (Schema Migration) cho CSDL cũ nếu thiếu các cột tốc độ mạng
        cursor.execute("PRAGMA table_info(performance_logs);")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if "net_sent_speed_mbps" not in existing_cols:
            cursor.execute("ALTER TABLE performance_logs ADD COLUMN net_sent_speed_mbps REAL DEFAULT 0.0;")
        if "net_recv_speed_mbps" not in existing_cols:
            cursor.execute("ALTER TABLE performance_logs ADD COLUMN net_recv_speed_mbps REAL DEFAULT 0.0;")

    conn.close()
    # Tự động cập nhật các agent cũ đã mất kết nối sang OFFLINE
    check_and_update_offline_agents(timeout_seconds=0, db_path=db_path)

# ----------------- QUẢN LÝ CẤU HÌNH (SETTINGS) ----------------- #

def get_setting(key: str, default: Any = None, db_path=config.DB_PATH) -> Any:
    """Đọc một tham số cấu hình lưu trong CSDL SQLite."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?;", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return default

def set_setting(key: str, value: Any, db_path=config.DB_PATH) -> None:
    """Lưu vĩnh viễn một tham số cấu hình vào SQLite."""
    conn = get_connection(db_path)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn:
        conn.execute("""
        INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;
        """, (key, str(value), now_str))
    conn.close()

def load_thresholds(db_path=config.DB_PATH) -> Dict[str, float]:
    """Tải toàn bộ các ngưỡng cảnh báo từ SQLite."""
    cpu = float(get_setting("cpu_threshold", config.CPU_THRESHOLD_PERCENT, db_path))
    ram = float(get_setting("ram_threshold", config.RAM_THRESHOLD_PERCENT, db_path))
    disk = float(get_setting("disk_threshold", config.DISK_THRESHOLD_PERCENT, db_path))
    return {"cpu": cpu, "ram": ram, "disk": disk}

def save_thresholds(cpu: float, ram: float, disk: float, db_path=config.DB_PATH) -> None:
    """Lưu lại các ngưỡng cảnh báo vào SQLite."""
    set_setting("cpu_threshold", cpu, db_path)
    set_setting("ram_threshold", ram, db_path)
    set_setting("disk_threshold", disk, db_path)
    config.CPU_THRESHOLD_PERCENT = cpu
    config.RAM_THRESHOLD_PERCENT = ram
    config.DISK_THRESHOLD_PERCENT = disk

# ----------------- QUẢN LÝ AGENT & HEARTBEAT ----------------- #

def upsert_agent(agent_data: Dict[str, Any], db_path=config.DB_PATH) -> None:
    """Cập nhật hoặc thêm mới thông tin Agent, thiết lập trạng thái ONLINE."""
    conn = get_connection(db_path)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn:
        conn.execute("""
        INSERT INTO agents (agent_id, hostname, ip_address, os, cpu_cores, total_ram_gb, status, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, 'ONLINE', ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            hostname=excluded.hostname,
            ip_address=excluded.ip_address,
            os=excluded.os,
            cpu_cores=excluded.cpu_cores,
            total_ram_gb=excluded.total_ram_gb,
            status='ONLINE',
            last_seen=excluded.last_seen;
        """, (
            agent_data.get("agent_id"),
            agent_data.get("hostname", "Unknown"),
            agent_data.get("ip_address", "127.0.0.1"),
            agent_data.get("os", "Unknown"),
            agent_data.get("cpu_cores", 1),
            agent_data.get("total_ram_gb", 0.0),
            now_str,
            now_str
        ))
    conn.close()

def mark_agent_offline(agent_id: str, db_path=config.DB_PATH) -> None:
    """Đánh dấu Agent cụ thể chuyển sang trạng thái OFFLINE khi mất kết nối Socket."""
    conn = get_connection(db_path)
    with conn:
        conn.execute("UPDATE agents SET status = 'OFFLINE' WHERE agent_id = ?;", (agent_id,))
    conn.close()

def check_and_update_offline_agents(timeout_seconds: float = config.HEARTBEAT_TIMEOUT_SEC, db_path=config.DB_PATH) -> int:
    """Quét toàn bộ Agent: Nếu mốc last_seen quá thời gian timeout thì cập nhật sang OFFLINE."""
    conn = get_connection(db_path)
    now = datetime.now()
    updated_count = 0
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT agent_id, last_seen, status FROM agents WHERE status = 'ONLINE';")
        rows = cursor.fetchall()
        for row in rows:
            aid = row["agent_id"]
            last_seen_str = row["last_seen"]
            last_seen_dt = None
            if last_seen_str:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
                    try:
                        last_seen_dt = datetime.strptime(str(last_seen_str).strip(), fmt)
                        break
                    except (ValueError, TypeError):
                        continue
            
            # Nếu không parse được hoặc vượt quá timeout, chuyển sang OFFLINE
            if last_seen_dt is None or (now - last_seen_dt).total_seconds() > timeout_seconds:
                cursor.execute("UPDATE agents SET status = 'OFFLINE' WHERE agent_id = ?;", (aid,))
                updated_count += 1
    conn.close()
    return updated_count

def reset_database(db_path=config.DB_PATH) -> None:
    """Xóa trắng dữ liệu nhật ký và đặt lại trạng thái ban đầu."""
    conn = get_connection(db_path)
    with conn:
        conn.execute("DELETE FROM anomalies;")
        conn.execute("DELETE FROM performance_logs;")
        conn.execute("DELETE FROM agents;")
        conn.execute("VACUUM;")
    conn.close()

def insert_performance_log(log_data: Dict[str, Any], db_path=config.DB_PATH) -> int:
    """Chèn một bản ghi log hiệu năng vào database và cập nhật last_seen của agent."""
    conn = get_connection(db_path)
    timestamp = log_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    agent_id = log_data.get("agent_id")
    with conn:
        cursor = conn.cursor()
        # Đảm bảo Agent đã có bản ghi trong bảng agents để không vi phạm Foreign Key
        cursor.execute("""
        INSERT OR IGNORE INTO agents (agent_id, hostname, status, first_seen, last_seen)
        VALUES (?, ?, 'ONLINE', ?, ?);
        """, (agent_id, agent_id, timestamp, timestamp))

        cursor.execute("""
        INSERT INTO performance_logs 
        (agent_id, timestamp, cpu_usage, ram_usage, disk_usage, net_sent_mb, net_recv_mb, 
         net_sent_speed_mbps, net_recv_speed_mbps, process_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            agent_id,
            timestamp,
            log_data.get("cpu_usage", 0.0),
            log_data.get("ram_usage", 0.0),
            log_data.get("disk_usage", 0.0),
            log_data.get("net_sent_mb", 0.0),
            log_data.get("net_recv_mb", 0.0),
            log_data.get("net_sent_speed_mbps", 0.0),
            log_data.get("net_recv_speed_mbps", 0.0),
            log_data.get("process_count", 0)
        ))
        row_id = cursor.lastrowid
        # Đồng thời cập nhật trạng thái ONLINE và last_seen cho agent
        cursor.execute("UPDATE agents SET status = 'ONLINE', last_seen = ? WHERE agent_id = ?;", (timestamp, agent_id))
    conn.close()
    return row_id

def insert_anomaly(anomaly_data: Dict[str, Any], db_path=config.DB_PATH) -> int:
    """Lưu trữ một sự kiện bất thường đã phát hiện."""
    conn = get_connection(db_path)
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO anomalies 
        (agent_id, timestamp, metric, metric_value, threshold_used, detection_method, severity, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            anomaly_data.get("agent_id"),
            anomaly_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            anomaly_data.get("metric"),
            anomaly_data.get("metric_value"),
            anomaly_data.get("threshold_used"),
            anomaly_data.get("detection_method"),
            anomaly_data.get("severity", "WARNING"),
            anomaly_data.get("description", "")
        ))
        row_id = cursor.lastrowid
    conn.close()
    return row_id

def get_agents(db_path=config.DB_PATH, check_heartbeat=True) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các Agent với trạng thái cập nhật theo heartbeat."""
    if check_heartbeat:
        check_and_update_offline_agents(db_path=db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents ORDER BY status ASC, last_seen DESC;")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_recent_logs(agent_id: Optional[str] = None, limit: int = 100, db_path=config.DB_PATH) -> List[Dict[str, Any]]:
    """Truy vấn các bản ghi log gần nhất phục vụ vẽ biểu đồ và phân tích."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    limit = max(1, min(limit, 1000))
    if agent_id:
        cursor.execute("""
        SELECT * FROM performance_logs 
        WHERE agent_id = ? 
        ORDER BY timestamp DESC LIMIT ?;
        """, (agent_id, limit))
    else:
        cursor.execute("""
        SELECT * FROM performance_logs 
        ORDER BY timestamp DESC LIMIT ?;
        """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return list(reversed(rows))  # Đảo lại theo thứ tự thời gian tăng dần

def get_anomalies(limit: int = 50, db_path=config.DB_PATH) -> List[Dict[str, Any]]:
    """Lấy danh sách các sự kiện bất thường gần đây."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    limit = max(1, min(limit, 500))
    cursor.execute("SELECT * FROM anomalies ORDER BY timestamp DESC LIMIT ?;", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_system_summary(db_path=config.DB_PATH) -> Dict[str, Any]:
    """Tổng hợp số liệu thống kê chung của hệ thống."""
    check_and_update_offline_agents(db_path=db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM agents;")
    total_agents = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM agents WHERE status = 'ONLINE';")
    online_agents = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM performance_logs;")
    total_logs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM anomalies;")
    total_anomalies = cursor.fetchone()[0]

    # Tính trung bình tài nguyên gần nhất
    cursor.execute("""
    SELECT AVG(cpu_usage), AVG(ram_usage), AVG(disk_usage)
    FROM (SELECT cpu_usage, ram_usage, disk_usage FROM performance_logs ORDER BY timestamp DESC LIMIT 50);
    """)
    avg_metrics = cursor.fetchone()
    conn.close()

    return {
        "total_agents": total_agents,
        "online_agents": online_agents,
        "offline_agents": total_agents - online_agents,
        "total_logs": total_logs,
        "total_anomalies": total_anomalies,
        "avg_cpu": round(avg_metrics[0], 2) if avg_metrics and avg_metrics[0] is not None else 0.0,
        "avg_ram": round(avg_metrics[1], 2) if avg_metrics and avg_metrics[1] is not None else 0.0,
        "avg_disk": round(avg_metrics[2], 2) if avg_metrics and avg_metrics[2] is not None else 0.0,
    }

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", config.DB_PATH)
    print("Default thresholds:", load_thresholds())
