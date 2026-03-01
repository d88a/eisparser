const USER_ID = 1;
const API_BASE = "/api";

const STATUS_LABELS = {
    raw: "Нужен ИИ-анализ (Этап 2)",
    ai_processing: "ИИ-анализ выполняется. Дождитесь результата",
    ai_ready: "Проверьте результат ИИ и сформируйте ссылку (Этап 3)",
    url_ready: "Готово к сбору объявлений (Этап 4)",
    user_selected: "Проверено оператором",
    stage4_done: "Готово: объявления собраны",
    stage4_error: "Ошибка Stage 4, повторите запуск",
};

let zakupkiNew = [];
let zakupkiAll = [];
let currentLimit = 10;

let allOffset = 0;
const allLimit = 20;
let allTotal = 0;

let pendingSaveItems = null;

document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    setupGlobalActions();
    updateStatsNew();
});

function setStage1Status(message, type = "info", options = {}) {
    const el = document.getElementById("stage1-status");
    if (!el) return;

    if (!message) {
        el.style.display = "none";
        el.className = "inline-status";
        el.textContent = "";
        return;
    }

    el.style.display = "block";
    el.className = `inline-status ${type === "info" ? "" : type}`.trim();

    if (options.allowHtml) el.innerHTML = message;
    else el.textContent = message;
}

function showSaveConfirmation(selectedItems) {
    pendingSaveItems = selectedItems;

    const message = `
        <div style="display:flex; flex-wrap:wrap; align-items:center; gap:10px;">
            <span>Подтвердите сохранение выбранных закупок: <strong>${selectedItems.length}</strong>.</span>
            <button id="confirm-save-yes" class="btn btn-sm btn-primary" style="padding:4px 10px;">Подтвердить</button>
            <button id="confirm-save-no" class="btn btn-sm" style="padding:4px 10px; background:#e2e8f0; color:#334155;">Отмена</button>
        </div>
    `;

    setStage1Status(message, "info", { allowHtml: true });

    document.getElementById("confirm-save-yes")?.addEventListener("click", runSaveSelectedConfirmed);
    document.getElementById("confirm-save-no")?.addEventListener("click", () => {
        pendingSaveItems = null;
        setStage1Status("Сохранение отменено.");
    });
}

function setupTabs() {
    const tabNew = document.getElementById("tab-new");
    const tabAll = document.getElementById("tab-all");
    const panelNew = document.getElementById("panel-new");
    const panelAll = document.getElementById("panel-all");

    tabNew.addEventListener("click", () => {
        tabNew.classList.add("active");
        tabAll.classList.remove("active");
        panelNew.classList.add("active");
        panelAll.classList.remove("active");
        updateStatsNew();
    });

    tabAll.addEventListener("click", () => {
        tabAll.classList.add("active");
        tabNew.classList.remove("active");
        panelAll.classList.add("active");
        panelNew.classList.remove("active");
        loadAllZakupki(true);
        updateStatsAll();
    });
}

async function loadNewList() {
    const response = await fetch(`${API_BASE}/stage1?user_id=${USER_ID}&limit=${currentLimit}`);
    if (!response.ok) throw new Error("Не удалось загрузить данные");

    const data = await response.json();
    const items = Array.isArray(data) ? data : data.items || [];
    zakupkiNew = items;
    renderNewTable(items);
    updateStatsNew();
}

async function loadAllZakupki(reset = false) {
    try {
        if (reset) {
            allOffset = 0;
            zakupkiAll = [];
            document.getElementById("zakupki-body-all").innerHTML = "";
        }

        const response = await fetch(`${API_BASE}/admin/zakupki_all?offset=${allOffset}&limit=${allLimit}`);
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`Ошибка ${response.status}: ${text}`);
        }

        const data = await response.json();
        const items = Array.isArray(data) ? data : data.items || [];
        allTotal = Array.isArray(data) ? items.length : data.total || 0;
        zakupkiAll = zakupkiAll.concat(items);

        renderAllTable(items, reset);
        updateStatsAll();

        allOffset += items.length;
        const btn = document.getElementById("btn-load-more-all");
        if (!Array.isArray(data) && allOffset < allTotal) {
            btn.style.display = "inline-block";
            btn.disabled = false;
        } else {
            btn.style.display = "none";
        }
    } catch (error) {
        console.error("Error:", error);
        setStage1Status(`Не удалось загрузить вкладку \"Все закупки\": ${error.message}`, "error");
    }
}

function renderNewTable(data) {
    const tbody = document.getElementById("zakupki-body-new");
    tbody.innerHTML = "";

    const items = Array.isArray(data) ? data : [];
    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:40px; color:#999">Нет данных. Нажмите "Показать новые закупки"</td></tr>';
        return;
    }

    items.forEach((item) => {
        const tr = document.createElement("tr");
        tr.dataset.reg = item.reg_number;
        const price = item.initial_price ? `${(item.initial_price / 1000000).toFixed(2)} млн` : "-";

        tr.innerHTML = `
            <td><input type="checkbox" class="row-select" name="select_reg" value="${item.reg_number}" onchange="updateSelectionStats()"></td>
            <td><a href="${item.link || "#"}" target="_blank">${item.reg_number}</a></td>
            <td title="${item.description || ""}">${item.description || "-"}</td>
            <td>${price}</td>
            <td>${item.bid_end_date || "-"}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderAllTable(items, reset) {
    const tbody = document.getElementById("zakupki-body-all");
    const safeItems = Array.isArray(items) ? items : [];

    if (reset && safeItems.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:40px; color:#999">Нет закупок в базе</td></tr>';
        return;
    }

    safeItems.forEach((item) => {
        const tr = document.createElement("tr");
        const price = item.initial_price ? `${(item.initial_price / 1000000).toFixed(2)} млн` : "-";
        const status = STATUS_LABELS[item.status] || item.status || "-";
        tr.innerHTML = `
            <td><a href="${item.link || "#"}" target="_blank">${item.reg_number}</a></td>
            <td title="${item.description || ""}">${item.description || "-"}</td>
            <td>${price}</td>
            <td>${item.bid_end_date || "-"}</td>
            <td>${status}</td>
        `;
        tbody.appendChild(tr);
    });
}

function toggleSelectAll(source) {
    const checkboxes = document.querySelectorAll(".row-select");
    checkboxes.forEach((cb) => {
        cb.checked = source.checked;
    });
    updateSelectionStats();
}

function updateSelectionStats() {
    const selected = document.querySelectorAll(".row-select:checked").length;
    const btn = document.getElementById("btn-save-selected");
    document.getElementById("stat-selected").textContent = selected;

    if (selected > 0) {
        btn.textContent = `Скачать и сохранить выбранные (${selected})`;
        btn.disabled = false;
    } else {
        btn.textContent = "Скачать и сохранить выбранные";
        btn.disabled = true;
    }
}

function updateStatsNew() {
    const total = zakupkiNew.length;
    document.getElementById("stat-total").textContent = total;
    document.getElementById("stat-selected").textContent = 0;

    const btn = document.getElementById("btn-save-selected");
    btn.textContent = "Скачать и сохранить выбранные";
    btn.disabled = true;
}

function updateStatsAll() {
    document.getElementById("stat-total").textContent = allTotal || zakupkiAll.length;
    document.getElementById("stat-selected").textContent = 0;
}

async function runSaveSelected(items, triggerBtn) {
    triggerBtn.disabled = true;
    setStage1Status("Скачиваю документы и сохраняю выбранные закупки...");

    try {
        const response = await fetch(`${API_BASE}/actions/save_stage1_selected`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: USER_ID,
                items,
            }),
        });

        const result = await response.json();
        if (result.status === "ok") {
            setStage1Status(result.message || "Выбранные закупки сохранены.", "success");
            document.getElementById("select-all").checked = false;
            document.querySelectorAll(".row-select:checked").forEach((cb) => {
                cb.checked = false;
            });
            updateSelectionStats();
            pendingSaveItems = null;
        } else {
            setStage1Status(`Не удалось сохранить: ${result.message || "неизвестная ошибка"}`, "error");
        }
    } catch (error) {
        console.error(error);
        setStage1Status("Ошибка соединения при сохранении закупок.", "error");
    } finally {
        triggerBtn.disabled = false;
    }
}

async function runSaveSelectedConfirmed() {
    const btn = document.getElementById("btn-save-selected");
    if (!btn) return;

    if (!pendingSaveItems || pendingSaveItems.length === 0) {
        setStage1Status("Список выбранных закупок пуст.", "error");
        return;
    }

    await runSaveSelected(pendingSaveItems, btn);
}

function setupGlobalActions() {
    document.getElementById("btn-save-selected").addEventListener("click", async () => {
        const checkboxes = document.querySelectorAll(".row-select:checked");
        const selectedIds = Array.from(checkboxes).map((cb) => cb.value);

        if (selectedIds.length === 0) {
            setStage1Status("Отметьте закупки галочками, чтобы сохранить их.", "error");
            return;
        }

        const items = zakupkiNew
            .filter((z) => selectedIds.includes(z.reg_number))
            .map((z) => ({
                reg_number: z.reg_number,
                description: z.description || "",
                update_date: z.update_date || "",
                bid_end_date: z.bid_end_date || "",
                initial_price: z.initial_price ?? null,
                link: z.link || "",
            }));

        showSaveConfirmation(items);
    });

    document.getElementById("btn-refresh-stage1").addEventListener("click", async () => {
        const btn = document.getElementById("btn-refresh-stage1");
        const limitInput = document.getElementById("stage1-limit");
        const limit = Number(limitInput.value || 10);

        if (!Number.isInteger(limit) || limit <= 0 || limit > 100) {
            setStage1Status("Введите число от 1 до 100 в поле количества закупок.", "error");
            return;
        }

        currentLimit = limit;
        btn.disabled = true;
        setStage1Status("Загружаю новые закупки...");

        try {
            await loadNewList();
            setStage1Status(`Найдено закупок: ${zakupkiNew.length}.`, "success");
        } catch (error) {
            console.error(error);
            setStage1Status(`Ошибка загрузки: ${error.message}`, "error");
        } finally {
            btn.disabled = false;
        }
    });

    const btnLoadMoreAll = document.getElementById("btn-load-more-all");
    if (btnLoadMoreAll) {
        btnLoadMoreAll.addEventListener("click", () => loadAllZakupki(false));
    }
}
