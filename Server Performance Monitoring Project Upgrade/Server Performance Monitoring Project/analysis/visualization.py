from pathlib import Path
from typing import Optional, Dict
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

try:
    import matplotlib
    matplotlib.use("Agg")  # Chế độ vẽ không cần màn hình hiển thị (Headless) cho server
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

def plot_time_series(df, agent_id: str, output_path: Optional[Path] = None) -> Optional[str]:
    """Vẽ biểu đồ chuỗi thời gian biến động CPU, RAM, Disk với đầy đủ 3 đường ngưỡng cảnh báo."""
    if not MATPLOTLIB_AVAILABLE or df.empty:
        return None

    agent_df = df[df["agent_id"] == agent_id].copy()
    if agent_df.empty:
        return None

    plt.figure(figsize=(12, 6))
    plt.plot(agent_df["timestamp"], agent_df["cpu_usage"], label="CPU Usage (%)", color="#e74c3c", linewidth=1.8)
    plt.plot(agent_df["timestamp"], agent_df["ram_usage"], label="RAM Usage (%)", color="#3498db", linewidth=1.8)
    plt.plot(agent_df["timestamp"], agent_df["disk_usage"], label="Disk Usage (%)", color="#2ecc71", linewidth=1.8)

    # Vẽ đầy đủ 3 đường ngưỡng cấu hình (CPU, RAM, Disk)
    plt.axhline(y=config.CPU_THRESHOLD_PERCENT, color="#e74c3c", linestyle="--", alpha=0.8, 
                label=f"Ngưỡng CPU ({config.CPU_THRESHOLD_PERCENT}%)")
    plt.axhline(y=config.RAM_THRESHOLD_PERCENT, color="#2980b9", linestyle=":", alpha=0.8, 
                label=f"Ngưỡng RAM ({config.RAM_THRESHOLD_PERCENT}%)")
    plt.axhline(y=config.DISK_THRESHOLD_PERCENT, color="#27ae60", linestyle="-.", alpha=0.8, 
                label=f"Ngưỡng Disk ({config.DISK_THRESHOLD_PERCENT}%)")
    
    plt.title(f"Biến động tài nguyên theo chuỗi thời gian - Máy chủ {agent_id}", fontsize=14, fontweight="bold")
    plt.xlabel("Thời gian", fontsize=11)
    plt.ylabel("Tỷ lệ chiếm dụng (%)", fontsize=11)
    plt.ylim(0, 105)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper right", framealpha=0.9)
    plt.tight_layout()

    if output_path is None:
        output_path = config.REPORTS_DIR / f"timeseries_{agent_id}.png"
    
    plt.savefig(output_path, dpi=300)
    plt.close()
    return str(output_path)

def plot_moving_average_anomaly(df, agent_id: str, output_path: Optional[Path] = None) -> Optional[str]:
    """Vẽ biểu đồ đường trung bình động (MA) và đánh dấu trực quan các điểm dị biệt phát hiện được."""
    if not MATPLOTLIB_AVAILABLE or df.empty:
        return None

    agent_df = df[df["agent_id"] == agent_id].copy()
    if agent_df.empty:
        return None

    # Xác định linh hoạt cột MA theo cấu hình thay vì gán cứng _sma_5
    ma_col = f"cpu_usage_sma_{config.MOVING_AVG_WINDOW}"
    if ma_col not in agent_df.columns:
        sma_cols = [c for c in agent_df.columns if c.startswith("cpu_usage_sma_")]
        if sma_cols:
            ma_col = sma_cols[0]
        else:
            # Tự động tính toán đường MA nếu chưa có trong DataFrame
            agent_df[ma_col] = agent_df["cpu_usage"].rolling(config.MOVING_AVG_WINDOW, min_periods=1).mean().round(2)

    plt.figure(figsize=(12, 6))
    plt.plot(agent_df["timestamp"], agent_df["cpu_usage"], label="Tải thực tế CPU (%)", color="#95a5a6", linewidth=1.2, alpha=0.85)
    plt.plot(agent_df["timestamp"], agent_df[ma_col], label=f"Đường làm mượt SMA ({config.MOVING_AVG_WINDOW})", color="#2980b9", linewidth=2.2)

    # Đánh dấu các điểm bất thường
    if "anomaly_ensemble" in agent_df.columns:
        anomalies = agent_df[agent_df["anomaly_ensemble"]]
        if not anomalies.empty:
            plt.scatter(anomalies["timestamp"], anomalies["cpu_usage"], color="#e74c3c", s=75, zorder=5, label="Bất thường phát hiện (Anomaly)", edgecolors="black")

    plt.title(f"Phân tích chuỗi thời gian & Phát hiện dị biệt CPU - Máy chủ {agent_id}", fontsize=14, fontweight="bold")
    plt.xlabel("Thời gian", fontsize=11)
    plt.ylabel("Tỷ lệ sử dụng (%)", fontsize=11)
    plt.ylim(0, 105)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.legend(loc="upper left", framealpha=0.9)
    plt.tight_layout()

    if output_path is None:
        output_path = config.REPORTS_DIR / f"ma_anomaly_{agent_id}.png"

    plt.savefig(output_path, dpi=300)
    plt.close()
    return str(output_path)

def plot_algorithm_comparison(results: Dict[str, Dict[str, float]], output_path: Optional[Path] = None) -> Optional[str]:
    """Vẽ biểu đồ cột so sánh Precision, Recall, F1-Score giữa các phương pháp phục vụ bài báo."""
    if not MATPLOTLIB_AVAILABLE or not results:
        return None

    methods = list(results.keys())
    precisions = [results[m].get("precision", 0) for m in methods]
    recalls = [results[m].get("recall", 0) for m in methods]
    f1_scores = [results[m].get("f1", 0) for m in methods]

    import numpy as np
    x = np.arange(len(methods))
    width = 0.25

    plt.figure(figsize=(10, 6))
    plt.bar(x - width, precisions, width, label="Precision", color="#3498db")
    plt.bar(x, recalls, width, label="Recall", color="#2ecc71")
    plt.bar(x + width, f1_scores, width, label="F1-Score", color="#e67e22")

    plt.xlabel("Phương pháp phát hiện bất thường", fontsize=11, fontweight="bold")
    plt.ylabel("Chỉ số đánh giá [0 - 1.0]", fontsize=11, fontweight="bold")
    plt.title("Đánh giá so sánh hiệu năng các thuật toán phát hiện bất thường", fontsize=13, fontweight="bold")
    plt.xticks(x, methods)
    plt.ylim(0, 1.1)
    plt.legend(loc="lower right")
    plt.grid(axis="y", linestyle=":", alpha=0.7)
    plt.tight_layout()

    if output_path is None:
        output_path = config.REPORTS_DIR / "algorithm_comparison.png"

    plt.savefig(output_path, dpi=300)
    plt.close()
    return str(output_path)
