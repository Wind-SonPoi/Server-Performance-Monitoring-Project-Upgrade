# Hệ Thống Giám Sát, Phân Tích & Phát Hiện Bất Thường Hiệu Năng Máy Chủ Phân Tán

Dự án nghiên cứu thực nghiệm và xây dựng hệ thống phần mềm hoàn chỉnh phục vụ viết **bài báo khoa học** và **báo cáo đề tài**, tích hợp đầy đủ 5 thành phần công nghệ: **TCP Socket, SQLite, Pandas / NumPy / Matplotlib, Flask Web Dashboard, và Tkinter Desktop GUI**.

---

## 1. Bản Đồ Ánh Xạ Công Nghệ (Technology Mapping)

| STT | Công nghệ | Vai trò trong hệ thống |
|:---:|:---|:---|
| 1 | **TCP Socket** | Thu thập các chỉ số hiệu năng (CPU, RAM, Disk, Net, Process) từ các máy con (Agent) gửi liên tục về Server trung tâm đa luồng. |
| 2 | **SQLite** | Cơ sở dữ liệu quan hệ lưu trữ dữ liệu chuỗi thời gian (time-series logs) với cơ chế WAL và đánh chỉ mục (Index) tối ưu truy vấn. |
| 3 | **Pandas / NumPy** | Động cơ phân tích dữ liệu: làm sạch (Cleaning), tính toán thống kê mô tả (Mean, Std, Percentiles), đường trung bình động (SMA/EMA) và thuật toán phát hiện dị biệt (Z-Score & Spike). |
| 4 | **Matplotlib** | Tự động vẽ và xuất các biểu đồ chất lượng cao (300 DPI) phục vụ cho bài báo khoa học vào thư mục `reports/`. |
| 5 | **Flask** | Web Dashboard trực quan hóa theo thời gian thực (Chart.js), cung cấp các RESTful API (`/api/metrics`, `/api/analytics`, `/api/anomalies`). |
| 6 | **Tkinter** | Desktop GUI quản trị viên cục bộ tại máy chủ: Bật/Tắt Socket Server, cấu hình IP/Port, điều chỉnh ngưỡng cảnh báo và xem console log. |

---

## 2. Cấu Trúc Thư Mục Dự Án

```
de tai ca nhan/
├── config.py                 # File cấu hình tập trung (IP, Port, Ngưỡng, DB Path)
├── requirements.txt          # Danh mục thư viện phụ thuộc
├── run_system.py             # Script điều phối khởi chạy hệ thống
│
├── client/                   # [Socket Client Agent]
│   ├── collector.py          # Thu thập metric hệ thống bằng psutil
│   └── agent.py              # Đóng gói JSON và gửi qua TCP Socket định kỳ
│
├── server/                   # [Socket Server & SQLite DB]
│   ├── database.py           # Khởi tạo bảng, index và hàm CRUD SQLite
│   └── socket_server.py      # TCP Server đa luồng tiếp nhận luồng dữ liệu
│
├── analysis/                 # [Data Analytics Engine]
│   ├── preprocessing.py      # Làm sạch dữ liệu chuỗi thời gian bằng Pandas
│   ├── statistics.py         # Thống kê mô tả & ma trận tương quan bằng NumPy/Pandas
│   ├── moving_average.py     # Tính toán Simple & Exponential Moving Average
│   ├── anomaly_detection.py  # 3 thuật toán: Ngưỡng tĩnh, Z-Score, Hybrid MA
│   └── visualization.py      # Xuất biểu đồ phân tích bằng Matplotlib
│
├── flask_app/                # [Flask Web Dashboard]
│   ├── app.py                # Server Flask & REST APIs
│   ├── templates/            # Giao diện HTML (dashboard, analytics, anomalies)
│   └── static/               # CSS & JavaScript (Chart.js real-time)
│
├── tkinter_app/              # [Desktop Admin GUI]
│   └── admin_panel.py        # Giao diện điều khiển máy chủ nội bộ
│
├── experiments/              # [Bộ Thực Nghiệm Khoa Học Phục Vụ Bài Báo]
│   ├── workload_simulator.py # Giả lập N máy con chạy đồng thời và tiêm lỗi tải
│   ├── latency_test.py       # Đo độ trễ truyền gói tin Socket (1, 5, 10, 20 clients)
│   ├── db_benchmark.py       # Benchmark tốc độ chèn và truy vấn CSDL SQLite
│   └── anomaly_eval.py       # Đánh giá đối chuẩn Precision, Recall, F1-Score
│
├── database/                 # Thư mục chứa file CSDL SQLite monitoring.db
└── reports/                  # Thư mục lưu trữ biểu đồ và báo cáo xuất ra
```

---

## 3. Hướng Dẫn Cài Đặt & Khởi Chạy

### A. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### B. Khởi chạy từng thành phần độc lập
1. **Khởi động Socket Server:**
   ```bash
   python run_system.py server
   ```
2. **Khởi động Desktop Admin Panel (Tkinter):**
   ```bash
   python run_system.py admin
   ```
3. **Khởi động Web Dashboard (Flask):**
   ```bash
   python run_system.py web
   ```
   *Truy cập trình duyệt tại: `http://127.0.0.1:5000`*
4. **Khởi động Client Agent (thu thập máy thật):**
   ```bash
   python run_system.py client srv-node-01
   ```

### C. Khởi chạy toàn bộ hệ thống cùng lúc
```bash
python run_system.py all
```

---

## 4. Chạy Bộ Thực Nghiệm Khoa Học Cho Bài Báo

Để có số liệu thực nghiệm, bảng đối chuẩn và biểu đồ minh chứng đưa vào bài báo khoa học:
```bash
python run_system.py experiments
```

Lệnh trên sẽ tự động:
1. **Đo đạc độ trễ Socket (Latency Benchmark):** Xuất bảng độ trễ theo số lượng client đồng thời.
2. **Đo hiệu năng SQLite (Database Scalability):** Xuất bảng thông lượng (throughput) và thời gian truy vấn theo quy mô bản ghi ($1.000 \rightarrow 50.000$ rows).
3. **Đánh giá thuật toán phát hiện bất thường (Algorithm Comparison):** Đo lường ma trận nhầm lẫn ($TP, FP, FN, TN$), $Precision$, $Recall$, và $F_1$-score giữa:
   - *Static Threshold*
   - *Dynamic Z-Score*
   - *Hybrid Moving Average Spike*
   - *Ensemble (Voting)*
4. Tự động xuất biểu đồ so sánh `algorithm_comparison.png` vào thư mục `reports/`.
