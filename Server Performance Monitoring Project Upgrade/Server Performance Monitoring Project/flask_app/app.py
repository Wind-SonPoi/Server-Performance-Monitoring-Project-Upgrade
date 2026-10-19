import threading
from pathlib import Path
import sys

# Đảm bảo import được config khi chạy độc lập
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from server.database import (
    get_agents, get_recent_logs, get_anomalies, get_system_summary,
    load_thresholds, save_thresholds, check_and_update_offline_agents
)
from analysis.preprocessing import load_logs_dataframe
from analysis.statistics import compute_summary_statistics, compute_correlation_matrix
from analysis.moving_average import calculate_moving_averages, analyze_trend
from analysis.anomaly_detection import evaluate_all_methods
from analysis.visualization import plot_time_series, plot_moving_average_anomaly

from flask import Flask, render_template, jsonify, request, send_from_directory

app = Flask(
    __name__, 
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static")
)

# ----------------- WEB PAGES ROUTES ----------------- #

@app.route("/")
def index():
    """Trang chủ Dashboard hiển thị thời gian thực."""
    summary = get_system_summary()
    agents = get_agents()
    thresholds = load_thresholds()
    local_ip = config.get_local_ip()
    return render_template(
        "dashboard.html", 
        summary=summary, 
        agents=agents, 
        thresholds=thresholds,
        local_ip=local_ip,
        socket_port=config.SOCKET_PORT
    )

@app.route("/analytics")
def analytics_view():
    """Trang phân tích chuyên sâu chuỗi thời gian và thống kê mô tả."""
    agents = get_agents()
    selected_agent = request.args.get("agent_id", agents[0]["agent_id"] if agents else None)
    local_ip = config.get_local_ip()
    return render_template(
        "analytics.html", 
        agents=agents, 
        selected_agent=selected_agent,
        local_ip=local_ip
    )

@app.route("/anomalies")
def anomalies_view():
    """Trang quản lý và tra cứu danh sách sự kiện bất thường đã phát hiện."""
    anomalies = get_anomalies(limit=100)
    local_ip = config.get_local_ip()
    return render_template("anomalies.html", anomalies=anomalies, local_ip=local_ip)

@app.route("/reports/<path:filename>")
def serve_report_file(filename):
    """Phục vụ xem trực tiếp các biểu đồ đã xuất từ Matplotlib."""
    return send_from_directory(str(config.REPORTS_DIR), filename)

# ----------------- RESTFUL APIS ----------------- #

@app.route("/api/summary")
def api_summary():
    """API cung cấp các chỉ số tổng quan hệ thống."""
    return jsonify(get_system_summary())

@app.route("/api/agents")
def api_agents():
    """API danh sách máy chủ kèm trạng thái ONLINE/OFFLINE cập nhật theo heartbeat."""
    return jsonify(get_agents())

@app.route("/api/metrics/recent")
def api_recent_metrics():
    """API lấy chuỗi thời gian hiệu năng gần nhất phục vụ vẽ biểu đồ động."""
    agent_id = request.args.get("agent_id", "").strip() or None
    try:
        limit = int(request.args.get("limit", 60))
        limit = max(1, min(limit, 1000))
    except (ValueError, TypeError):
        limit = 60

    logs = get_recent_logs(agent_id=agent_id, limit=limit)
    return jsonify(logs)

@app.route("/api/anomalies")
def api_anomalies():
    """API lấy danh sách sự kiện dị biệt gần nhất."""
    try:
        limit = int(request.args.get("limit", 50))
        limit = max(1, min(limit, 500))
    except (ValueError, TypeError):
        limit = 50

    return jsonify(get_anomalies(limit=limit))

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """API đọc và lưu trữ cấu hình ngưỡng vào CSDL SQLite."""
    if request.method == "POST":
        data = request.get_json() or {}
        try:
            cpu = float(data.get("cpu", config.CPU_THRESHOLD_PERCENT))
            ram = float(data.get("ram", config.RAM_THRESHOLD_PERCENT))
            disk = float(data.get("disk", config.DISK_THRESHOLD_PERCENT))

            if not (0 <= cpu <= 100 and 0 <= ram <= 100 and 0 <= disk <= 100):
                return jsonify({"success": False, "error": "Ngưỡng phải nằm trong khoảng 0-100%"}), 400

            save_thresholds(cpu, ram, disk)
            return jsonify({
                "success": True, 
                "message": "Đã lưu ngưỡng cảnh báo thành công vào CSDL SQLite!", 
                "thresholds": {"cpu": cpu, "ram": ram, "disk": disk}
            })
        except (ValueError, TypeError) as e:
            return jsonify({"success": False, "error": f"Dữ liệu không hợp lệ: {e}"}), 400

    return jsonify(load_thresholds())

@app.route("/api/analytics/statistics")
def api_statistics():
    """API tính toán thống kê mô tả thời gian thực bằng Pandas/NumPy."""
    agent_id = request.args.get("agent_id", "").strip() or None
    try:
        df = load_logs_dataframe(agent_id=agent_id, limit=300)
        if df.empty:
            return jsonify({"error": "Chưa có đủ dữ liệu hiệu năng của máy chủ này"}), 404
        
        stats = compute_summary_statistics(df)
        corr = compute_correlation_matrix(df)
        trend = analyze_trend(df["cpu_usage"]) if "cpu_usage" in df.columns else "UNKNOWN"

        return jsonify({
            "agent_id": agent_id,
            "sample_count": len(df),
            "statistics": stats,
            "correlation": corr,
            "cpu_trend": trend
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/reports/generate-charts")
def api_generate_charts():
    """API kích hoạt module Matplotlib xuất hình ảnh biểu đồ bài báo độ phân giải cao."""
    agent_id = request.args.get("agent_id", "").strip() or None
    try:
        df = load_logs_dataframe(agent_id=agent_id, limit=200)
        if df.empty:
            return jsonify({"success": False, "message": "Chưa có đủ dữ liệu để trích xuất biểu đồ"}), 400
        
        # Áp dụng MA và phát hiện bất thường
        df = calculate_moving_averages(df)
        df = evaluate_all_methods(df)

        actual_id = agent_id or (df["agent_id"].iloc[0] if not df.empty else "srv-node-01")
        chart1_path = plot_time_series(df, agent_id=actual_id)
        chart2_path = plot_moving_average_anomaly(df, agent_id=actual_id)

        return jsonify({
            "success": True, 
            "message": "Đã trích xuất biểu đồ chất lượng cao thành công vào thư mục /reports!",
            "charts": [
                f"/reports/timeseries_{actual_id}.png",
                f"/reports/ma_anomaly_{actual_id}.png"
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """API kích hoạt nhanh Agent mô phỏng tải để kiểm tra trực quan trên Dashboard."""
    try:
        from experiments.workload_simulator import run_multi_agent_simulation
        threading.Thread(target=run_multi_agent_simulation, args=(3, 15, 0.4), daemon=True).start()
        return jsonify({
            "success": True, 
            "message": "Đang chạy 3 trạm mô phỏng (sim-node-01..03) trong 15s với 40% tải tiêm dị biệt!"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def run_flask_app():
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG)

if __name__ == "__main__":
    run_flask_app()
