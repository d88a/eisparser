const API_BASE = "/api";

const STAGE4_STATUS_LABELS = {
    url_ready: "Готово к сбору объявлений",
    listings_fresh: "Объявления уже собраны",
    listings_stale: "Нужно обновить объявления",
};

let stage4Offset = 0;
const stage4Limit = 20;
let stage4Total = 0;
let stage4Items = [];
let selectedItems = new Set();
let selectedRegNumber = null;

document.addEventListener("DOMContentLoaded", () => {
    loadStage4(true);
    document.getElementById("btn-run-stage4").addEventListener("click", runStage4);
    document.getElementById("btn-load-more-stage4").addEventListener("click", () => loadStage4(false));
    document.getElementById("select-all-stage4").addEventListener("change", (e) => toggleSelectAllVisible(e.target.checked));
});

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function setStage4Status(message, type = "info") {
    const el = document.getElementById("stage4-status");
    if (!message) {
        el.style.display = "none";
        el.className = "status-box";
        el.textContent = "";
        return;
    }
    el.style.display = "block";
    el.className = `status-box ${type === "info" ? "" : type}`.trim();
    el.textContent = message;
}

function clearErrors() {
    const panel = document.getElementById("stage4-errors");
    panel.style.display = "none";
    panel.innerHTML = "";
}

function renderErrors(errors) {
    const panel = document.getElementById("stage4-errors");
    if (!errors || errors.length === 0) {
        clearErrors();
        return;
    }

    const rows = errors.map((line) => `<div class="error-row">${escapeHtml(line)}</div>`).join("");
    panel.innerHTML = `<strong>Ошибки запуска Этапа 4</strong>${rows}`;
    panel.style.display = "block";
}

async function loadStage4(reset = false, keepSelected = false) {
    try {
        if (reset) {
            stage4Offset = 0;
            stage4Items = [];
            selectedItems.clear();
            if (!keepSelected) selectedRegNumber = null;

            document.getElementById("stage4-list").innerHTML = "";
            document.getElementById("stage4-workspace").innerHTML = '<div class="empty-state">Выберите закупку слева</div>';
            if (!keepSelected) {
                clearErrors();
                setStage4Status("");
            }
        }

        const resp = await fetch(`${API_BASE}/stage4?offset=${stage4Offset}&limit=${stage4Limit}`);
        if (!resp.ok) throw new Error("Не удалось загрузить список закупок Этапа 4");

        const data = await resp.json();
        const items = Array.isArray(data) ? data : data.items || [];
        stage4Total = Array.isArray(data) ? items.length : data.total || 0;

        stage4Items = stage4Items.concat(items);
        renderList(items, reset);
        updateRunButton();

        stage4Offset += items.length;
        const btnLoadMore = document.getElementById("btn-load-more-stage4");
        if (!Array.isArray(data) && stage4Offset < stage4Total) {
            btnLoadMore.style.display = "inline-block";
            btnLoadMore.disabled = false;
        } else {
            btnLoadMore.style.display = "none";
        }

        if (reset && keepSelected && selectedRegNumber) {
            const exists = stage4Items.some((x) => x.reg_number === selectedRegNumber);
            if (exists) await selectZakupka(selectedRegNumber);
        }
    } catch (e) {
        console.error(e);
        setStage4Status(e.message || "Ошибка загрузки Этапа 4", "error");
    }
}

function renderList(items, reset) {
    const list = document.getElementById("stage4-list");
    if (reset) list.innerHTML = "";

    if (reset && items.length === 0) {
        list.innerHTML = '<div style="padding:20px; text-align:center; color:#999">Нет закупок для Этапа 4</div>';
        return;
    }

    items.forEach((item) => {
        const checked = selectedItems.has(item.reg_number);
        const hasStage3Url = !!item.two_gis_url;
        const statusLabel = STAGE4_STATUS_LABELS[item.status] || item.status || "—";

        const div = document.createElement("div");
        div.className = "list-item";
        div.dataset.reg = item.reg_number;

        div.innerHTML = `
            <input type="checkbox" class="row-select-stage4" ${checked ? "checked" : ""} ${hasStage3Url ? "" : "disabled"} onclick="event.stopPropagation(); toggleSelection('${item.reg_number}', this.checked)">
            <div class="list-item-content">
                <div class="list-item-header">${item.reg_number}</div>
                <div class="list-item-desc">${item.ai_city || "—"} | ${item.bid_end_date || "—"} | ${formatPrice(item.initial_price)}</div>
                <div class="list-item-desc">${statusLabel}</div>
                <div class="list-item-desc" style="color:${hasStage3Url ? "#64748b" : "#b91c1c"};">${hasStage3Url ? "Ссылка Этапа 3 есть" : "Ссылки нет (Этап 3)"}</div>
            </div>
        `;

        div.addEventListener("click", () => selectZakupka(item.reg_number));
        list.appendChild(div);
    });
}

function formatPrice(price) {
    if (!price) return "—";
    return `${(price / 1000000).toFixed(2)} млн`;
}

function toggleSelection(regNumber, checked) {
    if (checked) selectedItems.add(regNumber);
    else selectedItems.delete(regNumber);
    updateRunButton();
}

function toggleSelectAllVisible(checked) {
    const checkboxes = document.querySelectorAll("#stage4-list .row-select-stage4");
    checkboxes.forEach((cb) => {
        if (cb.disabled) return;
        cb.checked = checked;

        const reg = cb.closest(".list-item")?.dataset?.reg;
        if (!reg) return;
        if (checked) selectedItems.add(reg);
        else selectedItems.delete(reg);
    });
    updateRunButton();
}

function updateRunButton() {
    const btn = document.getElementById("btn-run-stage4");
    btn.disabled = selectedItems.size === 0;
    btn.textContent = selectedItems.size > 0
        ? `Собрать объявления (${selectedItems.size})`
        : "Собрать объявления";
}

function renderSourceLinks(item) {
    let external = item.external_source || "";
    const externalUrl = item.external_url || "";

    if (!external && externalUrl) {
        const lowered = externalUrl.toLowerCase();
        if (lowered.includes("domclick") || lowered.includes("dom.click")) external = "domclick";
        else if (lowered.includes("cian")) external = "cian";
        else if (lowered.includes("avito")) external = "avito";
    }

    const domclick = external === "domclick" && externalUrl ? `<a class="source-link" href="${externalUrl}" target="_blank">Домклик</a>` : "—";
    const cian = external === "cian" && externalUrl ? `<a class="source-link" href="${externalUrl}" target="_blank">Циан</a>` : "—";
    const avito = external === "avito" && externalUrl ? `<a class="source-link" href="${externalUrl}" target="_blank">Avito</a>` : "—";
    const twoGisCard = item.two_gis_url ? `<a class="source-link" href="${item.two_gis_url}" target="_blank">2ГИС</a>` : "—";

    return `<div class="links-row"><strong>Ссылки:</strong> ${twoGisCard} | ${domclick} | ${cian} | ${avito}</div>`;
}

async function selectZakupka(regNumber) {
    selectedRegNumber = regNumber;
    document.querySelectorAll(".list-item").forEach((el) => el.classList.remove("active"));
    document.querySelector(`.list-item[data-reg="${regNumber}"]`)?.classList.add("active");

    const workspace = document.getElementById("stage4-workspace");
    workspace.innerHTML = '<div class="empty-state">Загрузка объявлений...</div>';
    const selectedMeta = stage4Items.find((x) => x.reg_number === regNumber);

    if (!selectedMeta || !selectedMeta.two_gis_url) {
        workspace.innerHTML = `
            <div class="workspace-header">
                <div><strong>${regNumber}</strong></div>
                <div style="color:#b91c1c;">Ссылки нет (Этап 3)</div>
            </div>
            <div class="workspace-body">
                <div class="listing-card" style="border-color:#fecaca; background:#fff1f2;">
                    Для этой закупки нет ссылки Этапа 3. Сначала сформируйте ссылку на Этапе 3.
                </div>
            </div>
        `;
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/stage4/${regNumber}/listings`);
        if (!resp.ok) throw new Error("Не удалось загрузить объявления");

        const data = await resp.json();
        const items = data.items || [];

        const head = `
            <div class="workspace-header">
                <div><strong>${regNumber}</strong></div>
                <div>Собрано объявлений: <strong>${items.length}</strong></div>
                <div><a href="${selectedMeta.two_gis_url}" target="_blank">Ссылка Этапа 3</a></div>
            </div>
        `;

        if (items.length === 0) {
            workspace.innerHTML = `${head}<div class="workspace-body"><div class="empty-state">По этой закупке пока нет собранных объявлений</div></div>`;
            return;
        }

        const cards = items.map((item) => {
            const rooms = item.rooms != null ? `${item.rooms} комн.` : "—";
            const area = item.area_m2 != null ? `${item.area_m2} м²` : "—";
            const floor = item.floor != null ? `${item.floor}/${item.building_floors || "?"}` : "—";
            const year = item.building_year != null ? `${item.building_year}` : "—";
            const price = item.price_rub ? `${item.price_rub.toLocaleString("ru-RU")} ₽` : "—";

            const links = renderSourceLinks(item);

            return `
                <div class="listing-card">
                    <div class="listing-title">#${item.rank || "—"} — ${price}</div>
                    <div class="listing-meta">
                        <div><strong>Адрес:</strong> ${item.address || "—"}</div>
                        <div><strong>Характеристики:</strong> ${rooms}, ${area}, этаж ${floor}, год ${year}</div>
                        ${links}
                    </div>
                </div>
            `;
        }).join("");

        workspace.innerHTML = `${head}<div class="workspace-body">${cards}</div>`;
    } catch (e) {
        console.error(e);
        workspace.innerHTML = '<div class="empty-state">Не удалось загрузить объявления</div>';
    }
}

function extractApiError(payload) {
    if (!payload) return "";
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
        return payload.detail.map((x) => x.msg || JSON.stringify(x)).join("; ");
    }
    return "";
}

async function runStage4() {
    if (selectedItems.size === 0) {
        setStage4Status("Выберите закупки галочками для запуска.", "error");
        return;
    }

    const topN = Number(document.getElementById("top-n-stage4").value || 20);
    const getDetails = !!document.getElementById("details-stage4").checked;
    const btn = document.getElementById("btn-run-stage4");
    const prevSelectedReg = selectedRegNumber;

    btn.disabled = true;
    setStage4Status("Собираю объявления по выбранным закупкам...");
    clearErrors();

    try {
        const resp = await fetch(`${API_BASE}/actions/run_stage4`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                reg_numbers: Array.from(selectedItems),
                top_n: topN,
                get_details: getDetails,
            }),
        });

        const result = await resp.json();
        if (!resp.ok) {
            const msg = extractApiError(result) || `HTTP ${resp.status}`;
            throw new Error(msg);
        }

        setStage4Status(`Готово: обработано закупок ${result.processed || 0}, собрано объявлений ${result.total_listings || 0}.`, "success");
        renderErrors(result.errors || []);

        selectedRegNumber = prevSelectedReg;
        await loadStage4(true, true);
    } catch (e) {
        console.error(e);
        setStage4Status(`Ошибка запуска: ${e.message || e}`, "error");
        renderErrors([`Ошибка запуска: ${e.message || e}`]);
    } finally {
        updateRunButton();
    }
}
