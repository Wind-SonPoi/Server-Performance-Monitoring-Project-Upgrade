from typing import Dict, Any, Optional
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from analysis.preprocessing import load_logs_dataframe

try:
    import pandas as pd
    import numpy as np
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

def compute_summary_statistics(df) -> Dict[str, Any]:
    """Tính toán các chỉ số thống kê mô tả (Descriptive Statistics) phục vụ báo cáo bài báo."""
    if not ANALYTICS_AVAILABLE or df.empty:
        return {}

    metrics = ["cpu_usage", "ram_usage", "disk_usage", "net_sent_mb", "net_recv_mb", "process_count"]
    stats_result = {}

    for metric in metrics:
        if metric not in df.columns:
            continue
        series = df[metric].dropna()
        if series.empty:
            continue

        stats_result[metric] = {
            "count": int(len(series)),
            "mean": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "std": round(float(series.std()), 2),
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "p25": round(float(np.percentile(series, 25)), 2),
            "p75": round(float(np.percentile(series, 75)), 2),
            "p95": round(float(np.percentile(series, 95)), 2),
            "p99": round(float(np.percentile(series, 99)), 2),
        }

    return stats_result

def compute_per_agent_statistics(df) -> Dict[str, Dict[str, Any]]:
    """Tính toán thống kê phân rã theo từng máy chủ (Agent)."""
    if not ANALYTICS_AVAILABLE or df.empty:
        return {}

    agent_stats = {}
    for agent_id, group in df.groupby("agent_id"):
        agent_stats[str(agent_id)] = compute_summary_statistics(group)

    return agent_stats

def compute_correlation_matrix(df) -> Dict[str, Dict[str, float]]:
    """Tính toán ma trận tương quan giữa các chỉ số hệ thống (Correlation Matrix)."""
    if not ANALYTICS_AVAILABLE or df.empty:
        return {}

    metrics = ["cpu_usage", "ram_usage", "disk_usage", "net_sent_mb", "net_recv_mb", "process_count"]
    available_metrics = [m for m in metrics if m in df.columns]
    
    corr_df = df[available_metrics].corr()
    return corr_df.round(3).to_dict()
