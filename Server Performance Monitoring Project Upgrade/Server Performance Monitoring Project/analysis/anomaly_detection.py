from typing import List, Dict, Any, Optional
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

try:
    import pandas as pd
    import numpy as np
    ANOMALY_LIB_AVAILABLE = True
except ImportError:
    ANOMALY_LIB_AVAILABLE = False

def detect_by_threshold(df, cpu_thresh: float = config.CPU_THRESHOLD_PERCENT,
                        ram_thresh: float = config.RAM_THRESHOLD_PERCENT,
                        disk_thresh: float = config.DISK_THRESHOLD_PERCENT):
    """Phương pháp 1: Phát hiện bất thường dựa trên ngưỡng tĩnh (Static Threshold)."""
    if not ANOMALY_LIB_AVAILABLE or df.empty:
        return df

    df = df.copy()
    cpu_cond = df["cpu_usage"] > cpu_thresh
    ram_cond = df["ram_usage"] > ram_thresh
    disk_cond = df["disk_usage"] > disk_thresh

    df["anomaly_threshold"] = cpu_cond | ram_cond | disk_cond
    return df

def detect_by_zscore(df, threshold: float = config.Z_SCORE_THRESHOLD, window: int = 20):
    """Phương pháp 2: Phát hiện bất thường dựa trên độ lệch chuẩn động Z-Score (Z-Score Outlier).
    Loại bỏ điểm hiện tại khỏi baseline bằng shift(1) nhằm tránh current-sample data leakage.
    """
    if not ANOMALY_LIB_AVAILABLE or df.empty:
        return df

    df = df.copy()
    df["anomaly_zscore"] = False

    for col in ["cpu_usage", "ram_usage"]:
        if col in df.columns:
            # Baseline tính trên lịch sử quá khứ (shift 1) để tránh việc mẫu bất thường tự làm biến dạng baseline của chính nó
            rolling_mean = df.groupby("agent_id")[col].transform(
                lambda s: s.shift(1).rolling(window, min_periods=3).mean()
            )
            rolling_std = df.groupby("agent_id")[col].transform(
                lambda s: s.shift(1).rolling(window, min_periods=3).std()
            )

            # Điền giá trị cho các điểm đầu chuỗi bằng mean/std tổng thể của agent
            rolling_mean = rolling_mean.fillna(df.groupby("agent_id")[col].transform("mean"))
            rolling_std = rolling_std.fillna(df.groupby("agent_id")[col].transform("std")).replace(0, np.nan)

            z_score = ((df[col] - rolling_mean) / rolling_std).abs()
            df[f"{col}_zscore"] = z_score.round(2)
            
            # Chỉ gắn cờ dị biệt khi Z-Score vượt ngưỡng và tải thực tế đáng kể (> 50%)
            is_z_anomaly = (z_score > threshold) & (df[col] > 50.0)
            df["anomaly_zscore"] = df["anomaly_zscore"] | is_z_anomaly.fillna(False)

    return df

def detect_by_hybrid_ma(df, window: int = config.MOVING_AVG_WINDOW, 
                        spike_delta: float = config.SPIKE_DELTA_PERCENT):
    """Phương pháp 3: Phát hiện bất thường đột biến tải dựa trên Moving Average (Hybrid MA Spike).
    Sử dụng baseline quá khứ shift(1) để đo chính xác bước nhảy đột ngột.
    """
    if not ANOMALY_LIB_AVAILABLE or df.empty:
        return df

    df = df.copy()
    df["anomaly_hybrid"] = False

    for col in ["cpu_usage", "ram_usage"]:
        if col in df.columns:
            # Baseline MA lịch sử không chứa điểm hiện tại
            ma = df.groupby("agent_id")[col].transform(
                lambda s: s.shift(1).rolling(window, min_periods=1).mean()
            )
            ma = ma.fillna(df[col])
            delta = df[col] - ma
            df[f"{col}_spike_delta"] = delta.round(2)
            
            is_spike = (delta > spike_delta) & (df[col] > 60.0)
            df["anomaly_hybrid"] = df["anomaly_hybrid"] | is_spike.fillna(False)

    return df

def evaluate_all_methods(df):
    """Chạy đồng thời cả 3 phương pháp trên tập dữ liệu để so sánh đối chuẩn."""
    if not ANOMALY_LIB_AVAILABLE or df.empty:
        return df

    df = detect_by_threshold(df)
    df = detect_by_zscore(df)
    df = detect_by_hybrid_ma(df)

    # Đánh dấu tổng hợp (Ensemble Voting)
    df["anomaly_ensemble"] = (
        df["anomaly_threshold"].astype(int) + 
        df["anomaly_zscore"].astype(int) + 
        df["anomaly_hybrid"].astype(int)
    ) >= 2

    return df
