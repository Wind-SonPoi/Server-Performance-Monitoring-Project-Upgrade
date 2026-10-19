import socket
import time
import json
import statistics
import threading
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

def measure_client_latency(host: str, port: int, num_requests: int = 20) -> list:
    """Đo độ trễ khứ hồi TCP Round-Trip Time (RTT: Client gửi -> Server xử lý & phản hồi -> Client nhận ACK)."""
    latencies = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(4.0)
        s.connect((host, port))
        
        for _ in range(num_requests):
            payload = {
                "type": "METRICS",
                "data": {
                    "agent_id": "latency-tester",
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "cpu_usage": 30.0,
                    "ram_usage": 40.0,
                    "disk_usage": 50.0
                }
            }
            raw = (json.dumps(payload) + "\n").encode("utf-8")
            
            t0 = time.perf_counter()
            s.sendall(raw)
            # Nhận ACK xác nhận từ Server để đo chính xác TCP Application-level RTT
            ack = s.recv(1024)
            t1 = time.perf_counter()
            
            if ack:
                latencies.append((t1 - t0) * 1000) # milliseconds
            time.sleep(0.04)
        s.close()
    except Exception as e:
        pass
    return latencies

def run_concurrency_experiment(concurrency_levels=[1, 5, 10, 20]):
    """Thực nghiệm đo độ trễ khứ hồi RTT khi quy mô kết nối đồng thời tăng dần."""
    print("=" * 68)
    print("THỰC NGHIỆM 1: ĐÁNH GIÁ ĐỘ TRỄ KHỨ HỒI TCP ROUND-TRIP TIME (RTT)")
    print("=" * 68)
    print(f"{'Clients':<10}{'Req/Client':<12}{'Avg RTT (ms)':<14}{'Min (ms)':<10}{'Max (ms)':<10}{'P95 (ms)':<10}")
    print("-" * 68)

    results = {}
    target_host = "127.0.0.1" if config.SOCKET_HOST == "0.0.0.0" else config.SOCKET_HOST
    for c in concurrency_levels:
        all_latencies = []
        threads = []

        def worker():
            lat = measure_client_latency(target_host, config.SOCKET_PORT, num_requests=15)
            all_latencies.extend(lat)

        for _ in range(c):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if all_latencies:
            avg_lat = statistics.mean(all_latencies)
            min_lat = min(all_latencies)
            max_lat = max(all_latencies)
            all_latencies.sort()
            p95_idx = int(0.95 * len(all_latencies))
            p95_lat = all_latencies[min(p95_idx, len(all_latencies)-1)]

            print(f"{c:<10}{15:<12}{avg_lat:<12.3f}{min_lat:<10.3f}{max_lat:<10.3f}{p95_lat:<10.3f}")
            results[c] = {"avg": avg_lat, "min": min_lat, "max": max_lat, "p95": p95_lat}
        else:
            print(f"{c:<10}{15:<12}{'Server Chưa Bật!':<30}")

    print("=" * 65)
    return results

if __name__ == "__main__":
    run_concurrency_experiment()
