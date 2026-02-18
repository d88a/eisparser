// stage3.js — Этап 3: формирование ссылок 2ГИС

const API_BASE = "/api";

let stage3Offset = 0;
const stage3Limit = 20;
let stage3Total = 0;
let stage3Items = [];
let selectedItems = new Set();

document.addEventListener("DOMContentLoaded", () => {
    loadStage3(true);
    document.getElementById("btn-run-stage3").addEventListener("click", runStage3);

    const btnLoadMore = document.getElementById("btn-load-more-stage3");
    if (btnLoadMore) {
        btnLoadMore.addEventListener("click", () => loadStage3(false));
    }

    const selectAll = document.getElementById("select-all-stage3");
    const selectAllHead = document.getElementById("select-all-stage3-head");
    if (selectAll) {
        selectAll.addEventListener("change", () => toggleSelectAllVisible(selectAll.checked));
    }
    if (selectAllHead) {
        selectAllHead.addEventListener("change", () => toggleSelectAllVisible(selectAllHead.checked));
    }
});

function setStage3Status(message, type = "info") {
    const el = document.getElementById("stage3-status");
    if (!message) {
        el.style.display = "none";
        el.className = "stage3-status";
        el.textContent = "";
        return;
    }
    el.style.display = "block";
    el.className = `stage3-status ${type === "info" ? "" : type}`.trim();
    el.textContent = message;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function renderStage3Errors(errors) {
    const el = document.getElementById("stage3-errors");
    if (!errors || errors.length === 0) {
        el.style.display = "none";
        el.innerHTML = "";
        return;
    }
    el.style.display = "block";
    el.innerHTML = `<strong>Ошибки формирования ссылок</strong>${errors
        .map((err) => `<div class="stage3-error-row">${escapeHtml(err)}</div>`)
        .join("")}`;
}

async function loadStage3(reset = false) {
    try {
        if (reset) {
            stage3Offset = 0;
            stage3Items = [];
            document.getElementById("zakupki-body-stage3").innerHTML = "";
        }

        const resp = await fetch(`${API_BASE}/stage3?offset=${stage3Offset}&limit=${stage3Limit}`);
        if (!resp.ok) throw new Error("Не удалось загрузить данные Этапа 3");

        const data = await resp.json();
        const items = Array.isArray(data) ? data : data.items || [];
        stage3Total = Array.isArray(data) ? items.length : data.total || 0;

        stage3Items = stage3Items.concat(items);
        renderStage3(items, reset);
        updateStats();

        stage3Offset += items.length;
        const btn = document.getElementById("btn-load-more-stage3");
        if (!Array.isArray(data) && stage3Offset < stage3Total) {
            btn.style.display = "inline-block";
            btn.disabled = false;
        } else {
            btn.style.display = "none";
        }
        syncSelectAllCheckbox();
    } catch (e) {
        console.error(e);
        setStage3Status(e.message || "Ошибка загрузки данных", "error");
    }
}

function renderStage3(items, reset) {
    const tbody = document.getElementById("zakupki-body-stage3");
    if (reset) tbody.innerHTML = "";

    if (reset && items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:40px; color:#999">Нет закупок для Этапа 3</td></tr>';
        return;
    }

    items.forEach((item) => {
        const tr = document.createElement("tr");
        tr.dataset.reg = item.reg_number;

        const price = item.initial_price ? `${(item.initial_price / 1000000).toFixed(2)} млн` : "-";
        const area = formatArea(item.ai_area_min, item.ai_area_max);
        const link = item.two_gis_url
            ? `<a href="${item.two_gis_url}" target="_blank">Открыть</a>`
            : "—";

        tr.innerHTML = `
            <td><input type="checkbox" class="row-select-stage3" name="stage3_select" ${selectedItems.has(item.reg_number) ? "checked" : ""} onchange="toggleStage3Selection('${item.reg_number}', this.checked)"></td>
            <td><a href="${item.link || "#"}" target="_blank">${item.reg_number}</a></td>
            <td title="${item.description || ""}">${item.description || "-"}</td>
            <td>${item.ai_city || "-"}</td>
            <td>${area}</td>
            <td>${price}</td>
            <td>${item.bid_end_date || "-"}</td>
            <td class="link-cell" data-link="${item.reg_number}">${link}</td>
        `;
        tbody.appendChild(tr);
    });
}

function formatArea(minVal, maxVal) {
    if (minVal && maxVal && minVal !== maxVal) return `${minVal}–${maxVal} м²`;
    if (minVal) return `${minVal} м²`;
    if (maxVal) return `${maxVal} м²`;
    return "-";
}

function toggleStage3Selection(regNumber, checked) {
    if (checked) selectedItems.add(regNumber);
    else selectedItems.delete(regNumber);
    updateStats();
    syncSelectAllCheckbox();
}

function toggleSelectAllVisible(checked) {
    const checkboxes = document.querySelectorAll("#zakupki-body-stage3 .row-select-stage3");
    checkboxes.forEach((cb) => {
        cb.checked = checked;
        const regNumber = cb.closest("tr")?.dataset?.reg;
        if (regNumber) {
            if (checked) selectedItems.add(regNumber);
            else selectedItems.delete(regNumber);
        }
    });
    updateStats();
    syncSelectAllCheckbox();
}

function syncSelectAllCheckbox() {
    const selectAll = document.getElementById("select-all-stage3");
    const selectAllHead = document.getElementById("select-all-stage3-head");
    const checkboxes = document.querySelectorAll("#zakupki-body-stage3 .row-select-stage3");
    if (checkboxes.length === 0) {
        if (selectAll) selectAll.checked = false;
        if (selectAllHead) selectAllHead.checked = false;
        return;
    }
    const allChecked = Array.from(checkboxes).every((cb) => cb.checked);
    if (selectAll) selectAll.checked = allChecked;
    if (selectAllHead) selectAllHead.checked = allChecked;
}

function updateStats() {
    document.getElementById("stat-total").textContent = stage3Total || stage3Items.length;
    document.getElementById("stat-selected").textContent = selectedItems.size;
    const btn = document.getElementById("btn-run-stage3");
    btn.disabled = selectedItems.size === 0;
    btn.textContent = selectedItems.size > 0
        ? `Сформировать ссылки 2ГИС (${selectedItems.size})`
        : "Сформировать ссылки 2ГИС";
}

function extractApiError(payload) {
    if (!payload) return "";
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
        return payload.detail.map((x) => x.msg || JSON.stringify(x)).join("; ");
    }
    return "";
}

async function runStage3() {
    if (selectedItems.size === 0) {
        setStage3Status("Выберите закупки галочками.", "error");
        return;
    }

    const overwrite = document.getElementById("overwrite-stage3")?.checked || false;
    const btn = document.getElementById("btn-run-stage3");
    btn.disabled = true;
    setStage3Status("Формирую ссылки 2ГИС...");
    renderStage3Errors([]);

    try {
        const resp = await fetch(`${API_BASE}/actions/run_stage3`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                reg_numbers: Array.from(selectedItems),
                overwrite,
            }),
        });
        const result = await resp.json();
        if (!resp.ok) {
            const msg = extractApiError(result) || `HTTP ${resp.status}`;
            throw new Error(msg);
        }

        if (result.status === "ok") {
            setStage3Status(result.message || "Ссылки сформированы.", "success");
            const items = result.items || [];
            items.forEach((it) => {
                const cell = document.querySelector(`td[data-link="${it.reg_number}"]`);
                if (cell) {
                    cell.innerHTML = it.two_gis_url ? `<a href="${it.two_gis_url}" target="_blank">Открыть</a>` : "—";
                }
            });
            renderStage3Errors(result.errors || []);
        } else {
            setStage3Status(result.message || "Ошибка формирования ссылок.", "error");
            renderStage3Errors(result.errors || []);
        }
    } catch (e) {
        console.error(e);
        setStage3Status(`Ошибка запуска: ${e.message || e}`, "error");
        renderStage3Errors([`${e.message || e}`]);
    } finally {
        btn.disabled = false;
        updateStats();
    }
}
