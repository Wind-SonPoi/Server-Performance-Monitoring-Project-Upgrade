import sys

# Cấu hình UTF-8 an toàn cho console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import time
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
import config

def run_server():
    """Chạy độc lập TCP Socket Server."""
    from server.socket_server import SocketServerManager
    srv = SocketServerManager()
    if srv.start():
        print(f"TCP Socket Server đã khởi động thành công trên {srv.host}:{srv.port}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nĐang dừng TCP Socket Server...")
        srv.stop()

def run_client(agent_id="srv-node-01"):
    """Chạy độc lập Client Agent thu thập máy thật."""
    from client.agent import MonitoringAgent
    agent = MonitoringAgent(agent_id=agent_id, host=config.SERVER_HOST, port=config.SERVER_PORT)
    agent.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nĐang dừng Client Agent...")
        agent.stop()

def run_web():
    """Chạy độc lập Flask Web Dashboard."""
    from flask_app.app import run_flask_app
    print(f"Khởi động Web Dashboard tại http://127.0.0.1:{config.FLASK_PORT}")
    print(f"Địa chỉ mạng LAN: http://{config.get_local_ip()}:{config.FLASK_PORT}")
    run_flask_app()

def run_admin():
    """Chạy Desktop GUI Tkinter Admin Panel."""
    from tkinter_app.admin_panel import run_tkinter_app
    run_tkinter_app()

def run_experiments():
    """Chạy bộ 3 thực nghiệm đối chuẩn phục vụ báo cáo khoa học."""
    print("\n" + "=" * 75)
    print(" BẮT ĐẦU CHẠY BỘ THỰC NGHIỆM KHOA HỌC PHỤC VỤ BÁO CÁO BẢO VỆ")
    print("=" * 75 + "\n")

    # 1. Khởi động nhanh server ngầm phục vụ đo RTT Latency
    from server.socket_server import SocketServerManager
    srv = SocketServerManager()
    srv.start()
    time.sleep(1.2)

    try:
        # Thí nghiệm 1: Socket RTT Latency
        from experiments.latency_test import run_concurrency_experiment
        run_concurrency_experiment([1, 5, 10, 20])
    finally:
        srv.stop()

    print("\n")
    # Thí nghiệm 2: SQLite Scalability (1.000 -> 50.000 rows)
    from experiments.db_benchmark import benchmark_sqlite_scaling
    benchmark_sqlite_scaling([1000, 5000, 20000, 50000])

    print("\n")
    # Thí nghiệm 3: Anomaly Detection Benchmarking (Multi-seed & Ground Truth)
    from experiments.anomaly_eval import run_anomaly_evaluation
    run_anomaly_evaluation()

    print("\n" + "=" * 75)
    print(" HOÀN THÀNH TOÀN BỘ CÁC THỰC NGHIỆM! CÁC BIỂU ĐỒ ĐÃ ĐƯỢC LƯU TẠI /reports")
    print("=" * 75 + "\n")

def run_all():
    """Khởi động toàn diện: Socket Server + Flask Web + Client Agent + Tkinter GUI."""
    print("\n" + "=" * 75)
    print(" HỆ THỐNG GIÁM SÁT HIỆU NĂNG MÁY CHỦ PHÂN TÁN (KHỞI ĐỘNG ĐẦY ĐỦ)")
    print("=" * 75)

    # 1. Khởi động TCP Socket Server
    from server.socket_server import SocketServerManager
    server_mgr = SocketServerManager(host=config.SOCKET_HOST, port=config.SOCKET_PORT)
    if server_mgr.start():
        print(f"-> [1/4] TCP Socket Server đã khởi động tại: {server_mgr.host}:{server_mgr.port}")
    else:
        print("-> [1/4] Cảnh báo: Không thể khởi động TCP Server.")

    time.sleep(1.0)

    # 2. Khởi động Flask Web Dashboard trên luồng phụ
    def run_web_worker():
        from flask_app.app import run_flask_app
        run_flask_app()

    web_thread = threading.Thread(target=run_web_worker, name="Flask-Web", daemon=True)
    web_thread.start()
    local_ip = config.get_local_ip()
    print(f"-> [2/4] Flask Web Dashboard sẵn sàng tại: http://127.0.0.1:{config.FLASK_PORT}")
    print(f"        (Địa chỉ truy cập mạng LAN: http://{local_ip}:{config.FLASK_PORT})")

    # 3. Khởi động Client Agent thu thập máy thật trên luồng phụ
    def run_client_worker():
        time.sleep(1.5)
        from client.agent import MonitoringAgent
        # Client kết nối tới local server
        client = MonitoringAgent(agent_id="local-host-agent", host="127.0.0.1", port=config.SOCKET_PORT)
        client.start()

    client_thread = threading.Thread(target=run_client_worker, name="Client-Worker", daemon=True)
    client_thread.start()
    print(f"-> [3/4] Client Agent [local-host-agent] đã kích hoạt và đang gửi dữ liệu.")

    # 4. Mở Tkinter Admin GUI ở luồng chính (Tkinter yêu cầu Main Thread trên Windows)
    print("-> [4/4] Đang mở Bảng điều khiển Desktop Tkinter Admin Panel...")
    print("=" * 75)
    print("Tip: Bấm Ctrl+C hoặc đóng cửa sổ Tkinter để tắt toàn bộ hệ thống.\n")

    try:
        from tkinter_app.admin_panel import run_tkinter_app
        run_tkinter_app(server_manager=server_mgr)
    except Exception as e:
        print(f"Lỗi Desktop GUI Tkinter: {e}")
    finally:
        print("\nĐang dừng các dịch vụ Socket Server...")
        server_mgr.stop()
        print("Hệ thống đã dừng an toàn.")

def main():
    if len(sys.argv) < 2:
        print("""
========================================================================
HỆ THỐNG GIÁM SÁT VÀ PHÂN TÍCH HIỆU NĂNG MÁY CHỦ PHÂN TÁN (PYTHON)
========================================================================
Cách sử dụng:
  python run_system.py all          : Khởi động Server + Web + Client + Tkinter (Khuyên dùng)
  python run_system.py server       : Chạy TCP Socket Server
  python run_system.py client [ID]  : Chạy Client Agent (mặc định: srv-node-01)
  python run_system.py web          : Chạy Flask Web Dashboard (http://127.0.0.1:5000)
  python run_system.py admin        : Mở Bảng điều khiển Desktop GUI Tkinter
  python run_system.py experiments  : Chạy toàn bộ các kịch bản thực nghiệm đo đạc
========================================================================
        """)
        return

    mode = sys.argv[1].lower()

    if mode == "server":
        run_server()
    elif mode == "client":
        aid = sys.argv[2] if len(sys.argv) > 2 else "srv-node-01"
        run_client(aid)
    elif mode == "web":
        run_web()
    elif mode == "admin":
        run_admin()
    elif mode == "experiments":
        run_experiments()
    elif mode == "all":
        run_all()
    else:
        print(f"Tham số không hợp lệ: '{mode}'. Hãy chạy 'python run_system.py' để xem hướng dẫn.")

if __name__ == "__main__":
    main()
