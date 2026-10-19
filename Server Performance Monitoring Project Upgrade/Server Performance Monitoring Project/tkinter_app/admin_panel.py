import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import sys
import webbrowser
from pathlib import Path
from typing import Optional

# UTF-8 console output setup
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent.parent))
import config
from server.socket_server import SocketServerManager
from server.database import get_agents, get_system_summary, load_thresholds, save_thresholds

class AdminControlPanelApp:
    """Giao diện Desktop GUI Tkinter cao cấp dành cho Quản trị viên điều khiển Server cục bộ."""

    def __init__(self, root: tk.Tk, server_manager: Optional[SocketServerManager] = None):
        self.root = root
        self.root.title("Server Sentinel - Bảng Điều Khiển Quản Trị Cục Bộ")
        self.root.geometry("960x720")
        self.root.minsize(860, 620)
        self.root.configure(bg="#f1f5f9")

        # Quản lý Socket Server
        if server_manager is not None:
            self.server_manager = server_manager
        else:
            self.server_manager = SocketServerManager()

        self.is_monitoring_gui = True
        self.local_ip = config.get_local_ip()

        self._setup_style()
        self._build_ui()
        self._load_saved_settings()

        # Kiểm tra nếu Server đã được bật từ trước (ví dụ qua run_system all)
        if self.server_manager.running:
            self._set_server_ui_running(True)
            self.log_message(f"TCP Socket Server đang hoạt động tại {self.server_manager.host}:{self.server_manager.port}", "SUCCESS")

        # Bắt đầu luồng cập nhật giao diện định kỳ
        self._update_thread = threading.Thread(target=self._periodic_ui_refresh, daemon=True)
        self._update_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Cấu hình màu sắc hiện đại
        self.style.configure(".", background="#f1f5f9", font=("Segoe UI", 9))
        self.style.configure("TFrame", background="#f1f5f9")
        self.style.configure("Card.TFrame", background="#ffffff", relief="flat")
        
        self.style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#0f172a", background="#ffffff")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#64748b", background="#ffffff")
        
        self.style.configure("StatTitle.TLabel", font=("Segoe UI", 8, "bold"), foreground="#64748b", background="#ffffff")
        self.style.configure("StatVal.TLabel", font=("Segoe UI", 16, "bold"), foreground="#0f172a", background="#ffffff")
        
        # Style cho Treeview
        self.style.configure("Treeview", 
            background="#ffffff",
            foreground="#1e293b",
            rowheight=26,
            fieldbackground="#ffffff",
            font=("Segoe UI", 9)
        )
        self.style.configure("Treeview.Heading", 
            font=("Segoe UI", 9, "bold"), 
            background="#e2e8f0", 
            foreground="#334155"
        )
        self.style.map("Treeview", background=[("selected", "#3b82f6")], foreground=[("selected", "#ffffff")])

    def _build_ui(self):
        # 1. Header Bar (Dark Banner)
        header_container = tk.Frame(self.root, bg="#0f172a", height=65)
        header_container.pack(fill=tk.X)

        header_inner = tk.Frame(header_container, bg="#0f172a")
        header_inner.pack(fill=tk.X, padx=18, pady=12)

        # Left: Logo & Title
        title_box = tk.Frame(header_inner, bg="#0f172a")
        title_box.pack(side=tk.LEFT)
        lbl_app_name = tk.Label(title_box, text="⚡ SERVER SENTINEL", font=("Segoe UI", 12, "bold"), fg="#ffffff", bg="#0f172a")
        lbl_app_name.pack(side=tk.LEFT)
        lbl_sub = tk.Label(title_box, text=" | Quản Trị Hệ Thống Phân Tán", font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a")
        lbl_sub.pack(side=tk.LEFT)

        # Right: Status Pill & LAN IP
        status_box = tk.Frame(header_inner, bg="#0f172a")
        status_box.pack(side=tk.RIGHT)

        self.lbl_server_pill = tk.Label(
            status_box, 
            text="● SERVER ĐANG TẮT", 
            font=("Segoe UI", 9, "bold"), 
            fg="#ef4444", 
            bg="#1e293b",
            padx=10, 
            pady=3,
            relief=tk.FLAT
        )
        self.lbl_server_pill.pack(side=tk.RIGHT, padx=(10, 0))

        lan_text = f"LAN IP: {self.local_ip}:{config.SOCKET_PORT}"
        self.lbl_lan = tk.Label(status_box, text=lan_text, font=("Consolas", 9), fg="#38bdf8", bg="#1e293b", padx=8, pady=3)
        self.lbl_lan.pack(side=tk.RIGHT)

        btn_copy_ip = tk.Button(
            status_box, text="📋", font=("Segoe UI", 8), bg="#334155", fg="white", relief=tk.FLAT,
            command=self._copy_lan_ip, cursor="hand2"
        )
        btn_copy_ip.pack(side=tk.RIGHT, padx=4)

        # 2. Main Content Canvas/Container
        main_content = tk.Frame(self.root, bg="#f1f5f9")
        main_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Top Section: KPI Quick Cards
        cards_frame = tk.Frame(main_content, bg="#f1f5f9")
        cards_frame.pack(fill=tk.X, pady=(0, 10))

        self.card_clients = self._create_kpi_card(cards_frame, "KẾT NỐI SOCKET", "0 Client", "#2563eb", 0)
        self.card_packets = self._create_kpi_card(cards_frame, "GÓI TIN ĐÃ XỬ LÝ", "0", "#0891b2", 1)
        self.card_agents  = self._create_kpi_card(cards_frame, "MÁY CHỦ (ONLINE)", "0 / 0", "#10b981", 2)
        self.card_alerts  = self._create_kpi_card(cards_frame, "DỊ BIỆT (ANOMALIES)", "0", "#ef4444", 3)

        # Control Panel & Thresholds Row
        controls_row = tk.Frame(main_content, bg="#ffffff", bd=1, relief="solid")
        controls_row.pack(fill=tk.X, pady=(0, 10), ipady=5)

        # Frame 1: Server Startup & Network
        sec1 = tk.Frame(controls_row, bg="#ffffff", padx=12, pady=6)
        sec1.pack(side=tk.LEFT, fill=tk.Y)

        lbl_s1 = tk.Label(sec1, text="VẬN HÀNH SOCKET SERVER", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff")
        lbl_s1.pack(anchor="w", pady=(0, 4))

        f_inputs = tk.Frame(sec1, bg="#ffffff")
        f_inputs.pack(anchor="w")

        tk.Label(f_inputs, text="Host:", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT)
        self.ent_host = ttk.Entry(f_inputs, width=12)
        self.ent_host.insert(0, config.SOCKET_HOST)
        self.ent_host.pack(side=tk.LEFT, padx=(3, 10))

        tk.Label(f_inputs, text="Port:", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT)
        self.ent_port = ttk.Entry(f_inputs, width=6)
        self.ent_port.insert(0, str(config.SOCKET_PORT))
        self.ent_port.pack(side=tk.LEFT, padx=(3, 12))

        self.btn_start = tk.Button(
            f_inputs, text="▶ Bật Server", bg="#10b981", fg="white", font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, padx=10, pady=2, command=self.start_server, cursor="hand2"
        )
        self.btn_start.pack(side=tk.LEFT, padx=3)

        self.btn_stop = tk.Button(
            f_inputs, text="⏹ Dừng", bg="#ef4444", fg="white", font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, padx=10, pady=2, command=self.stop_server, state=tk.DISABLED, cursor="hand2"
        )
        self.btn_stop.pack(side=tk.LEFT, padx=3)

        # Vertical Divider
        tk.Frame(controls_row, bg="#e2e8f0", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=4)

        # Frame 2: Thresholds Persistence
        sec2 = tk.Frame(controls_row, bg="#ffffff", padx=8, pady=6)
        sec2.pack(side=tk.LEFT, fill=tk.Y)

        lbl_s2 = tk.Label(sec2, text="NGƯỠNG CẢNH BÁO (%)", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff")
        lbl_s2.pack(anchor="w", pady=(0, 4))

        f_th = tk.Frame(sec2, bg="#ffffff")
        f_th.pack(anchor="w")

        tk.Label(f_th, text="CPU:", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT)
        self.ent_cpu_thresh = ttk.Entry(f_th, width=5)
        self.ent_cpu_thresh.pack(side=tk.LEFT, padx=(3, 8))

        tk.Label(f_th, text="RAM:", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT)
        self.ent_ram_thresh = ttk.Entry(f_th, width=5)
        self.ent_ram_thresh.pack(side=tk.LEFT, padx=(3, 8))

        tk.Label(f_th, text="Disk:", font=("Segoe UI", 8), bg="#ffffff", fg="#64748b").pack(side=tk.LEFT)
        self.ent_disk_thresh = ttk.Entry(f_th, width=5)
        self.ent_disk_thresh.pack(side=tk.LEFT, padx=(3, 10))

        btn_save = tk.Button(
            f_th, text="💾 Lưu CSDL", bg="#2563eb", fg="white", font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, padx=8, pady=2, command=self.save_thresholds_gui, cursor="hand2"
        )
        btn_save.pack(side=tk.LEFT)

        # Vertical Divider
        tk.Frame(controls_row, bg="#e2e8f0", width=1).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=4)

        # Frame 3: Quick Navigation Actions
        sec3 = tk.Frame(controls_row, bg="#ffffff", padx=8, pady=6)
        sec3.pack(side=tk.RIGHT, fill=tk.Y, padx=8)

        lbl_s3 = tk.Label(sec3, text="TIỆN ÍCH & TRÌNH DUYỆT", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff")
        lbl_s3.pack(anchor="w", pady=(0, 4))

        f_actions = tk.Frame(sec3, bg="#ffffff")
        f_actions.pack(anchor="w")

        btn_web = tk.Button(
            f_actions, text="🌐 Mở Web Dashboard", bg="#3b82f6", fg="white", font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, padx=8, pady=2, command=self._open_web_dashboard, cursor="hand2"
        )
        btn_web.pack(side=tk.LEFT, padx=3)

        btn_sim = tk.Button(
            f_actions, text="🚀 Giả Lập Tải", bg="#8b5cf6", fg="white", font=("Segoe UI", 8, "bold"),
            relief=tk.FLAT, padx=8, pady=2, command=self._run_simulator_thread, cursor="hand2"
        )
        btn_sim.pack(side=tk.LEFT, padx=3)

        # 3. Middle Section: Monitored Nodes Treeview
        tree_container = tk.Frame(main_content, bg="#ffffff", bd=1, relief="solid")
        tree_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tree_header = tk.Frame(tree_container, bg="#ffffff", padx=12, pady=6)
        tree_header.pack(fill=tk.X)
        tk.Label(tree_header, text="DANH SÁCH MÁY CON PHÂN TÁN (AGENT NODES)", font=("Segoe UI", 9, "bold"), fg="#1e293b", bg="#ffffff").pack(side=tk.LEFT)
        self.lbl_tree_count = tk.Label(tree_header, text="Đang đồng bộ...", font=("Segoe UI", 8), fg="#64748b", bg="#ffffff")
        self.lbl_tree_count.pack(side=tk.RIGHT)

        tree_table_frame = tk.Frame(tree_container, bg="#ffffff")
        tree_table_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        columns = ("status", "agent_id", "hostname", "ip", "os", "cores", "ram", "last_seen")
        self.tree = ttk.Treeview(tree_table_frame, columns=columns, show="headings", height=5)
        
        self.tree.heading("status", text="Trạng Thái")
        self.tree.heading("agent_id", text="Agent ID")
        self.tree.heading("hostname", text="Hostname")
        self.tree.heading("ip", text="Địa Chỉ IP")
        self.tree.heading("os", text="Hệ Điều Hành")
        self.tree.heading("cores", text="Số Core")
        self.tree.heading("ram", text="RAM (GB)")
        self.tree.heading("last_seen", text="Lần Cuối Giao Tiếp")

        self.tree.column("status", width=95, anchor=tk.CENTER)
        self.tree.column("agent_id", width=120, anchor=tk.W)
        self.tree.column("hostname", width=130, anchor=tk.W)
        self.tree.column("ip", width=110, anchor=tk.CENTER)
        self.tree.column("os", width=140, anchor=tk.W)
        self.tree.column("cores", width=65, anchor=tk.CENTER)
        self.tree.column("ram", width=75, anchor=tk.CENTER)
        self.tree.column("last_seen", width=155, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(tree_table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Cấu hình màu cho status tags
        self.tree.tag_configure("online_tag", foreground="#059669", font=("Segoe UI", 9, "bold"))
        self.tree.tag_configure("offline_tag", foreground="#94a3b8")

        # 4. Bottom Section: Terminal Style Event Console
        console_container = tk.Frame(main_content, bg="#090d16", bd=1, relief="solid")
        console_container.pack(fill=tk.BOTH, expand=True)

        console_bar = tk.Frame(console_container, bg="#111827", padx=10, pady=4)
        console_bar.pack(fill=tk.X)
        tk.Label(console_bar, text="NHẬT KÝ HỆ THỐNG THỜI GIAN THỰC (SERVER CONSOLE)", font=("Segoe UI", 8, "bold"), fg="#9ca3af", bg="#111827").pack(side=tk.LEFT)
        
        btn_clear = tk.Button(
            console_bar, text="Xóa Log", font=("Segoe UI", 7), bg="#1f2937", fg="#d1d5db", relief=tk.FLAT,
            command=self._clear_console, cursor="hand2"
        )
        btn_clear.pack(side=tk.RIGHT)

        self.txt_log = scrolledtext.ScrolledText(
            console_container, height=6, font=("JetBrains Mono", 8), bg="#090d16", fg="#e2e8f0",
            insertbackground="white", bd=0
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # Cấu hình màu các tag console
        self.txt_log.tag_config("INFO", foreground="#38bdf8")
        self.txt_log.tag_config("SUCCESS", foreground="#34d399")
        self.txt_log.tag_config("WARN", foreground="#fbbf24")
        self.txt_log.tag_config("ERROR", foreground="#f87171")
        self.txt_log.tag_config("TIME", foreground="#64748b")

        self.log_message("Admin Panel đã sẵn sàng. CSDL SQLite và cấu hình ngưỡng đã được nạp.", "INFO")

    def _create_kpi_card(self, parent, title, default_val, accent_color, col_idx):
        card = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid")
        card.grid(row=0, column=col_idx, padx=4, sticky="nsew")
        parent.grid_columnconfigure(col_idx, weight=1)

        # Top Accent Line
        tk.Frame(card, bg=accent_color, height=3).pack(fill=tk.X)

        inner = tk.Frame(card, bg="#ffffff", padx=12, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        tk.Label(inner, text=title, font=("Segoe UI", 8, "bold"), fg="#64748b", bg="#ffffff").pack(anchor="w")
        val_lbl = tk.Label(inner, text=default_val, font=("Segoe UI", 14, "bold"), fg="#0f172a", bg="#ffffff")
        val_lbl.pack(anchor="w", pady=(2, 0))
        return val_lbl

    def _load_saved_settings(self):
        """Nạp ngưỡng từ CSDL vào giao diện."""
        try:
            th = load_thresholds()
            self.ent_cpu_thresh.delete(0, tk.END)
            self.ent_cpu_thresh.insert(0, str(th["cpu"]))
            self.ent_ram_thresh.delete(0, tk.END)
            self.ent_ram_thresh.insert(0, str(th["ram"]))
            self.ent_disk_thresh.delete(0, tk.END)
            self.ent_disk_thresh.insert(0, str(th["disk"]))
        except Exception as e:
            self.log_message(f"Không thể đọc ngưỡng từ CSDL: {e}", "WARN")

    def log_message(self, msg: str, level: str = "INFO"):
        """Ghi nhật ký hệ thống kèm mốc thời gian và màu sắc."""
        now = time.strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{now}] ", "TIME")
        self.txt_log.insert(tk.END, f"[{level}] ", level)
        self.txt_log.insert(tk.END, f"{msg}\n")
        self.txt_log.see(tk.END)

    def _clear_console(self):
        self.txt_log.delete("1.0", tk.END)

    def _copy_lan_ip(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.local_ip)
        messagebox.showinfo("Đã Sao Chép", f"Đã sao chép IP LAN vào Clipboard:\n{self.local_ip}")

    def _set_server_ui_running(self, running: bool):
        if running:
            self.lbl_server_pill.config(text="● SERVER ĐANG CHẠY", fg="#10b981")
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.ent_host.config(state=tk.DISABLED)
            self.ent_port.config(state=tk.DISABLED)
        else:
            self.lbl_server_pill.config(text="● SERVER ĐANG TẮT", fg="#ef4444")
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.ent_host.config(state=tk.NORMAL)
            self.ent_port.config(state=tk.NORMAL)

    def start_server(self):
        """Khởi động TCP Socket Server."""
        try:
            host = self.ent_host.get().strip()
            port = int(self.ent_port.get().strip())
        except ValueError:
            messagebox.showerror("Lỗi Cổng Mạng", "Cổng mạng (Port) phải là một số nguyên dương hợp lệ!")
            return

        self.server_manager.host = host
        self.server_manager.port = port
        success = self.server_manager.start()

        if success:
            self._set_server_ui_running(True)
            self.log_message(f"TCP Socket Server đã mở lắng nghe trên {host}:{port} (Multi-interface/LAN)", "SUCCESS")
        else:
            messagebox.showerror("Lỗi Khởi Động", f"Không thể bind Socket trên {host}:{port}. Cổng có thể đang bị chiếm dụng.")
            self.log_message(f"Khởi động Server thất bại trên {host}:{port}", "ERROR")

    def stop_server(self):
        """Dừng Socket Server."""
        self.server_manager.stop()
        self._set_server_ui_running(False)
        self.log_message("TCP Socket Server đã ngừng nhận kết nối mới.", "WARN")

    def save_thresholds_gui(self):
        """Lưu các ngưỡng cảnh báo vào CSDL SQLite."""
        try:
            cpu_th = float(self.ent_cpu_thresh.get().strip())
            ram_th = float(self.ent_ram_thresh.get().strip())
            disk_th = float(self.ent_disk_thresh.get().strip())

            if not (0 <= cpu_th <= 100 and 0 <= ram_th <= 100 and 0 <= disk_th <= 100):
                messagebox.showerror("Lỗi Giá Trị", "Các ngưỡng phải nằm trong khoảng từ 0% đến 100%!")
                return

            save_thresholds(cpu_th, ram_th, disk_th)
            self.server_manager.refresh_thresholds()

            self.log_message(f"Đã lưu ngưỡng vào SQLite: CPU={cpu_th}%, RAM={ram_th}%, Disk={disk_th}%", "SUCCESS")
            messagebox.showinfo("Thành Công", "Đã lưu cài đặt ngưỡng thành công vào CSDL SQLite!")
        except ValueError:
            messagebox.showerror("Lỗi Nhập Liệu", "Vui lòng nhập giá trị số thực hợp lệ cho ngưỡng.")

    def _open_web_dashboard(self):
        """Mở Web Dashboard trên trình duyệt mặc định."""
        url = f"http://127.0.0.1:{config.FLASK_PORT}"
        self.log_message(f"Đang mở Web Dashboard tại {url}", "INFO")
        webbrowser.open(url)

    def _run_simulator_thread(self):
        """Kích hoạt mô phỏng tải trong một luồng riêng."""
        def sim_task():
            self.log_message("Bắt đầu chạy kịch bản mô phỏng 3 máy con (tiêm tải dị biệt)...", "WARN")
            from experiments.workload_simulator import run_multi_agent_simulation
            run_multi_agent_simulation(num_agents=3, duration_sec=15, anomaly_ratio=0.5)
            self.log_message("Kịch bản mô phỏng đã kết thúc.", "SUCCESS")

        t = threading.Thread(target=sim_task, daemon=True)
        t.start()

    def _periodic_ui_refresh(self):
        """Luồng ngầm định kỳ 2 giây đồng bộ số liệu và danh sách agent từ SQLite."""
        while self.is_monitoring_gui:
            try:
                active_conn = self.server_manager.active_connections
                total_pkts = self.server_manager.total_packets_received
                summary = get_system_summary()
                agents = get_agents()

                def update_labels():
                    self.card_clients.config(text=f"{active_conn} Client")
                    self.card_packets.config(text=f"{total_pkts:,}")
                    online_cnt = summary.get("online_agents", 0)
                    total_cnt = summary.get("total_agents", 0)
                    self.card_agents.config(text=f"{online_cnt} / {total_cnt}")
                    self.card_alerts.config(text=str(summary.get("total_anomalies", 0)))
                    self.lbl_tree_count.config(text=f"{online_cnt} Online, {total_cnt - online_cnt} Offline")

                    # Đồng bộ trạng thái chạy của server nếu khởi động từ bên ngoài
                    if self.server_manager.running and str(self.lbl_server_pill["text"]).startswith("● SERVER ĐANG TẮT"):
                        self._set_server_ui_running(True)
                    elif not self.server_manager.running and str(self.lbl_server_pill["text"]).startswith("● SERVER ĐANG CHẠY"):
                        self._set_server_ui_running(False)

                self.root.after(0, update_labels)

                def update_tree():
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    for a in agents:
                        status = a.get("status", "OFFLINE")
                        tag = "online_tag" if status == "ONLINE" else "offline_tag"
                        status_display = "● ONLINE" if status == "ONLINE" else "○ OFFLINE"

                        self.tree.insert("", tk.END, values=(
                            status_display,
                            a.get("agent_id"),
                            a.get("hostname"),
                            a.get("ip_address"),
                            a.get("os"),
                            a.get("cpu_cores"),
                            f"{a.get('total_ram_gb', 0)} GB",
                            a.get("last_seen")
                        ), tags=(tag,))

                self.root.after(0, update_tree)
            except Exception:
                pass

            time.sleep(2.0)

    def _on_closing(self):
        self.is_monitoring_gui = False
        if self.server_manager.running:
            self.server_manager.stop()
        self.root.destroy()

def run_tkinter_app(server_manager: Optional[SocketServerManager] = None):
    root = tk.Tk()
    app = AdminControlPanelApp(root, server_manager=server_manager)
    root.mainloop()

if __name__ == "__main__":
    run_tkinter_app()
