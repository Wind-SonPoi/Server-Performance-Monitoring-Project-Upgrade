import socket
import json
import time
import threading
import sys
from typing import Optional
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo import được config khi chạy độc lập
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from client.collector import SystemMetricsCollector

class MonitoringAgent:
    """TCP Socket Client gửi dữ liệu hiệu năng hệ thống định kỳ về Central Server."""

    def __init__(self, agent_id: str = config.DEFAULT_AGENT_ID, 
                 host: str = config.SERVER_HOST, 
                 port: int = config.SERVER_PORT, 
                 interval: float = config.DEFAULT_SAMPLE_INTERVAL):
        self.agent_id = agent_id
        self.host = host
        self.port = port
        self.interval = interval
        self.collector = SystemMetricsCollector(agent_id=self.agent_id)
        self.running = False
        self.sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    def connect(self) -> bool:
        """Thiết lập kết nối TCP Socket tới Server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, self.port))
            print(f"[{self.agent_id}] Kết nối thành công tới Server {self.host}:{self.port}")
            
            # Gửi thông điệp đăng ký ban đầu (Profile)
            profile = self.collector.get_agent_profile()
            register_msg = {
                "type": "REGISTER",
                "data": profile
            }
            self._send_payload(register_msg)
            return True
        except Exception as e:
            print(f"[{self.agent_id}] Không thể kết nối tới Server {self.host}:{self.port} - Lỗi: {e}")
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            return False

    def _send_payload(self, payload: dict) -> bool:
        """Đóng gói dữ liệu dạng JSON với ký tự kết dòng \\n và truyền qua Socket kèm nhận ACK."""
        if not self.sock:
            return False
        try:
            raw_msg = (json.dumps(payload) + "\n").encode("utf-8")
            self.sock.sendall(raw_msg)
            # Nhận gói tin xác nhận ACK từ Server để xác nhận hoàn tất Round-Trip
            self.sock.settimeout(3.0)
            ack_raw = self.sock.recv(1024)
            if not ack_raw:
                return False
            return True
        except Exception as e:
            print(f"[{self.agent_id}] Lỗi truyền/nhận dữ liệu qua Socket: {e}")
            return False

    def start(self) -> None:
        """Khởi động luồng thu thập và gửi dữ liệu định kỳ."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        """Vòng lặp chạy ngầm tự động gửi dữ liệu và khôi phục kết nối (Reconnection)."""
        while self.running:
            if not self.sock:
                print(f"[{self.agent_id}] Đang thử kết nối lại tới Server sau 3 giây...")
                time.sleep(3.0)
                if not self.connect():
                    continue

            # Thu thập chỉ số
            metrics = self.collector.collect_metrics()
            msg = {
                "type": "METRICS",
                "data": metrics
            }
            success = self._send_payload(msg)
            if not success:
                # Mất kết nối, dọn dẹp để kết nối lại
                if self.sock:
                    try:
                        self.sock.close()
                    except Exception:
                        pass
                    self.sock = None

            time.sleep(self.interval)

    def stop(self) -> None:
        """Dừng Agent an toàn."""
        self.running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        print(f"[{self.agent_id}] Agent đã dừng.")

if __name__ == "__main__":
    agent_id = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_AGENT_ID
    agent = MonitoringAgent(agent_id=agent_id)
    agent.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()
