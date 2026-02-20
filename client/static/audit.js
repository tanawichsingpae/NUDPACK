let currentAction = "";
let currentSearch = "";
let currentDate = "";

const ACTION_MAP = {
    "filter-all": "",
    "filter-received": "ได้รับพัสดุ",
    "filter-confirmed": "ยืนยันการรับพัสดุ",
    "filter-deleted": "ลบรายการพัสดุ",
    "filter-added": "เพิ่มหมายเลขพัสดุ",
    "filter-confirmed-added": "ยืนยันการเพิ่มหมายเลขพัสดุ",
};

document.addEventListener("DOMContentLoaded", () => {
    loadAuditLogs();
});

/* ------------------------------
  Load audit logs
-------------------------------- */
async function loadAuditLogs() {
  const container = document.getElementById("audit-list");
  if (!container) return;

  container.innerHTML = skeletonLoading();

  const params = new URLSearchParams();
  if (currentAction) params.append("action", currentAction);
  if (currentSearch) params.append("q", currentSearch);
  if (currentDate) params.append("date", currentDate);

  const res = await fetch(`/api/audit_logs?${params.toString()}`, {
    credentials: "include",
  });

  if (!res.ok) {
    container.innerHTML = errorBox("โหลด Audit Log ไม่ได้");
    return;
  }

  const logs = await res.json();

  if (!logs.length) {
    container.innerHTML = emptyState();
    return;
  }

  container.innerHTML = logs.map(renderLogCard).join("");
}

/* ------------------------------
  Render card
-------------------------------- */
function renderLogCard(log) {
    return `
  <div class="bg-white dark:bg-[#2d1f18] p-4 rounded-xl shadow-sm border border-transparent hover:border-primary/20 transition">
    <div class="flex items-start justify-between mb-3">
      <div>
        <p class="text-sm font-bold">${escape(log.user || "System")}</p>
        
      </div>
      <span class="text-[11px] px-2 py-1 rounded-full bg-[#f4ebe6] dark:bg-[#3d2b21] text-[#9e6747]">
        ${formatDateTime(log.timestamp)}
      </span>
    </div>

    <div class="flex items-center gap-2 mb-3">
      ${actionBadge(log.action)}
      <span class="text-sm font-mono font-medium">
        <p class="text-[10px] uppercase tracking-wide text-[#9e6747] dark:text-[#cbb0a0]">
          
        </p>
      </span>
    </div>

    <details class="group">
      <summary class="cursor-pointer text-[11px] font-semibold text-primary uppercase flex items-center justify-between">
        ดูรายละเอียด
        <span class="material-symbols-outlined transition-transform group-open:rotate-90">
          chevron_right
        </span>
      </summary>

      <div class="mt-3 bg-[#fcf9f8] dark:bg-[#1c120d] rounded-lg p-3 text-[11px] border border-[#f4ebe6] dark:border-[#3d2b21] space-y-1">
        ${renderDetails(log.details)}
      </div>
    </details>
  </div>
  `;
}

/* ------------------------------
  Helpers
-------------------------------- */
function actionBadge(action) {
    const map = {
        pickup: "bg-green-500/10 text-green-600",
        pickup_recipient: "bg-green-500/10 text-green-600",
        create: "bg-blue-500/10 text-blue-600",
        delete: "bg-red-500/10 text-red-600",
        update: "bg-yellow-500/10 text-yellow-600",
    };

    const cls = map[action] || "bg-slate-500/10 text-slate-600";

    return `
    <span class="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase ${cls}">
      ${action}
    </span>
  `;
}
function renderDetails(details) {
    if (!details) {
        return `<p class="italic text-[#9e6747]">ไม่มีรายละเอียด</p>`;
    }

    const safe = escape(details);

    // ถ้ามี = แสดงแบบ key/value
    if (safe.includes("=")) {
        return safe
            .split(",")
            .map((d) => {
                const parts = d.split("=");
                return `
                <div class="flex justify-between">
                    <span class="text-[#9e6747]">${parts[0] || ""}</span>
                    <span class="font-mono">${parts[1] || ""}</span>
                </div>
                `;
            })
            .join("");
    }

    // ถ้าไม่มี = ให้แสดงแบบหลายบรรทัดตาม \n
    return safe
        .split("\n")
        .map(
            (line) => `<div class="font-mono">${line}</div>`
        )
        .join("");
}

function formatDateTime(dateStr) {
    if (!dateStr) return "-";

    const d = new Date(dateStr);

    return d.toLocaleString("th-TH-u-ca-gregory", {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function escape(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

/* ------------------------------
  UI states
-------------------------------- */
function skeletonLoading() {
    return `
    <div class="animate-pulse space-y-3">
      <div class="h-20 bg-slate-200 dark:bg-[#3d2b21] rounded-xl"></div>
      <div class="h-20 bg-slate-200 dark:bg-[#3d2b21] rounded-xl"></div>
      <div class="h-20 bg-slate-200 dark:bg-[#3d2b21] rounded-xl"></div>
    </div>
  `;
}

function emptyState() {
    return `
    <div class="text-center py-10 text-[#9e6747]">
      <span class="material-symbols-outlined text-4xl mb-2">history</span>
      <p class="text-sm font-semibold">ไม่พบรายการ</p>
    </div>
  `;
}

function errorBox(msg) {
    return `
    <div class="text-center py-10 text-red-500 font-semibold">
      ${msg}
    </div>
  `;
}
document.getElementById("search-input")?.addEventListener("input", (e) => {
    currentSearch = e.target.value.trim();
    loadAuditLogs();
});
document.getElementById("selected-date")?.addEventListener("change", (e) => {
    currentDate = e.target.value; // yyyy-mm-dd
    loadAuditLogs();
});

Object.keys(ACTION_MAP).forEach((id) => {
    const btn = document.getElementById(id);
    if (!btn) return;

    btn.addEventListener("click", () => {
        currentAction = ACTION_MAP[id];
        setActiveFilter(btn);
        loadAuditLogs();
    });
});
function setActiveFilter(activeBtn) {
    document.querySelectorAll(
        "#filter-all, #filter-received, #filter-confirmed, #filter-deleted, #filter-added, #filter-confirmed-added"
    ).forEach((btn) => {
        btn.classList.remove("bg-orange-400", "text-white", "shadow-primary/30");
        btn.classList.add(
            "bg-white",
            "dark:bg-[#2d1f18]",
            "text-[#1c120d]",
            "dark:text-white",
            "border"
        );
    });

    activeBtn.classList.remove(
        "bg-white",
        "dark:bg-[#2d1f18]",
        "text-[#1c120d]",
        "dark:text-white",
        "border"
    );
    activeBtn.classList.add(
        "bg-orange-400",
        "text-white",
        "shadow-primary/30"
    );
}
document.getElementById("reload-audit").addEventListener("click", () => {
    loadAuditLogs();
});