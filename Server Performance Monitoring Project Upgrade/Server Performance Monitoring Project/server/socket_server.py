import socket
import threading
import json
import time
import sys
import logging
from typing import Optional, Dict, Any
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
from server.database import (
    init_db, upsert_agent, insert_performance_log, insert_anomaly, 
    mark_agent_offline, check_and_update_offline_agents, load_thresholds
)

# Thiết lập hệ thống ghi log chuyên nghiệp (File + Console)
log_file = config.LOGS_DIR / "server.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SocketServer")

class SocketServerManager:
    """TCP Socket Server đa luồng tiếp nhận luồng dữ liệu phân tán và phản hồi ACK."""

    def __init__(self, host: str = config.SOCKET_HOST, port: int = config.SOCKET_PORT):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self._main_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self.active_connections = 0
        self.total_packets_received = 0
        self.lock = threading.Lock()
        
        # Đảm bảo database đã được tạo và nạp ngưỡng từ CSDL
        init_db()
        thresholds = load_thresholds()
        self.cpu_threshold = thresholds["cpu"]
        self.ram_threshold = thresholds["ram"]
        self.disk_threshold = thresholds["disk"]

    def refresh_thresholds(self) -> Dict[str, float]:
        """Tải lại các ngưỡng cảnh báo mới nhất từ SQLite CSDL."""
        thresholds = load_thresholds()
        self.cpu_threshold = thresholds["cpu"]
        self.ram_threshold = thresholds["ram"]
        self.disk_threshold = thresholds["disk"]
        return thresholds

    def start(self) -> bool:
        """Khởi động TCP Server trên một luồng riêng biệt."""
        if self.running:
            return True
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(50)
            self.server_socket.settimeout(1.0)
            self.running = True

            self._main_thread = threading.Thread(target=self._listen_loop, name="Server-Acceptor", daemon=True)
            self._main_thread.start()

            # Khởi động luồng kiểm tra Heartbeat quét máy OFFLINE
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_checker_loop, name="Heartbeat-Monitor", daemon=True)
            self._heartbeat_thread.start()

            logger.info("TCP Socket Server đang lắng nghe tại %s:%s (Hỗ trợ LAN/Multi-interface)", self.host, self.port)
            return True
        except Exception as e:
            logger.error("Không thể khởi động TCP Server: %s", e)
            self.running = False
            if self.server_socket:
                try:
                    self.server_socket.close()
                except Exception:
                    pass
                self.server_socket = None
            return False

    def _listen_loop(self) -> None:
        """Vòng lặp chấp nhận kết nối từ các Client Agent."""
        while self.running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                with self.lock:
                    self.active_connections += 1
                logger.info("Chấp nhận kết nối mới từ: %s", client_addr)
                client_handler = threading.Thread(
                    target=self._handle_client, 
                    args=(client_sock, client_addr), 
                    name=f"Client-{client_addr[1]}",
                    daemon=True
                )
                client_handler.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error("Lỗi tiếp nhận kết nối Socket: %s", e)
                break

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple) -> None:
        """Xử lý luồng dữ liệu truyền nhận từ một Client cụ thể với cơ chế phản hồi ACK."""
        client_sock.settimeout(15.0)
        buffer = ""
        agent_id = None

        try:
            while self.running:
                data = client_sock.recv(config.SOCKET_BUFFER_SIZE)
                if not data:
                    break
                
                buffer += data.decode("utf-8", errors="ignore")
                
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        payload = json.loads(line)
                        with self.lock:
                            self.total_packets_received += 1
                        
                        agent_id, msg_type = self._process_payload(payload, client_addr[0])

                        # Gửi phản hồi ACK (Round-Trip Time ACK Confirmation)
                        ack_msg = {
                            "type": "ACK",
                            "status": "OK",
                            "ref_type": msg_type,
                            "timestamp": time.time()
                        }
                        ack_bytes = (json.dumps(ack_msg) + "\n").encode("utf-8")
                        client_sock.sendall(ack_bytes)

                    except json.JSONDecodeError as err:
                        logger.warning("Lỗi cú pháp JSON từ %s: %s", client_addr, err)
        except (socket.timeout, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.debug("Lỗi kết nối client %s: %s", client_addr, e)
        finally:
            with self.lock:
                self.active_connections = max(0, self.active_connections - 1)
            
            # Cập nhật ngay trạng thái OFFLINE nếu Agent bị ngắt kết nối
            if agent_id:
                logger.info("Agent [%s] từ %s đã ngắt kết nối -> Đánh dấu OFFLINE", agent_id, client_addr)
                mark_agent_offline(agent_id)

            try:
                client_sock.close()
            except Exception:
                pass

    def _process_payload(self, payload: Dict[str, Any], client_ip: str) -> tuple:
        """Phân loại và xử lý nội dung gói tin từ Client."""
        msg_type = payload.get("type")
        data = payload.get("data", {})
        agent_id = data.get("agent_id", "unknown")

        if msg_type == "REGISTER":
            data["ip_address"] = client_ip
            upsert_agent(data)
            logger.info("Đã đăng ký máy chủ: %s (%s) từ IP %s", agent_id, data.get("hostname"), client_ip)

        elif msg_type == "METRICS":
            insert_performance_log(data)

            cpu = data.get("cpu_usage", 0.0)
            ram = data.get("ram_usage", 0.0)
            disk = data.get("disk_usage", 0.0)
            timestamp = data.get("timestamp")

            if cpu > self.cpu_threshold:
                insert_anomaly({
                    "agent_id": agent_id,
                    "timestamp": timestamp,
                    "metric": "CPU",
                    "metric_value": cpu,
                    "threshold_used": self.cpu_threshold,
                    "detection_method": "REALTIME_THRESHOLD",
                    "severity": "CRITICAL" if cpu > 95.0 else "WARNING",
                    "description": f"Sử dụng CPU vượt ngưỡng an toàn: {cpu}% > {self.cpu_threshold}%"
                })

            if ram > self.ram_threshold:
                insert_anomaly({
                    "agent_id": agent_id,
                    "timestamp": timestamp,
                    "metric": "RAM",
                    "metric_value": ram,
                    "threshold_used": self.ram_threshold,
                    "detection_method": "REALTIME_THRESHOLD",
                    "severity": "CRITICAL" if ram > 95.0 else "WARNING",
                    "description": f"Chiếm dụng bộ nhớ RAM vượt ngưỡng: {ram}% > {self.ram_threshold}%"
                })

            if disk > self.disk_threshold:
                insert_anomaly({
                    "agent_id": agent_id,
                    "timestamp": timestamp,
                    "metric": "DISK",
                    "metric_value": disk,
                    "threshold_used": self.disk_threshold,
                    "detection_method": "REALTIME_THRESHOLD",
                    "severity": "WARNING",
                    "description": f"Dung lượng ổ đĩa sắp đầy: {disk}% > {self.disk_threshold}%"
                })

        return agent_id, msg_type

    def _heartbeat_checker_loop(self) -> None:
        """Quét định kỳ mỗi 5s để phát hiện và chuyển đổi trạng thái OFFLINE cho các agent im lặng."""
        while self.running:
            time.sleep(5.0)
            try:
                check_and_update_offline_agents()
            except Exception as e:
                logger.debug("Lỗi heartbeat checker: %s", e)

    def stop(self) -> None:
        """Dừng Server Socket."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
            self.server_socket = None
        if self._main_thread and self._main_thread.is_alive():
            self._main_thread.join(timeout=1.0)
        logger.info("TCP Socket Server đã tắt an toàn.")

if __name__ == "__main__":
    server = SocketServerManager()
    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
