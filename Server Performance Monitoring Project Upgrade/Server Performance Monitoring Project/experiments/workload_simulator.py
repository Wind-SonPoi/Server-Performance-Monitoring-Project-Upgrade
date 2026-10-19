import socket
import json
import time
import random
import threading
import sys
from datetime import datetime
from pathlib import Path
from typing import List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

class SimulatedAgent:
    """Agent giả lập chạy đa luồng để kiểm thử chịu tải và tiêm lỗi (Fault Injection)."""

    def __init__(self, agent_id: str, host: str = config.SERVER_HOST, port: int = config.SERVER_PORT):
        self.agent_id = agent_id
        self.host = "127.0.0.1" if host == "0.0.0.0" else host
        self.port = port
        self.running = False
        self.sock = None

    def start(self, duration_sec: int = 30, interval: float = 1.0, inject_anomaly: bool = False):
        self.running = True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(4.0)
            self.sock.connect((self.host, self.port))

            # Gửi đăng ký
            profile = {
                "type": "REGISTER",
                "data": {
                    "agent_id": self.agent_id,
                    "hostname": f"vnode-{self.agent_id}",
                    "os": "Linux Ubuntu 22.04 LTS (Simulated)",
                    "cpu_cores": random.choice([2, 4, 8]),
                    "total_ram_gb": random.choice([8.0, 16.0, 32.0])
                }
            }
            self.sock.sendall((json.dumps(profile) + "\n").encode("utf-8"))

            start_time = time.time()
            step = 0

            while self.running and (time.time() - start_time < duration_sec):
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                step += 1

                # Mặc định là tải bình thường
                cpu = random.uniform(20.0, 45.0)
                ram = random.uniform(40.0, 60.0)
                disk = 55.0 + random.uniform(-1, 1)

                # Tiêm kịch bản bất thường (Anomaly Injection) ở bước 10-15
                if inject_anomaly and (10 <= step <= 15):
                    cpu = random.uniform(92.0, 99.5)
                    ram = random.uniform(88.0, 96.0)

                payload = {
                    "type": "METRICS",
                    "data": {
                        "agent_id": self.agent_id,
                        "timestamp": timestamp,
                        "cpu_usage": round(cpu, 2),
                        "ram_usage": round(ram, 2),
                        "disk_usage": round(disk, 2),
                        "net_sent_mb": round(random.uniform(0.5, 3.0), 2),
                        "net_recv_mb": round(random.uniform(1.0, 5.0), 2),
                        "process_count": random.randint(150, 220)
                    }
                }
                self.sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                # Đọc ACK từ Server
                try:
                    self.sock.recv(1024)
                except Exception:
                    pass
                time.sleep(interval)

        except Exception as e:
            pass
        finally:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass

def run_multi_agent_simulation(num_agents: int = 5, duration_sec: int = 20, anomaly_ratio: float = 0.3):
    """Khởi động đồng thời N agent giả lập."""
    print(f"--> Bắt đầu mô phỏng {num_agents} Agent trong {duration_sec} giây (Tỷ lệ tiêm dị biệt: {anomaly_ratio*100}%)...")
    threads: List[threading.Thread] = []
    
    for i in range(num_agents):
        agent_id = f"sim-node-{i+1:02d}"
        inject = (i < int(num_agents * anomaly_ratio))
        agent = SimulatedAgent(agent_id=agent_id)
        t = threading.Thread(target=agent.start, args=(duration_sec, 1.0, inject))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    print("--> Mô phỏng hoàn tất!")

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_multi_agent_simulation(num_agents=count, duration_sec=15)
