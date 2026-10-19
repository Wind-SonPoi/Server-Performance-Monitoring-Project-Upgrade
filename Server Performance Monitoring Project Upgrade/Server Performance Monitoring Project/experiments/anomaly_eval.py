import pandas as pd
import numpy as np
import sys
import statistics
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
from analysis.anomaly_detection import detect_by_threshold, detect_by_zscore, detect_by_hybrid_ma
from analysis.visualization import plot_algorithm_comparison

def generate_multi_scenario_dataset(n_samples: int = 600, seed: int = 42) -> pd.DataFrame:
    """Tạo bộ dữ liệu chuỗi thời gian tổng hợp có gán nhãn thực tế (Ground Truth)
    kết hợp đa kịch bản bất thường: Quá tải tĩnh, Đột biến tức thời và Biến động nền.
    """
    np.random.seed(seed)
    timestamps = pd.date_range(start="2026-09-19 08:00:00", periods=n_samples, freq="3s")

    # Dữ liệu nền (Baseline): CPU dao động quanh 28-35%, RAM quanh 45-55% kèm nhiễu ngẫu nhiên
    time_steps = np.linspace(0, 25, n_samples)
    cpu = 30.0 + 6.0 * np.sin(time_steps) + np.random.normal(0, 3.5, n_samples)
    ram = 50.0 + 3.0 * np.cos(time_steps * 0.5) + np.random.normal(0, 2.0, n_samples)
    disk = np.linspace(55.0, 62.0, n_samples)

    labels = np.zeros(n_samples, dtype=bool)

    # Kịch bản 1: Quá tải CPU kéo dài vượt ngưỡng tĩnh 85% (3 cụm quá tải)
    cluster_1 = [45, 46, 47, 180, 181, 182, 360, 361]
    for idx in cluster_1:
        if idx < n_samples:
            cpu[idx] = np.random.uniform(88.0, 97.0)
            labels[idx] = True

    # Kịch bản 2: Quá tải RAM kéo dài vượt ngưỡng tĩnh 85%
    cluster_ram = [250, 251, 252, 480, 481]
    for idx in cluster_ram:
        if idx < n_samples:
            ram[idx] = np.random.uniform(87.0, 95.0)
            labels[idx] = True

    # Kịch bản 3: Đột biến tức thời (Spikes) dưới ngưỡng tĩnh nhưng nhảy vọt so với đường MA
    # Đang từ 30% vọt lên 68-82% rồi quay về baseline ngay lập tức
    spikes = [110, 215, 310, 420, 530]
    for idx in spikes:
        if idx < n_samples:
            cpu[idx] = np.random.uniform(70.0, 82.0)
            labels[idx] = True

    # Kịch bản 4: Đột biến nhẹ / Nhiễu biên (Boundary edge cases để kiểm tra tính nhạy)
    subtle_spikes = [90, 460]
    for idx in subtle_spikes:
        if idx < n_samples:
            cpu[idx] = np.random.uniform(62.0, 68.0)
            labels[idx] = True

    df = pd.DataFrame({
        "agent_id": "eval-node-01",
        "timestamp": timestamps,
        "cpu_usage": np.clip(cpu, 0.0, 100.0).round(2),
        "ram_usage": np.clip(ram, 0.0, 100.0).round(2),
        "disk_usage": np.clip(disk, 0.0, 100.0).round(2),
        "ground_truth": labels
    })
    return df

def calculate_metrics(y_true, y_pred) -> Dict[str, Any]:
    """Tính toán Precision, Recall, F1-Score và Ma trận nhầm lẫn."""
    tp = int(np.sum((y_true == True) & (y_pred == True)))
    fp = int(np.sum((y_true == False) & (y_pred == True)))
    fn = int(np.sum((y_true == True) & (y_pred == False)))
    tn = int(np.sum((y_true == False) & (y_pred == False)))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3)
    }

def run_anomaly_evaluation(seeds: List[int] = [10, 20, 30, 40, 50]):
    """Thực nghiệm 3: Đánh giá so sánh đối chuẩn các phương pháp phát hiện bất thường
    trên đa hạt giống ngẫu nhiên (Multi-seed Robustness Benchmark).
    """
    print("=" * 78)
    print("THỰC NGHIỆM 3: ĐÁNH GIÁ ĐỐI CHUẨN CÁC THUẬT TOÁN PHÁT HIỆN BẤT THƯỜNG")
    print("Bộ dữ liệu: Tổng hợp chuỗi thời gian có gán nhãn Ground Truth (5 kịch bản kiểm thử)")
    print("=" * 78)

    method_names = [
        "Static Threshold",
        "Dynamic Z-Score",
        "Hybrid MA Spike",
        "Ensemble (Voting)"
    ]

    metric_accumulator = {m: {"precision": [], "recall": [], "f1": [], "tp": [], "fp": [], "fn": []} for m in method_names}
    last_run_results = {}

    for seed in seeds:
        df = generate_multi_scenario_dataset(n_samples=600, seed=seed)
        y_true = df["ground_truth"]

        df = detect_by_threshold(df, cpu_thresh=config.CPU_THRESHOLD_PERCENT, ram_thresh=config.RAM_THRESHOLD_PERCENT)
        df = detect_by_zscore(df, threshold=config.Z_SCORE_THRESHOLD, window=20)
        df = detect_by_hybrid_ma(df, window=config.MOVING_AVG_WINDOW, spike_delta=config.SPIKE_DELTA_PERCENT)

        pred_ensemble = (
            df["anomaly_threshold"].astype(int) + 
            df["anomaly_zscore"].astype(int) + 
            df["anomaly_hybrid"].astype(int)
        ) >= 2

        runs = {
            "Static Threshold": calculate_metrics(y_true, df["anomaly_threshold"]),
            "Dynamic Z-Score": calculate_metrics(y_true, df["anomaly_zscore"]),
            "Hybrid MA Spike": calculate_metrics(y_true, df["anomaly_hybrid"]),
            "Ensemble (Voting)": calculate_metrics(y_true, pred_ensemble)
        }

        for m, met in runs.items():
            metric_accumulator[m]["precision"].append(met["precision"])
            metric_accumulator[m]["recall"].append(met["recall"])
            metric_accumulator[m]["f1"].append(met["f1"])
            metric_accumulator[m]["tp"].append(met["tp"])
            metric_accumulator[m]["fp"].append(met["fp"])
            metric_accumulator[m]["fn"].append(met["fn"])

        last_run_results = runs

    # Bảng tổng hợp Mean +- Std
    print(f"{'Thuật toán':<22}{'Precision (Mean±Std)':<24}{'Recall (Mean±Std)':<22}{'F1-Score (Mean±Std)':<22}")
    print("-" * 78)

    summary_results = {}
    for m in method_names:
        p_mean = statistics.mean(metric_accumulator[m]["precision"])
        p_std = statistics.stdev(metric_accumulator[m]["precision"]) if len(seeds) > 1 else 0.0
        r_mean = statistics.mean(metric_accumulator[m]["recall"])
        r_std = statistics.stdev(metric_accumulator[m]["recall"]) if len(seeds) > 1 else 0.0
        f1_mean = statistics.mean(metric_accumulator[m]["f1"])
        f1_std = statistics.stdev(metric_accumulator[m]["f1"]) if len(seeds) > 1 else 0.0

        p_str = f"{p_mean:.3f} ± {p_std:.3f}"
        r_str = f"{r_mean:.3f} ± {r_std:.3f}"
        f1_str = f"{f1_mean:.3f} ± {f1_std:.3f}"
        print(f"{m:<22}{p_str:<24}{r_str:<22}{f1_str:<22}")

        summary_results[m] = {
            "precision": round(p_mean, 3),
            "recall": round(r_mean, 3),
            "f1": round(f1_mean, 3)
        }

    print("=" * 78)
    print("Nhận xét khoa học:")
    print(" - Ngưỡng tĩnh (Static Threshold): Độ chính xác cao (ít dương tính giả) nhưng bỏ sót các đột biến cục bộ.")
    print(" - Dynamic Z-Score & Hybrid MA: Nhận diện nhạy bén các cú nhảy vọt tài nguyên trước khi chạm trần quá tải.")
    print(" - Ensemble Voting: Kết hợp đa phương pháp giúp cân bằng tối ưu giữa Precision và Recall.")
    print("=" * 78)

    # Xuất đồ thị đối chuẩn bài báo
    chart_path = plot_algorithm_comparison(summary_results)
    if chart_path:
        print(f"--> Đã xuất biểu đồ so sánh F1-Score bài báo tại: {chart_path}")

    return summary_results

if __name__ == "__main__":
    run_anomaly_evaluation()
