const USER_ID = 1;
const API_BASE = "/api";

let currentData = [];
let selectedRegNumber = null;
let selectedItems = new Set();
let currentOverrides = {};
let currentEditField = null;

let stage2Offset = 0;
const stage2Limit = 20;
let stage2Total = 0;
let stage2View = "pending";

const AI_FIELDS = [
    { key: "ai_zakupka_name", label: "Название" },
    { key: "ai_city", label: "Город" },
    { key: "ai_address", label: "Адрес" },
    { key: "initial_price", label: "Начальная цена", format: (v) => (v ? `${v.toLocaleString("ru-RU")} ₽` : "-") },
    { key: "area", label: "Площадь", custom: true },
    { key: "ai_rooms", label: "Комнат" },
    { key: "ai_floor", label: "Этаж" },
    { key: "ai_building_floors_min", label: "Этажность здания" },
    { key: "ai_year_build", label: "Год постройки" },
    { key: "ai_wear_percent", label: "Износ, %" },
    { key: "ai_zakazchik", label: "Заказчик" },
];

function readAiField(item, key) {
    const direct = item?.[key];
    if (direct !== undefined && direct !== null && direct !== "") return direct;

    const fallbackMap = {
        ai_zakupka_name: "zakupka_name",
        ai_city: "city",
        ai_address: "address",
        ai_rooms: "rooms",
        ai_floor: "floor",
        ai_building_floors_min: "building_floors_min",
        ai_year_build: "year_build_str",
        ai_wear_percent: "wear_percent",
        ai_zakazchik: "zakazchik",
    };

    const fallbackKey = fallbackMap[key];
    if (!fallbackKey) return direct;
    return item?.[fallbackKey];
}

document.addEventListener("DOMContentLoaded", () => {
    loadList(true);

    const runBtn = document.getElementById("btn-run-stage2");
    if (runBtn) runBtn.addEventListener("click", openRunConfirmModal);

    const btnLoadMore = document.getElementById("btn-load-more-stage2");
    if (btnLoadMore) btnLoadMore.addEventListener("click", () => loadList(false));

    const selectAll = document.getElementById("select-all-stage2");
    if (selectAll) selectAll.addEventListener("change", () => toggleSelectAllVisible(selectAll.checked));

    const btnPending = document.getElementById("btn-view-pending");
    const btnProcessed = document.getElementById("btn-view-processed");
    if (btnPending) btnPending.addEventListener("click", () => setStage2View("pending"));
    if (btnProcessed) btnProcessed.addEventListener("click", () => setStage2View("processed"));
});

function setStage2View(viewName) {
    stage2View = viewName === "processed" ? "processed" : "pending";
    const btnPending = document.getElementById("btn-view-pending");
    const btnProcessed = document.getElementById("btn-view-processed");

    if (btnPending) btnPending.classList.toggle("active", stage2View === "pending");
    if (btnProcessed) btnProcessed.classList.toggle("active", stage2View === "processed");

    selectedItems.clear();
    selectedRegNumber = null;
    loadList(true);
}

function setRunStatus(message, type = "info") {
    const el = document.getElementById("stage2-run-status");
    if (!el) return;

    if (!message) {
        el.style.display = "none";
        el.className = "stage2-status";
        el.textContent = "";
        return;
    }

    el.style.display = "block";
    el.className = `stage2-status ${type === "info" ? "" : type}`.trim();
    el.textContent = message;
}

function setRunStatusHtml(html, type = "info") {
    const el = document.getElementById("stage2-run-status");
    if (!el) return;
    if (!html) {
        setRunStatus("");
        return;
    }
    el.style.display = "block";
    el.className = `stage2-status ${type === "info" ? "" : type}`.trim();
    el.innerHTML = html;
}

function openRunConfirmModal() {
    if (selectedItems.size === 0) {
        setRunStatus("Выберите закупки галочками, затем запустите ИИ-анализ.", "error");
        return;
    }

    const modal = document.getElementById("confirm-run-modal");
    if (modal) modal.classList.add("active");
}

function closeRunConfirmModal() {
    const modal = document.getElementById("confirm-run-modal");
    if (modal) modal.classList.remove("active");
}

function confirmRunStage2() {
    closeRunConfirmModal();
    runStage2();
}

async function loadList(reset = false) {
    try {
        if (reset) {
            stage2Offset = 0;
            currentData = [];
            const listEl = document.getElementById("review-list");
            if (listEl) listEl.innerHTML = "";
        }

        const response = await fetch(`${API_BASE}/stage2?user_id=${USER_ID}&view=${stage2View}&offset=${stage2Offset}&limit=${stage2Limit}`);
        if (!response.ok) throw new Error("Не удалось загрузить закупки на Этапе 2");

        const data = await response.json();
        const items = Array.isArray(data) ? data : data.items || [];
        stage2Total = Array.isArray(data) ? items.length : data.total || 0;

        currentData = currentData.concat(items);
        renderList(items, reset);
        updateStats();
        syncSelectAllCheckbox();

        const btnLoadMore = document.getElementById("btn-load-more-stage2");
        stage2Offset += items.length;
        if (btnLoadMore) {
            if (!Array.isArray(data) && stage2Offset < stage2Total) {
                btnLoadMore.style.display = "inline-block";
                btnLoadMore.disabled = false;
            } else {
                btnLoadMore.style.display = "none";
            }
        }

        if (currentData.length === 0) {
            const workspace = document.getElementById("review-workspace");
            if (workspace) {
                workspace.innerHTML = stage2View === "pending"
                    ? '<div class="empty-state">Нет закупок для проверки</div>'
                    : '<div class="empty-state">Нет обработанных ИИ закупок</div>';
            }
            selectedRegNumber = null;
        }
    } catch (e) {
        console.error(e);
        setRunStatus(e.message || "Ошибка загрузки данных Этапа 2", "error");
    }
}

function renderList(items, reset) {
    const list = document.getElementById("review-list");
    if (!list) return;
    if (reset) list.innerHTML = "";

    if (reset && items.length === 0) {
        list.innerHTML = stage2View === "pending"
            ? '<div style="padding:20px; text-align:center; color:#999">Нет закупок для проверки.<br>Добавьте их на Этапе 1.</div>'
            : '<div style="padding:20px; text-align:center; color:#999">Нет обработанных ИИ закупок.</div>';
        return;
    }

    items.forEach((item) => {
        const div = document.createElement("div");
        div.className = `list-item${selectedItems.has(item.reg_number) ? " checked" : ""}`;
        div.dataset.reg = item.reg_number;

        div.innerHTML = `
            <input type="checkbox" class="stage2-checkbox" name="stage2_select" ${selectedItems.has(item.reg_number) ? "checked" : ""}
                   onclick="event.stopPropagation(); toggleStage2Selection('${item.reg_number}', this.checked)">
            <div class="list-item-content" onclick="selectItem('${item.reg_number}')">
                <div class="list-item-header">${item.reg_number}</div>
                <div class="list-item-desc">
                    ${item.ai_city || "—"} | ${item.ai_area_min || "—"} м² | ${item.initial_price ? `${(item.initial_price / 1000000).toFixed(1)} млн` : "-"} | ${item.status || "-"}
                </div>
            </div>
        `;

        list.appendChild(div);
    });
}

function toggleStage2Selection(regNumber, checked) {
    if (checked) selectedItems.add(regNumber);
    else selectedItems.delete(regNumber);

    updateStats();
    syncSelectAllCheckbox();

    const listItem = document.querySelector(`.list-item[data-reg="${regNumber}"]`);
    if (listItem) listItem.classList.toggle("checked", checked);
}

function toggleSelectAllVisible(checked) {
    const checkboxes = document.querySelectorAll("#review-list .stage2-checkbox");
    checkboxes.forEach((cb) => {
        cb.checked = checked;
        const regNumber = cb.closest(".list-item")?.dataset?.reg;
        if (!regNumber) return;

        if (checked) selectedItems.add(regNumber);
        else selectedItems.delete(regNumber);

        const listItem = document.querySelector(`.list-item[data-reg="${regNumber}"]`);
        if (listItem) listItem.classList.toggle("checked", checked);
    });

    updateStats();
    syncSelectAllCheckbox();
}

function syncSelectAllCheckbox() {
    const selectAll = document.getElementById("select-all-stage2");
    if (!selectAll) return;

    const checkboxes = document.querySelectorAll("#review-list .stage2-checkbox");
    if (checkboxes.length === 0) {
        selectAll.checked = false;
        return;
    }

    selectAll.checked = Array.from(checkboxes).every((cb) => cb.checked);
}

async function selectItem(regNumber) {
    selectedRegNumber = regNumber;
    const item = currentData.find((i) => i.reg_number === regNumber);
    if (!item) return;

    document.querySelectorAll(".list-item").forEach((el) => el.classList.remove("active"));
    document.querySelector(`.list-item[data-reg="${regNumber}"]`)?.classList.add("active");

    try {
        const resp = await fetch(`${API_BASE}/overrides/${regNumber}?user_id=${USER_ID}`);
        currentOverrides = await resp.json();
    } catch (e) {
        currentOverrides = {};
    }

    renderWorkspace(item);
}

function renderWorkspace(item) {
    const workspace = document.getElementById("review-workspace");
    if (!workspace) return;

    let fieldsHtml = "";

    AI_FIELDS.forEach((f) => {
        let aiValue;
        let displayValue;
        let overrideKey;

        if (f.custom && f.key === "area") {
            const areaMin = item.ai_area_min;
            const areaMax = item.ai_area_max;

            if (areaMin && areaMax && areaMin !== areaMax) aiValue = `${areaMin} м² - ${areaMax} м²`;
            else if (areaMin) aiValue = `${areaMin} м²`;
            else if (areaMax) aiValue = `${areaMax} м²`;
            else aiValue = null;

            displayValue = aiValue ?? "-";
            overrideKey = "area";
        } else {
            aiValue = readAiField(item, f.key);
            displayValue = f.format ? f.format(aiValue) : aiValue ?? "-";
            overrideKey = f.key.replace("ai_", "");
        }

        const override = currentOverrides[overrideKey];
        const hasOverride = override !== undefined && override !== null;
        const safeAi = String(aiValue ?? "").replace(/'/g, "\\'");

        fieldsHtml += `
            <div class="field-row ${hasOverride ? "has-override" : ""}">
                <div class="field-label">
                    <span>${f.label}</span>
                    <span class="edit-btn" onclick="openEditModal('${overrideKey}', '${f.label}', '${safeAi}')">Изменить</span>
                </div>
                <div class="field-values">
                    <span class="ai-value">${displayValue}</span>
                    ${hasOverride ? `<span class="override-value">→ ${override}</span>` : ""}
                </div>
            </div>
        `;
    });

    workspace.innerHTML = `
        <div class="review-header">
            <div>
                <h3>${item.reg_number}</h3>
                <span style="font-size:0.8em; color:#666">${item.update_date ? item.update_date.substring(0, 10) : ""}</span>
            </div>
            <a href="https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=${item.reg_number}"
               target="_blank" class="btn btn-sm">Открыть на ЕИС</a>
        </div>
        <div class="review-body">
            <div class="fields-panel">${fieldsHtml}</div>
            <div class="text-panel">
                <div class="text-panel-header">Документация</div>
                <div class="text-panel-content">${item.combined_text || "Текст закупки отсутствует..."}</div>
            </div>
        </div>
    `;
}

function openEditModal(fieldKey, fieldLabel, aiValue) {
    currentEditField = fieldKey;
    const nameEl = document.getElementById("modal-field-name");
    const aiEl = document.getElementById("modal-ai-value");
    const inputEl = document.getElementById("modal-input");
    const modal = document.getElementById("edit-modal");

    if (nameEl) nameEl.textContent = fieldLabel;
    if (aiEl) aiEl.textContent = aiValue || "-";
    if (inputEl) {
        inputEl.value = currentOverrides[fieldKey] || aiValue || "";
        inputEl.focus();
    }
    if (modal) modal.classList.add("active");
}

function closeModal() {
    const modal = document.getElementById("edit-modal");
    if (modal) modal.classList.remove("active");
    currentEditField = null;
}

async function saveOverride() {
    if (!currentEditField || !selectedRegNumber) return;

    const inputEl = document.getElementById("modal-input");
    const newValue = inputEl ? inputEl.value.trim() : "";

    try {
        const resp = await fetch(`${API_BASE}/overrides`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: USER_ID,
                reg_number: selectedRegNumber,
                field_name: currentEditField,
                value: newValue,
            }),
        });

        const result = await resp.json();
        if (result.status === "ok") {
            currentOverrides[currentEditField] = newValue;
            const item = currentData.find((i) => i.reg_number === selectedRegNumber);
            if (item) renderWorkspace(item);
            setRunStatus("Изменение сохранено.", "success");
        } else {
            setRunStatus("Не удалось сохранить изменение.", "error");
        }
    } catch (e) {
        console.error(e);
        setRunStatus("Ошибка соединения при сохранении изменения.", "error");
    }

    closeModal();
}

async function runStage2() {
    if (selectedItems.size === 0) {
        setRunStatus("Выберите закупки галочками, затем запустите ИИ-анализ.", "error");
        return;
    }

    const btn = document.getElementById("btn-run-stage2");
    if (btn) {
        btn.disabled = true;
        btn.textContent = "ИИ-анализ...";
    }
    setRunStatus("Запускаю ИИ-анализ по выбранным закупкам...");

    try {
        const response = await fetch(`${API_BASE}/actions/run_stage2`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: USER_ID,
                reg_numbers: Array.from(selectedItems),
                overwrite: true,
            }),
        });

        const result = await response.json();
        if (result.status === "ok") {
            const processedRegs = Array.isArray(result.processed_reg_numbers) ? result.processed_reg_numbers : [];
            const failedRegs = Array.isArray(result.failed_reg_numbers) ? result.failed_reg_numbers : [];

            const successPart = `Обработано: ${result.processed || 0}`;
            const movedPart = processedRegs.length > 0
                ? `Перенесены на Этап 3: ${processedRegs.join(", ")}.`
                : "Обработанные закупки будут доступны на Этапе 3.";
            const failedPart = failedRegs.length > 0
                ? `<br>Не обработаны: ${failedRegs.join(", ")}.`
                : "";

            setRunStatusHtml(
                `${successPart}. ${movedPart}${failedPart} <a href="/stage3" style="margin-left:6px;">Перейти на Этап 3</a>`,
                failedRegs.length > 0 ? "info" : "success"
            );
            if (processedRegs.length > 0) {
                stage2View = "processed";
                const btnPending = document.getElementById("btn-view-pending");
                const btnProcessed = document.getElementById("btn-view-processed");
                if (btnPending) btnPending.classList.toggle("active", false);
                if (btnProcessed) btnProcessed.classList.toggle("active", true);
            }
        } else {
            setRunStatus(result.message || "Ошибка запуска ИИ-анализа.", "error");
        }

        const prevSelected = selectedRegNumber;
        await loadList(true);
        selectedItems.clear();
        updateStats();

        if (currentData.length > 0) {
            const stillExists = prevSelected && currentData.some((x) => x.reg_number === prevSelected);
            if (stillExists) {
                await selectItem(prevSelected);
            } else {
                await selectItem(currentData[0].reg_number);
            }
        } else {
            selectedRegNumber = null;
            const workspace = document.getElementById("review-workspace");
            if (workspace) {
                workspace.innerHTML = '<div class="empty-state">Закупка обработана и перенесена на Этап 3. Список «На проверке» пуст.</div>';
            }
        }
    } catch (e) {
        console.error(e);
        setRunStatus("Ошибка соединения при запуске Этапа 2.", "error");
    } finally {
        if (btn) btn.disabled = false;
        updateStats();
    }
}

function updateStats() {
    const statCount = document.getElementById("stat-count");
    const statCountLabel = document.getElementById("stat-count-label");
    const statSelected = document.getElementById("stat-selected");

    if (statCountLabel) statCountLabel.textContent = stage2View === "pending" ? "На проверке" : "Обработано ИИ";
    if (statCount) statCount.textContent = stage2Total || currentData.length;
    if (statSelected) statSelected.textContent = selectedItems.size;

    const btn = document.getElementById("btn-run-stage2");
    if (!btn) return;

    btn.disabled = selectedItems.size === 0 || stage2View !== "pending";
    btn.textContent = selectedItems.size > 0
        ? `Запустить ИИ-анализ (${selectedItems.size})`
        : "Запустить ИИ-анализ";
}
