let currentOffset = 0;
const limit = 20;
let total = 0;
let currentTab = "active";
let loadedItems = [];
const tabTotals = { active: 0, history: 0, favorites: 0 };
const inFlightUnreserve = new Set();
const inFlightUnfavorite = new Set();

const TABS = {
    active: {
        title: "Активные брони",
        head: ["Рег. номер", "Название", "Цена", "Окончание подачи", "Маржа", "Забронировано до", "Статус", "Действие"],
        empty: "Активных броней нет",
    },
    history: {
        title: "История броней",
        head: ["Рег. номер", "Название", "Цена", "Окончание подачи", "Маржа", "Период брони", "Итоговый статус"],
        empty: "История пока пустая",
    },
    favorites: {
        title: "Избранные закупки",
        head: ["Рег. номер", "Название", "Цена", "Окончание подачи", "Маржа", "В избранном с", "Действие"],
        empty: "Избранных закупок нет",
    },
};

function bookingStatusLabel(status) {
    if (status === "active") return "Активна";
    if (status === "expired") return "Истекла";
    if (status === "released") return "Снята";
    return "-";
}

function marginCell(value) {
    const raw = String(value || "");
    const m = raw.match(/(-?\d+(?:\.\d+)?)%/);
    if (!m) return `<span class="margin-pill margin-muted">${publicTextOrDash(value)}</span>`;
    const pct = Number(m[1]);
    let cls = "margin-muted";
    if (pct >= 75) cls = "margin-high";
    else if (pct >= 50) cls = "margin-medium";
    else if (pct >= 25) cls = "margin-low";
    return `<span class="margin-pill ${cls}">${m[1]}%</span>`;
}

function periodLabel(item) {
    const from = publicFormatDate(item.booking_from);
    const to = publicFormatDate(item.booking_to);
    return `${from} — ${to}`;
}

function getSortModeForTab() {
    const raw = document.getElementById("cabinet-sort-mode").value || "default";
    if (raw !== "default") {
        return raw;
    }
    return currentTab === "history" ? "history_desc" : "bid_end_asc";
}

function updateCounters() {
    document.getElementById("count-active").textContent = String(tabTotals.active || 0);
    document.getElementById("count-history").textContent = String(tabTotals.history || 0);
    document.getElementById("count-favorites").textContent = String(tabTotals.favorites || 0);
}

function updateFilterVisibility() {
    const statusFilter = document.getElementById("cabinet-status-filter");
    const sortMode = document.getElementById("cabinet-sort-mode");
    const disableFilter = currentTab === "favorites";
    statusFilter.disabled = disableFilter;
    sortMode.disabled = disableFilter;
}

async function fetchTotalForTab(tab) {
    let url = "";
    if (tab === "favorites") {
        url = "/api/public/favorites?offset=0&limit=1";
    } else {
        url = `/api/public/reservations?tab=${encodeURIComponent(tab)}&status_filter=all&sort_mode=bid_end_asc&offset=0&limit=1`;
    }

    const resp = await fetch(url);
    if (resp.status === 401) {
        window.location.href = `/public/login?next=${encodeURIComponent("/public/reservations")}`;
        return 0;
    }
    if (!resp.ok) {
        throw new Error(publicCabinetMessage("load"));
    }

    const data = await resp.json();
    return Number(data.total || 0);
}

async function refreshCounters(force = false) {
    const tabs = ["active", "history", "favorites"];
    const jobs = tabs.map(async (tab) => {
        if (!force && tabTotals[tab] > 0) {
            return;
        }
        tabTotals[tab] = await fetchTotalForTab(tab);
    });

    await Promise.all(jobs);
    updateCounters();
}

async function unreserve(regNumber) {
    const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(regNumber)}/unreserve`, {
        method: "POST",
    });
    if (resp.status === 401) {
        window.location.href = `/public/login?next=${encodeURIComponent("/public/reservations")}`;
        return { ok: false, redirected: true };
    }
    if (!resp.ok) {
        throw new Error(publicCabinetMessage("unreserve"));
    }
    return { ok: true };
}

async function unfavorite(regNumber) {
    const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(regNumber)}/unfavorite`, {
        method: "POST",
    });
    if (resp.status === 401) {
        window.location.href = `/public/login?next=${encodeURIComponent("/public/reservations")}`;
        return { ok: false, redirected: true };
    }
    if (!resp.ok) {
        throw new Error(publicCabinetMessage("unfavorite"));
    }
    return { ok: true };
}

function renderHead() {
    const row = document.getElementById("cabinet-head-row");
    row.innerHTML = TABS[currentTab].head.map((text) => `<th>${text}</th>`).join("");
    document.getElementById("table-title").textContent = TABS[currentTab].title;
}

function bindRowActions(tbody) {
    tbody.querySelectorAll(".js-unreserve").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            const reg = e.currentTarget.dataset.reg;
            if (inFlightUnreserve.has(reg)) return;

            inFlightUnreserve.add(reg);
            e.currentTarget.disabled = true;
            e.currentTarget.textContent = "Снимаем...";
            try {
                const result = await unreserve(reg);
                if (!result.ok) {
                    return;
                }

                loadedItems = loadedItems.filter((x) => String(x.reg_number) !== String(reg));
                total = Math.max(0, total - 1);
                tabTotals.active = Math.max(0, Number(tabTotals.active || 0) - 1);
                document.getElementById("total-count").textContent = String(total);
                renderRows(loadedItems, true);
                await refreshCounters(true);
            } catch (err) {
                alert(publicCabinetMessage("unreserve"));
                e.currentTarget.disabled = false;
                e.currentTarget.textContent = "Снять бронь";
            } finally {
                inFlightUnreserve.delete(reg);
            }
        });
    });

    tbody.querySelectorAll(".js-unfavorite").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
            const reg = e.currentTarget.dataset.reg;
            if (inFlightUnfavorite.has(reg)) return;

            inFlightUnfavorite.add(reg);
            e.currentTarget.disabled = true;
            e.currentTarget.textContent = "Убираем...";
            try {
                const result = await unfavorite(reg);
                if (!result.ok) {
                    return;
                }

                loadedItems = loadedItems.filter((x) => String(x.reg_number) !== String(reg));
                total = Math.max(0, total - 1);
                tabTotals.favorites = Math.max(0, Number(tabTotals.favorites || 0) - 1);
                document.getElementById("total-count").textContent = String(total);
                renderRows(loadedItems, true);
                await refreshCounters(true);
            } catch (err) {
                alert(publicCabinetMessage("unfavorite"));
                e.currentTarget.disabled = false;
                e.currentTarget.textContent = "Убрать";
            } finally {
                inFlightUnfavorite.delete(reg);
            }
        });
    });
}

function renderRows(items, reset = false) {
    const tbody = document.getElementById("cabinet-body");
    const colCount = TABS[currentTab].head.length;
    if (reset) {
        tbody.innerHTML = "";
    }

    if (items.length === 0 && reset) {
        tbody.innerHTML = `<tr class="state-row"><td colspan="${colCount}" class="state-cell">${TABS[currentTab].empty}</td></tr>`;
        return;
    }

    let html = "";
    if (currentTab === "active") {
        html = items.map((item) => `
            <tr>
                <td><a class="link-reg" href="/public/zakupki/${encodeURIComponent(item.reg_number)}">${item.reg_number}</a></td>
                <td>${publicTextOrDash(item.title)}</td>
                <td>${publicFormatPrice(item.initial_price)}</td>
                <td>${publicFormatDate(item.bid_end_date)}</td>
                <td>${marginCell(item.margin_display)}</td>
                <td>${publicFormatDate(item.reserved_until)}</td>
                <td>${bookingStatusLabel(item.booking_status)}</td>
                <td><button class="reserve-btn js-unreserve" data-reg="${item.reg_number}">Снять бронь</button></td>
            </tr>
        `).join("");
    } else if (currentTab === "history") {
        html = items.map((item) => `
            <tr>
                <td><a class="link-reg" href="/public/zakupki/${encodeURIComponent(item.reg_number)}">${item.reg_number}</a></td>
                <td>${publicTextOrDash(item.title)}</td>
                <td>${publicFormatPrice(item.initial_price)}</td>
                <td>${publicFormatDate(item.bid_end_date)}</td>
                <td>${marginCell(item.margin_display)}</td>
                <td>${periodLabel(item)}</td>
                <td>${bookingStatusLabel(item.booking_status)}</td>
            </tr>
        `).join("");
    } else {
        html = items.map((item) => `
            <tr>
                <td><a class="link-reg" href="/public/zakupki/${encodeURIComponent(item.reg_number)}">${item.reg_number}</a></td>
                <td>${publicTextOrDash(item.title)}</td>
                <td>${publicFormatPrice(item.initial_price)}</td>
                <td>${publicFormatDate(item.bid_end_date)}</td>
                <td>${marginCell(item.margin_display)}</td>
                <td>${publicFormatDate(item.favorited_at)}</td>
                <td><button class="btn btn-outline js-unfavorite" data-reg="${item.reg_number}">Убрать</button></td>
            </tr>
        `).join("");
    }

    tbody.insertAdjacentHTML("beforeend", html);
    bindRowActions(tbody);
}

function buildDataUrl() {
    if (currentTab === "favorites") {
        return `/api/public/favorites?offset=${currentOffset}&limit=${limit}`;
    }

    const statusFilter = document.getElementById("cabinet-status-filter").value || "all";
    const sortMode = getSortModeForTab();
    return `/api/public/reservations?tab=${encodeURIComponent(currentTab)}&status_filter=${encodeURIComponent(statusFilter)}&sort_mode=${encodeURIComponent(sortMode)}&offset=${currentOffset}&limit=${limit}`;
}

async function loadPage(reset = false) {
    const btn = document.getElementById("btn-load-more");
    if (reset) {
        currentOffset = 0;
        loadedItems = [];
    }

    btn.disabled = true;
    btn.textContent = "Загрузка...";

    const resp = await fetch(buildDataUrl());
    if (resp.status === 401) {
        window.location.href = `/public/login?next=${encodeURIComponent("/public/reservations")}`;
        return;
    }
    if (!resp.ok) {
        throw new Error(publicCabinetMessage("load"));
    }

    const data = await resp.json();
    const items = data.items || [];

    total = Number(data.total || 0);
    tabTotals[currentTab] = total;
    updateCounters();
    document.getElementById("total-count").textContent = String(total);

    loadedItems.push(...items);
    renderRows(items, reset);
    currentOffset += items.length;

    if (currentOffset < total) {
        btn.style.display = "inline-flex";
        btn.disabled = false;
        btn.textContent = "Показать ещё";
    } else {
        btn.style.display = "none";
    }
}

async function selectTab(tab) {
    currentTab = tab;
    document.querySelectorAll(".tab-btn").forEach((node) => {
        node.classList.toggle("active", node.dataset.tab === tab);
    });
    updateFilterVisibility();
    renderHead();
    await loadPage(true);
    await refreshCounters(false);
}

async function bootstrap() {
    renderHead();
    updateFilterVisibility();
    try {
        await loadPage(true);
        await refreshCounters(true);
    } catch (err) {
        const tbody = document.getElementById("cabinet-body");
        const colCount = TABS[currentTab].head.length;
        tbody.innerHTML = `<tr class="state-row"><td colspan="${colCount}" class="state-cell">${publicCabinetMessage("load")}</td></tr>`;
    }
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
        if (btn.dataset.tab === currentTab) return;
        try {
            await selectTab(btn.dataset.tab);
        } catch (err) {
            alert(publicCabinetMessage("load"));
        }
    });
});

document.getElementById("cabinet-status-filter").addEventListener("change", async () => {
    if (currentTab === "favorites") return;
    try {
        await loadPage(true);
        await refreshCounters(true);
    } catch (err) {
        alert(publicCabinetMessage("load"));
    }
});

document.getElementById("cabinet-sort-mode").addEventListener("change", async () => {
    if (currentTab === "favorites") return;
    try {
        await loadPage(true);
    } catch (err) {
        alert(publicCabinetMessage("load"));
    }
});

document.getElementById("btn-load-more").addEventListener("click", async () => {
    try {
        await loadPage(false);
    } catch (err) {
        alert(publicCabinetMessage("load"));
    }
});

bootstrap();
