let currentOffset = 0;
const PAGE_LIMIT = 20;
let total = 0;
const includeReserved = new URLSearchParams(window.location.search).get("include_reserved") === "1";
const inFlightReserves = new Set();
const inFlightFavorites = new Set();
const loadedItems = [];

function parseMarginPercent(value) {
    const raw = String(value || "");
    const match = raw.match(/(-?\d+(?:\.\d+)?)%/);
    return match ? Number(match[1]) : null;
}

function parseBidDate(value) {
    const raw = String(value || "").trim();
    if (!raw) return null;

    const ru = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (ru) {
        const ts = Date.UTC(Number(ru[3]), Number(ru[2]) - 1, Number(ru[1]));
        return Number.isFinite(ts) ? ts : null;
    }

    const isoTs = Date.parse(raw);
    return Number.isFinite(isoTs) ? isoTs : null;
}

function formatDateTime(value) {
    if (!value) return "—";
    const ts = parseBidDate(value);
    if (ts === null) return publicTextOrDash(value);
    return new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(new Date(ts));
}

function formatShortDate(value) {
    const ts = parseBidDate(value);
    if (ts === null) return publicTextOrDash(value);
    return new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(new Date(ts));
}

function rawStatusLabel(status) {
    const map = {
        raw: "Новая",
        ai_ready: "ИИ готов",
        ai_error: "Ошибка ИИ",
        url_ready: "Готова к подбору",
        stage4_done: "Есть варианты квартир",
        stage4_error: "Нужна перепроверка",
        listings_fresh: "Есть варианты квартир",
        listings_stale: "Требует обновления",
    };
    return map[String(status || "").trim()] || "Неизвестно";
}

function statusTone(label) {
    const text = String(label || "").toLowerCase();
    if (text.includes("ошибка") || text.includes("перепровер")) return "status-danger";
    if (text.includes("обновлен")) return "status-warning";
    if (text.includes("готов") || text.includes("варианты")) return "status-success";
    return "status-neutral";
}

function statusCell(item) {
    const label = publicTextOrDash(item.status_label || rawStatusLabel(item.status));
    return `<span class="status-pill ${statusTone(label)}">${label}</span>`;
}

function marginCell(item) {
    const margin = parseMarginPercent(item.margin_display);
    if (margin === null) {
        return '<span class="margin-pill margin-muted">—</span>';
    }

    let level = "margin-muted";
    if (margin >= 75) level = "margin-high";
    else if (margin >= 50) level = "margin-medium";
    else if (margin >= 25) level = "margin-low";

    return `<span class="margin-pill ${level}">${margin}%</span>`;
}

function listingsCell(item) {
    const hasListings = Number(item.listings_count || 0) > 0;
    if (hasListings) {
        return '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0f766e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
    }
    return '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>';
}

function findLoadedItem(reg) {
    return loadedItems.find((item) => String(item.reg_number) === String(reg));
}

function favoriteCell(item) {
    const isFavorite = Boolean(item.is_favorite);
    const action = isFavorite ? "unfavorite" : "favorite";
    const title = isFavorite ? "Убрать из избранного" : "Добавить в избранное";
    const fillAttr = isFavorite ? 'fill="currentColor"' : 'fill="none"';
    return `
        <button
            class="favorite-toggle ${isFavorite ? "active" : ""} js-favorite"
            data-reg="${item.reg_number}"
            data-action="${action}"
            type="button"
            aria-label="${title}"
            title="${title}"
        ><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" ${fillAttr} stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg></button>
    `;
}

function eisLink(item) {
    if (!item.eis_url) {
        return `<span class="eis-link muted">—</span>`;
    }
    return `<a class="eis-link" target="_blank" rel="noopener noreferrer" href="${item.eis_url}">Открыть на ЕИС</a>`;
}

function reserveCell(item) {
    if (item.is_reserved) {
        return `<button class="reserve-btn reserve-btn--destructive js-unreserve" data-reg="${item.reg_number}" type="button">Снять бронь</button>`;
    }
    return `<button class="reserve-btn js-reserve" data-reg="${item.reg_number}" type="button">Забронировать</button>`;
}

async function toggleFavorite(reg, action) {
    const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(reg)}/${action}`, { method: "POST" });
    if (resp.status === 401) {
        window.location.href = `/public/login?next=${encodeURIComponent("/public/zakupki")}`;
        return { ok: false, redirected: true };
    }
    if (!resp.ok) {
        const detail = await publicExtractFriendlyError(resp, "изменение избранного");
        throw new Error(detail);
    }
    return { ok: true };
}

function getFilteredAndSortedItems() {
    let rows = [...loadedItems];

    const onlyWithListings = document.getElementById("flt-has-listings").checked;
    const marginRaw = document.getElementById("flt-margin-min").value.trim();
    const marginMin = marginRaw ? Number(marginRaw) : null;
    const sortMode = document.getElementById("sort-mode").value;

    if (onlyWithListings) {
        rows = rows.filter((item) => Number(item.listings_count || 0) > 0);
    }

    if (Number.isFinite(marginMin)) {
        rows = rows.filter((item) => {
            const margin = parseMarginPercent(item.margin_display);
            return margin !== null && margin >= marginMin;
        });
    }

    if (sortMode === "margin_desc") {
        rows.sort((a, b) => (parseMarginPercent(b.margin_display) ?? -Infinity) - (parseMarginPercent(a.margin_display) ?? -Infinity));
    } else if (sortMode === "margin_asc") {
        rows.sort((a, b) => (parseMarginPercent(a.margin_display) ?? Infinity) - (parseMarginPercent(b.margin_display) ?? Infinity));
    } else if (sortMode === "date_asc") {
        rows.sort((a, b) => (parseBidDate(a.bid_end_date) ?? Infinity) - (parseBidDate(b.bid_end_date) ?? Infinity));
    } else if (sortMode === "date_desc") {
        rows.sort((a, b) => (parseBidDate(b.bid_end_date) ?? -Infinity) - (parseBidDate(a.bid_end_date) ?? -Infinity));
    }

    return rows;
}

function renderRows(items) {
    const tbody = document.getElementById("public-list-body");
    tbody.innerHTML = "";

    if (!items.length) {
        tbody.innerHTML = '<tr class="state-row"><td colspan="9" class="state-cell">По текущим фильтрам закупки не найдены.</td></tr>';
        return;
    }

    const html = items.map((item) => `
        <tr>
            <td>
                <a class="link-reg" href="/public/zakupki/${encodeURIComponent(item.reg_number)}">${item.reg_number}</a>
                ${eisLink(item)}
            </td>
            <td>
                <a class="title-cell" href="/public/zakupki/${encodeURIComponent(item.reg_number)}">${publicTextOrDash(item.title)}</a>
            </td>
            <td class="cell-price">${publicFormatPrice(item.initial_price)}</td>
            <td class="cell-center">${listingsCell(item)}</td>
            <td class="cell-center">${marginCell(item)}</td>
            <td class="cell-center">${favoriteCell(item)}</td>
            <td class="cell-center">${reserveCell(item)}</td>
            <td class="cell-center"><span class="deadline-text">${formatShortDate(item.bid_end_date)}</span></td>
        </tr>
    `).join("");

    tbody.insertAdjacentHTML("beforeend", html);

    tbody.querySelectorAll(".js-reserve").forEach((btn) => {
        btn.addEventListener("click", async (event) => {
            const reg = event.currentTarget.dataset.reg;
            if (inFlightReserves.has(reg)) return;

            inFlightReserves.add(reg);
            event.currentTarget.disabled = true;
            event.currentTarget.textContent = "Бронируем...";

            try {
                const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(reg)}/reserve`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({}),
                });

                if (resp.status === 401) {
                    window.location.href = `/public/login?next=${encodeURIComponent("/public/zakupki")}`;
                    return;
                }

                if (resp.status === 409) {
                    const item = findLoadedItem(reg);
                    if (item) {
                        item.is_reserved = true;
                    }
                    applyFiltersAndSort();
                    return;
                }

                if (!resp.ok) {
                    const detail = await publicExtractFriendlyError(resp, "бронирование закупки");
                    throw new Error(detail);
                }

                const data = await resp.json();
                const item = findLoadedItem(reg);
                if (item) {
                    item.is_reserved = true;
                    item.reserved_until = data.expires_at || item.reserved_until || null;
                }
                applyFiltersAndSort();
            } catch (error) {
                alert(error.message || "Не удалось забронировать закупку.");
            } finally {
                inFlightReserves.delete(reg);
            }
        });
    });

    tbody.querySelectorAll(".js-unreserve").forEach((btn) => {
        btn.addEventListener("click", async (event) => {
            const reg = event.currentTarget.dataset.reg;
            if (inFlightReserves.has(reg)) return;

            inFlightReserves.add(reg);
            event.currentTarget.disabled = true;
            event.currentTarget.textContent = "Снимаем...";

            try {
                const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(reg)}/unreserve`, {
                    method: "POST",
                });

                if (resp.status === 401) {
                    window.location.href = `/public/login?next=${encodeURIComponent("/public/zakupki")}`;
                    return;
                }

                if (!resp.ok) {
                    const detail = await publicExtractFriendlyError(resp, "снятие брони");
                    throw new Error(detail);
                }

                const item = findLoadedItem(reg);
                if (item) {
                    item.is_reserved = false;
                    item.reserved_until = null;
                }
                applyFiltersAndSort();
            } catch (error) {
                alert(error.message || "Не удалось снять бронь.");
            } finally {
                inFlightReserves.delete(reg);
            }
        });
    });

    tbody.querySelectorAll(".js-favorite").forEach((btn) => {
        btn.addEventListener("click", async (event) => {
            const reg = event.currentTarget.dataset.reg;
            const action = event.currentTarget.dataset.action;
            if (inFlightFavorites.has(reg)) return;

            inFlightFavorites.add(reg);
            event.currentTarget.disabled = true;
            try {
                const result = await toggleFavorite(reg, action);
                if (!result.ok) return;

                const item = findLoadedItem(reg);
                if (item) {
                    item.is_favorite = action === "favorite";
                }
                applyFiltersAndSort();
            } catch (error) {
                alert(error.message || "Не удалось изменить избранное.");
            } finally {
                inFlightFavorites.delete(reg);
            }
        });
    });
}

function applyFiltersAndSort() {
    renderRows(getFilteredAndSortedItems());
}

function syncTotal(value) {
    const totalNode = document.getElementById("total-count");
    const summaryNode = document.getElementById("hero-total-count");
    if (summaryNode) summaryNode.textContent = String(value);
    if (totalNode) totalNode.textContent = String(value);
}

async function loadPage(reset = false) {
    const btn = document.getElementById("btn-load-more");
    if (reset) {
        currentOffset = 0;
        loadedItems.length = 0;
    }

    btn.disabled = true;
    btn.textContent = "Загрузка...";

    const reservedFlag = includeReserved ? "1" : "0";
    const resp = await fetch(`/api/public/zakupki?offset=${currentOffset}&limit=${PAGE_LIMIT}&include_reserved=${reservedFlag}`);
    if (!resp.ok) {
        const detail = await publicExtractFriendlyError(resp, "загрузка списка закупок");
        throw new Error(detail);
    }

    const data = await resp.json();
    const items = data.items || [];

    total = data.total || 0;
    syncTotal(total);

    loadedItems.push(...items);
    currentOffset += items.length;
    applyFiltersAndSort();

    if (currentOffset < total) {
        btn.style.display = "inline-flex";
        btn.disabled = false;
        btn.textContent = "Показать ещё";
    } else {
        btn.style.display = "none";
    }
}

function resetFilters() {
    document.getElementById("flt-has-listings").checked = false;
    document.getElementById("flt-margin-min").value = "";
    document.getElementById("sort-mode").value = "date_asc";
    applyFiltersAndSort();
}

async function bootstrap() {
    try {
        await loadPage(true);
    } catch (error) {
        const tbody = document.getElementById("public-list-body");
        tbody.innerHTML = `<tr class="state-row"><td colspan="9" class="state-cell">${publicTextOrDash(error.message)}</td></tr>`;
    }
}

document.getElementById("flt-has-listings").addEventListener("change", applyFiltersAndSort);
document.getElementById("flt-margin-min").addEventListener("input", applyFiltersAndSort);
document.getElementById("sort-mode").addEventListener("change", applyFiltersAndSort);
document.getElementById("btn-filters-reset").addEventListener("click", resetFilters);
document.getElementById("btn-load-more").addEventListener("click", async () => {
    try {
        await loadPage(false);
    } catch (error) {
        alert(error.message || "Не удалось загрузить следующую страницу.");
    }
});

resetFilters();
bootstrap();
