/* ==========================================================================
   Server Sentinel - Real-time Dashboard Chart & Data Poller
   ========================================================================== */

let cpuChart, ramChart, diskChart, netChart;
let pollInterval = 3000;
let pollTimer = null;
let isPaused = false;
let netMode = 'speed'; // 'speed' (Mbps) hoặc 'volume' (MB)
let currentThresholds = { cpu: 85, ram: 85, disk: 90 };

// Cấu hình chung cho Chart.js
function getChartOptions(maxVal = 100, yLabel = "%") {
    return {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 350 },
        interaction: {
            mode: 'index',
            intersect: false,
        },
        scales: {
            x: {
                grid: { display: false },
                ticks: {
                    maxTicksLimit: 7,
                    font: { size: 10, family: "'JetBrains Mono', monospace" },
                    color: "#94a3b8"
                }
            },
            y: {
                beginAtZero: true,
                max: maxVal !== null ? maxVal : undefined,
                grid: { color: "#f1f5f9" },
                ticks: {
                    font: { size: 10, family: "'Inter', sans-serif" },
                    color: "#64748b",
                    callback: function(value) {
                        return value + (yLabel ? " " + yLabel : "");
                    }
                }
            }
        },
        plugins: {
            legend: {
                position: "top",
                labels: {
                    boxWidth: 10,
                    usePointStyle: true,
                    font: { size: 11, family: "'Inter', sans-serif" }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                titleFont: { size: 11, family: "'Inter', sans-serif" },
                bodyFont: { size: 11, family: "'Inter', sans-serif" },
                padding: 8,
                cornerRadius: 8
            }
        }
    };
}

function initCharts() {
    // 1. CPU Chart
    const ctxCpu = document.getElementById("cpuChart").getContext("2d");
    const gradientCpu = ctxCpu.createLinearGradient(0, 0, 0, 200);
    gradientCpu.addColorStop(0, "rgba(245, 158, 11, 0.25)");
    gradientCpu.addColorStop(1, "rgba(245, 158, 11, 0.0)");

    cpuChart = new Chart(ctxCpu, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "CPU Usage (%)",
                    borderColor: "#f59e0b",
                    backgroundColor: gradientCpu,
                    data: [],
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                },
                {
                    label: "Ngưỡng Cảnh Báo",
                    borderColor: "rgba(239, 68, 68, 0.7)",
                    borderDash: [5, 5],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    data: [],
                    fill: false
                }
            ]
        },
        options: getChartOptions(100, "%")
    });

    // 2. RAM Chart
    const ctxRam = document.getElementById("ramChart").getContext("2d");
    const gradientRam = ctxRam.createLinearGradient(0, 0, 0, 200);
    gradientRam.addColorStop(0, "rgba(37, 99, 235, 0.25)");
    gradientRam.addColorStop(1, "rgba(37, 99, 235, 0.0)");

    ramChart = new Chart(ctxRam, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "RAM Usage (%)",
                    borderColor: "#2563eb",
                    backgroundColor: gradientRam,
                    data: [],
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                },
                {
                    label: "Ngưỡng Cảnh Báo",
                    borderColor: "rgba(37, 99, 235, 0.6)",
                    borderDash: [5, 5],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    data: [],
                    fill: false
                }
            ]
        },
        options: getChartOptions(100, "%")
    });

    // 3. Disk Chart
    const ctxDisk = document.getElementById("diskChart").getContext("2d");
    const gradientDisk = ctxDisk.createLinearGradient(0, 0, 0, 200);
    gradientDisk.addColorStop(0, "rgba(16, 185, 129, 0.2)");
    gradientDisk.addColorStop(1, "rgba(16, 185, 129, 0.0)");

    diskChart = new Chart(ctxDisk, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Disk Usage (%)",
                    borderColor: "#10b981",
                    backgroundColor: gradientDisk,
                    data: [],
                    fill: true,
                    tension: 0.2,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 5
                },
                {
                    label: "Ngưỡng Cảnh Báo",
                    borderColor: "rgba(16, 185, 129, 0.6)",
                    borderDash: [5, 5],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    data: [],
                    fill: false
                }
            ]
        },
        options: getChartOptions(100, "%")
    });

    // 4. Network Chart
    const ctxNet = document.getElementById("netChart").getContext("2d");
    netChart = new Chart(ctxNet, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Sent",
                    borderColor: "#8b5cf6",
                    backgroundColor: "rgba(139, 92, 246, 0.1)",
                    data: [],
                    borderWidth: 1.8,
                    pointRadius: 2,
                    tension: 0.2
                },
                {
                    label: "Recv",
                    borderColor: "#06b6d4",
                    backgroundColor: "rgba(6, 182, 212, 0.1)",
                    data: [],
                    borderWidth: 1.8,
                    pointRadius: 2,
                    tension: 0.2
                }
            ]
        },
        options: getChartOptions(null, netMode === 'speed' ? 'Mbps' : 'MB')
    });
}

function setNetChartMode(mode) {
    netMode = mode;
    document.getElementById("btnNetSpeed").classList.toggle("active", mode === 'speed');
    document.getElementById("btnNetVolume").classList.toggle("active", mode === 'volume');
    
    netChart.options = getChartOptions(null, mode === 'speed' ? 'Mbps' : 'MB');
    netChart.data.datasets[0].label = mode === 'speed' ? "Tốc độ gửi (Mbps)" : "Dung lượng gửi (MB)";
    netChart.data.datasets[1].label = mode === 'speed' ? "Tốc độ nhận (Mbps)" : "Dung lượng nhận (MB)";
    updateDashboard();
}

async function updateDashboard() {
    if (isPaused) return;

    const select = document.getElementById("agentSelect");
    const agentId = select ? select.value.trim() : "";

    try {
        // 1. Cập nhật Ngưỡng
        const resTh = await fetch("/api/settings");
        if (resTh.ok) {
            currentThresholds = await resTh.json();
            document.getElementById("badgeCpuTh").textContent = currentThresholds.cpu;
            document.getElementById("badgeRamTh").textContent = currentThresholds.ram;
            document.getElementById("badgeDiskTh").textContent = currentThresholds.disk;
        }

        // 2. Cập nhật KPI Summary
        const resSum = await fetch("/api/summary");
        if (resSum.ok) {
            const sum = await resSum.json();
            document.getElementById("kpi-online-agents").textContent = sum.online_agents;
            document.getElementById("kpi-total-agents").textContent = sum.total_agents;
            document.getElementById("kpi-online-badge").textContent = `${sum.online_agents} Online`;
            document.getElementById("kpi-offline-badge").textContent = `${sum.offline_agents} Offline`;
            document.getElementById("kpi-cpu").textContent = `${sum.avg_cpu}%`;
            document.getElementById("kpi-cpu-bar").style.width = `${Math.min(sum.avg_cpu, 100)}%`;
            document.getElementById("kpi-ram").textContent = `${sum.avg_ram}%`;
            document.getElementById("kpi-ram-bar").style.width = `${Math.min(sum.avg_ram, 100)}%`;
            document.getElementById("kpi-anomalies").textContent = sum.total_anomalies;
            document.getElementById("kpi-logs").textContent = sum.total_logs;
        }

        // 3. Cập nhật Biểu đồ chuỗi thời gian
        let url = `/api/metrics/recent?limit=40`;
        if (agentId) url += `&agent_id=${encodeURIComponent(agentId)}`;
        
        const resLogs = await fetch(url);
        if (resLogs.ok) {
            const logs = await resLogs.json();
            if (logs.length > 0) {
                const labels = logs.map(l => l.timestamp.split(" ")[1] || l.timestamp);
                const cpuData = logs.map(l => l.cpu_usage);
                const ramData = logs.map(l => l.ram_usage);
                const diskData = logs.map(l => l.disk_usage);

                // Dữ liệu ngưỡng nằm ngang
                const cpuThreshLine = logs.map(() => currentThresholds.cpu);
                const ramThreshLine = logs.map(() => currentThresholds.ram);
                const diskThreshLine = logs.map(() => currentThresholds.disk);

                // Network data theo chế độ
                let netSent, netRecv;
                if (netMode === 'speed') {
                    netSent = logs.map(l => l.net_sent_speed_mbps !== undefined ? l.net_sent_speed_mbps : 0);
                    netRecv = logs.map(l => l.net_recv_speed_mbps !== undefined ? l.net_recv_speed_mbps : 0);
                } else {
                    netSent = logs.map(l => l.net_sent_mb !== undefined ? l.net_sent_mb : 0);
                    netRecv = logs.map(l => l.net_recv_mb !== undefined ? l.net_recv_mb : 0);
                }

                // Cập nhật nhãn hiện tại
                const latest = logs[logs.length - 1];
                document.getElementById("currentCpuVal").textContent = `${latest.cpu_usage}%`;
                document.getElementById("currentRamVal").textContent = `${latest.ram_usage}%`;
                document.getElementById("currentDiskVal").textContent = `${latest.disk_usage}%`;

                // Update CPU Chart
                cpuChart.data.labels = labels;
                cpuChart.data.datasets[0].data = cpuData;
                cpuChart.data.datasets[1].data = cpuThreshLine;
                cpuChart.update();

                // Update RAM Chart
                ramChart.data.labels = labels;
                ramChart.data.datasets[0].data = ramData;
                ramChart.data.datasets[1].data = ramThreshLine;
                ramChart.update();

                // Update Disk Chart
                diskChart.data.labels = labels;
                diskChart.data.datasets[0].data = diskData;
                diskChart.data.datasets[1].data = diskThreshLine;
                diskChart.update();

                // Update Net Chart
                netChart.data.labels = labels;
                netChart.data.datasets[0].data = netSent;
                netChart.data.datasets[1].data = netRecv;
                netChart.update();
            }
        }

        // 4. Cập nhật Bảng Máy Chủ (Agent List Table)
        const resAgents = await fetch("/api/agents");
        if (resAgents.ok) {
            const agents = await resAgents.json();
            renderAgentsTable(agents);
        }

    } catch (err) {
        console.warn("Lỗi cập nhật dashboard:", err);
    }
}

function renderAgentsTable(agents) {
    const tbody = document.getElementById("agentsTableBody");
    if (!tbody) return;

    if (!agents || agents.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-muted">Chưa có máy chủ nào đăng ký. Hãy chạy Client Agent hoặc bấm nút Mô Phỏng Tải ở trên!</td></tr>`;
        return;
    }

    let html = "";
    for (const a of agents) {
        const isOnline = (a.status === 'ONLINE');
        const badgeHtml = isOnline 
            ? `<span class="badge badge-online"><span class="pulse-dot-online"></span>ONLINE</span>`
            : `<span class="badge badge-offline"><span class="dot-offline"></span>OFFLINE</span>`;

        html += `
            <tr>
                <td>${badgeHtml}</td>
                <td class="fw-bold text-primary">${a.agent_id}</td>
                <td>${a.hostname || 'Unknown'}</td>
                <td><code class="ip-tag">${a.ip_address || '127.0.0.1'}</code></td>
                <td><small>${a.os || 'Unknown'}</small></td>
                <td><small class="text-secondary">${a.cpu_cores || 1} Cores &middot; ${a.total_ram_gb || 0} GB RAM</small></td>
                <td><small class="text-muted">${a.last_seen || '-'}</small></td>
                <td class="text-end">
                    <a href="/analytics?agent_id=${encodeURIComponent(a.agent_id)}" class="btn btn-sm btn-light border py-1 px-2" title="Xem phân tích máy này">
                        <i class="fa-solid fa-chart-line text-primary"></i>
                    </a>
                </td>
            </tr>
        `;
    }
    tbody.innerHTML = html;
}

function setRefreshInterval(ms, btn) {
    pollInterval = ms;
    if (pollTimer) clearInterval(pollTimer);
    
    // Update active button state
    document.querySelectorAll(".btn-group button").forEach(b => b.classList.remove("active"));
    if (btn) btn.classList.add("active");

    const sec = ms / 1000;
    document.getElementById("refreshRateText").textContent = `${sec}s`;

    if (!isPaused) {
        pollTimer = setInterval(updateDashboard, pollInterval);
    }
}

function togglePause(btn) {
    isPaused = !isPaused;
    if (isPaused) {
        btn.innerHTML = `<i class="fa-solid fa-play"></i>`;
        btn.classList.add("btn-warning", "text-dark");
        btn.classList.remove("btn-outline-secondary");
        document.getElementById("refreshRateText").textContent = "Tạm dừng";
    } else {
        btn.innerHTML = `<i class="fa-solid fa-pause"></i>`;
        btn.classList.remove("btn-warning", "text-dark");
        btn.classList.add("btn-outline-secondary");
        document.getElementById("refreshRateText").textContent = `${pollInterval / 1000}s`;
        updateDashboard();
    }
}

async function triggerSimulation() {
    const btn = document.getElementById("btnSimulate");
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Đang chạy mô phỏng...`;

    const placeholder = document.getElementById("dashboardAlertPlaceholder");
    try {
        const res = await fetch("/api/simulate", { method: "POST" });
        const data = await res.json();
        if (data.success) {
            placeholder.innerHTML = `
                <div class="alert alert-success alert-dismissible fade show shadow-sm py-2 mb-3" role="alert">
                    <i class="fa-solid fa-circle-check me-2"></i>${data.message}
                    <button type="button" class="btn-close py-2" data-bs-dismiss="alert"></button>
                </div>
            `;
            setTimeout(updateDashboard, 1500);
        } else {
            placeholder.innerHTML = `<div class="alert alert-danger py-2 mb-3">${data.error}</div>`;
        }
    } catch (e) {
        placeholder.innerHTML = `<div class="alert alert-danger py-2 mb-3">Lỗi: ${e}</div>`;
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt me-1"></i> Mô Phỏng Tải (Demo)`;
        }, 3000);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initCharts();
    updateDashboard();
    pollTimer = setInterval(updateDashboard, pollInterval);
    document.getElementById("agentSelect")?.addEventListener("change", updateDashboard);
});
