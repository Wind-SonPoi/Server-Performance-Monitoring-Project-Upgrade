import os
import socket
from pathlib import Path

# Thư mục gốc dự án
BASE_DIR = Path(__file__).resolve().parent

# Thư mục lưu trữ CSDL và báo cáo
DB_DIR = BASE_DIR / "database"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "monitoring.db"

REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

def get_local_ip() -> str:
    """Tự động phát hiện địa chỉ IP LAN của máy tính hiện tại."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Kết nối tạm thời tới một IP công khai không cần truyền dữ liệu để xác định default interface IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Cấu hình Mạng TCP Socket
# 0.0.0.0 cho phép Server lắng nghe trên tất cả các card mạng (Wi-Fi, Ethernet, LAN)
SOCKET_HOST = os.getenv("SOCKET_HOST", "0.0.0.0")
SOCKET_PORT = int(os.getenv("SOCKET_PORT", "9999"))
SOCKET_BUFFER_SIZE = 4096

# Cấu hình phía Client kết nối tới Server
# Trong cùng máy thì dùng 127.0.0.1, khi chạy máy khác trong LAN thì dùng IP của Server
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = SOCKET_PORT

# Cấu hình Web Dashboard Flask
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = False

# Cấu hình Client Agent
DEFAULT_AGENT_ID = "srv-local-01"
DEFAULT_SAMPLE_INTERVAL = 3.0  # Chu kỳ gửi tin (giây)
HEARTBEAT_TIMEOUT_SEC = 10.0   # Quá 10s không có log -> Coi như OFFLINE

# Cấu hình Ngưỡng Phát hiện Bất thường Mặc định (Có thể lưu đè vào CSDL)
CPU_THRESHOLD_PERCENT = 85.0     # Cảnh báo CPU vượt ngưỡng (%)
RAM_THRESHOLD_PERCENT = 85.0     # Cảnh báo RAM vượt ngưỡng (%)
DISK_THRESHOLD_PERCENT = 90.0    # Cảnh báo Disk vượt ngưỡng (%)
Z_SCORE_THRESHOLD = 2.5          # Độ lệch chuẩn Z-Score để coi là bất thường
MOVING_AVG_WINDOW = 5            # Cửa sổ trượt k mẫu
SPIKE_DELTA_PERCENT = 25.0       # Tăng vọt tức thời so với Moving Average (%)
