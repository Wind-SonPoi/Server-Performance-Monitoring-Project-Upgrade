from typing import Optional
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def calculate_moving_averages(df, window: int = config.MOVING_AVG_WINDOW):
    """Tính toán đường trung bình động giản đơn (SMA) và hàm mũ (EMA) cho các chỉ số tài nguyên."""
    if not PANDAS_AVAILABLE or df.empty:
        return df

    df = df.copy()
    for col in ["cpu_usage", "ram_usage", "disk_usage"]:
        if col in df.columns:
            # 1. Simple Moving Average (SMA)
            df[f"{col}_sma_{window}"] = (
                df.groupby("agent_id")[col]
                .transform(lambda s: s.rolling(window=window, min_periods=1).mean())
                .round(2)
            )

            # 2. Exponential Moving Average (EMA)
            df[f"{col}_ema_{window}"] = (
                df.groupby("agent_id")[col]
                .transform(lambda s: s.ewm(span=window, adjust=False).mean())
                .round(2)
            )

            # 3. Residual / Delta so với MA (độ chênh lệch)
            df[f"{col}_delta"] = (df[col] - df[f"{col}_sma_{window}"]).round(2)

    return df

def analyze_trend(series, window: int = 5) -> str:
    """Xác định xu hướng biến động (Tăng / Giảm / Ổn định) dựa trên độ dốc trung bình gần nhất."""
    if len(series) < 2:
        return "STABLE"
    recent = series.tail(window).values
    slope = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
    if slope > 1.5:
        return "RISING_RAPIDLY"
    elif slope > 0.5:
        return "RISING"
    elif slope < -1.5:
        return "FALLING_RAPIDLY"
    elif slope < -0.5:
        return "FALLING"
    else:
        return "STABLE"
