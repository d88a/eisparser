let detailState = null;
let reserveInFlight = false;
let favoriteInFlight = false;

const TEXT = {
    titleFallback: "Карточка закупки",
    subtitleFallback: "Подробная карточка закупки и доступных вариантов квартир.",
    regLabel: "Рег. номер",
    bidEndLabel: "Окончание подачи",
    reserveAction: "Забронировать закупку",
    reserveProgress: "Бронируем...",
    reserveLocked: "Закупка забронирована",
    reserveConflict: "Закупка уже занята другим пользователем.",
    reserveError: "Не удалось забронировать закупку.",
    addFavorite: "В избранное",
    removeFavorite: "Убрать из избранного",
    favoriteOn: "В избранном",
    favoriteOff: "Не в избранном",
    favoriteError: "Не удалось изменить избранное.",
    detailLoadError: "Загрузка карточки закупки",
    reserveRequest: "бронирование закупки",
    favoriteRequest: "изменение избранного",
    emptyListings: "Для этой закупки пока нет подходящих вариантов квартир.",
    externalUnavailable: "Внешняя ссылка недоступна",
    openListing: "Открыть объявление",
    loadFailed: "Ошибка загрузки",
    labels: {
        initialPrice: "Цена",
        margin: "Маржа",
        city: "Населенный пункт",
        address: "Адрес",
        areaFrom: "Площадь от",
        areaTo: "Площадь до",
        rooms: "Комнаты",
        floor: "Этаж",
        floors: "Этажность",
        year: "Год постройки",
        wear: "Износ",
        customer: "Заказчик",
        area: "Площадь",
    },
};

function detailDash(value) {
    return publicTextOrDash(value);
}

function formatDetailDateTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return detailDash(value);
    return new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(date);
}

function formatBidDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return detailDash(value);
    return new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(date);
}

function formatSquareMeters(value) {
    if (value === null || value === undefined || value === "") return null;
    return `${value} м²`;
}

function parseMarginPercent(value) {
    const raw = String(value || "");
    const match = raw.match(/(-?\d+(?:\.\d+)?)%/);
    return match ? Number(match[1]) : null;
}

function marginBadge(value) {
    const percent = parseMarginPercent(value);
    if (percent === null) {
        return '<span class="margin-pill margin-muted">—</span>';
    }

    let tone = "margin-low";
    if (percent >= 12) tone = "margin-high";
    else if (percent >= 8) tone = "margin-medium";

    return `<span class="margin-pill ${tone}">${percent}%</span>`;
}

function buildSubtitle(detail) {
    const parts = [detail.city, detail.address].filter(Boolean);
    if (parts.length) return parts.join(", ");
    return TEXT.subtitleFallback;
}

function setReserveStatus(message, isError = false) {
    // Reserve status is no longer displayed on the page
}

function syncFavoriteState(detail) {
    const btn = document.getElementById("btn-favorite");
    const isFavorite = Boolean(detail.is_favorite);
    btn.dataset.action = isFavorite ? "unfavorite" : "favorite";
    btn.innerHTML = isFavorite
        ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg> Убрать из избранного'
        : '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg> В избранное';
}

function syncReserveButton(detail) {
    const btn = document.getElementById("btn-reserve-zakupka");
    if (detail.is_reserved) {
        btn.disabled = true;
        btn.textContent = TEXT.reserveLocked;
        setReserveStatus(`До ${formatDetailDateTime(detail.reserved_until)}`);
    } else {
        btn.disabled = false;
        btn.textContent = TEXT.reserveAction;
        setReserveStatus("");
    }
}

function renderFeatures(detail) {
    const fields = [
        [TEXT.labels.initialPrice, publicFormatPrice(detail.initial_price)],
        [TEXT.labels.margin, marginBadge(detail.margin_display)],
        [TEXT.labels.city, detailDash(detail.city)],
        [TEXT.labels.address, detailDash(detail.address)],
        [TEXT.labels.areaFrom, detailDash(formatSquareMeters(detail.area_min_m2))],
        [TEXT.labels.areaTo, detailDash(formatSquareMeters(detail.area_max_m2))],
        [TEXT.labels.rooms, detailDash(detail.rooms)],
        [TEXT.labels.floor, detailDash(detail.floor)],
        [TEXT.labels.floors, detailDash(detail.building_floors_min)],
        [TEXT.labels.year, detailDash(detail.year_build_str)],
        [TEXT.labels.wear, detail.wear_percent ? `${detail.wear_percent}%` : "—"],
        [TEXT.labels.customer, detailDash(detail.zakazchik)],
    ];

    const root = document.getElementById("detail-features");
    root.innerHTML = fields.map(([label, value]) => `
        <article class="feature">
            <div class="key">${label}</div>
            <div class="value">${value}</div>
        </article>
    `).join("");
}

function listingMetaItem(label, value) {
    return `
        <div class="listing-meta-item">
            <span class="label">${label}</span>
            <span class="value">${detailDash(value)}</span>
        </div>
    `;
}

function renderListings(detail) {
    const listings = detail.listings || [];
    const root = document.getElementById("listings-container");

    const countNode = document.getElementById("listings-total");
    if (countNode) countNode.textContent = String(listings.length);

    if (!listings.length) {
        root.innerHTML = `<div class="empty-state">${TEXT.emptyListings}</div>`;
        return;
    }

    root.innerHTML = listings.map((item) => {
        const params = [
            item.rooms ? `${item.rooms}-комн.` : null,
            item.area_m2 ? `${item.area_m2} м²` : null,
            item.floor ? `этаж ${item.floor}` : null,
        ].filter(Boolean).join(', ');

        const extUrl = item.external_url;
        const extLabel = item.external_source === 'cian' ? 'Открыть на CIAN' : 'Открыть на Домклик';
        const actions = extUrl
            ? `<div class="listing-actions"><a class="btn btn-sm" target="_blank" rel="noopener noreferrer" href="${extUrl}">${extLabel}</a></div>`
            : `<div class="listing-actions"><span class="muted-note">${TEXT.externalUnavailable}</span></div>`;

        return `
            <article class="listing-card">
                <div class="listing-address">${detailDash(item.address)}</div>
                <div class="listing-price">${publicFormatPrice(item.price_rub)}</div>
                <div class="listing-params">${params || '—'}</div>
                ${actions}
            </article>
        `;
    }).join("");
}

function renderDetail(detail) {
    detailState = { ...detail };

    document.getElementById("detail-title").textContent = detail.title || TEXT.titleFallback;
    document.getElementById("detail-subtitle").textContent = `${TEXT.regLabel}: ${detailDash(detail.reg_number)}`;

    const eisBtn = document.getElementById("btn-open-eis");
    if (detailState.eis_url) {
        eisBtn.href = detailState.eis_url;
        eisBtn.style.display = "inline-flex";
    } else {
        eisBtn.style.display = "none";
    }

    syncReserveButton(detailState);
    syncFavoriteState(detailState);
    renderFeatures(detailState);
    renderListings(detailState);
}

async function loadDetail() {
    const regNumber = window.PUBLIC_REG_NUMBER;
    const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(regNumber)}`);
    if (!resp.ok) {
        const detail = await publicExtractFriendlyError(resp, TEXT.detailLoadError);
        throw new Error(detail);
    }

    const detail = await resp.json();
    renderDetail(detail);
}

async function reserveProcurement() {
    const regNumber = window.PUBLIC_REG_NUMBER;
    if (reserveInFlight) return;

    const btn = document.getElementById("btn-reserve-zakupka");
    reserveInFlight = true;
    btn.disabled = true;
    btn.textContent = TEXT.reserveProgress;
    setReserveStatus(TEXT.reserveProgress);

    try {
        const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(regNumber)}/reserve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });

        if (resp.status === 401) {
            window.location.href = `/public/login?next=${encodeURIComponent(`/public/zakupki/${regNumber}`)}`;
            return;
        }

        if (resp.status === 409) {
            if (detailState) {
                detailState.is_reserved = true;
                syncReserveButton(detailState);
            }
            setReserveStatus(TEXT.reserveConflict, true);
            return;
        }

        if (!resp.ok) {
            const text = await publicExtractFriendlyError(resp, TEXT.reserveRequest);
            throw new Error(text);
        }

        const data = await resp.json();
        if (detailState) {
            detailState.is_reserved = true;
            detailState.reserved_until = data.expires_at || detailState.reserved_until || null;
            syncReserveButton(detailState);
        }
    } catch (error) {
        setReserveStatus(error.message || TEXT.reserveError, true);
    } finally {
        reserveInFlight = false;
    }
}

async function toggleFavorite() {
    const regNumber = window.PUBLIC_REG_NUMBER;
    if (favoriteInFlight) return;

    const btn = document.getElementById("btn-favorite");
    const action = btn.dataset.action || "favorite";
    favoriteInFlight = true;
    btn.disabled = true;

    try {
        const resp = await fetch(`/api/public/zakupki/${encodeURIComponent(regNumber)}/${action}`, { method: "POST" });
        if (resp.status === 401) {
            window.location.href = `/public/login?next=${encodeURIComponent(`/public/zakupki/${regNumber}`)}`;
            return;
        }
        if (!resp.ok) {
            const text = await publicExtractFriendlyError(resp, TEXT.favoriteRequest);
            throw new Error(text);
        }

        if (detailState) {
            detailState.is_favorite = action === "favorite";
            syncFavoriteState(detailState);
        }
    } catch (error) {
        setReserveStatus(error.message || TEXT.favoriteError, true);
    } finally {
        favoriteInFlight = false;
        btn.disabled = false;
    }
}

document.getElementById("btn-reserve-zakupka").addEventListener("click", reserveProcurement);
document.getElementById("btn-favorite").addEventListener("click", toggleFavorite);

loadDetail().catch((error) => {
    document.getElementById("detail-subtitle").textContent = `${TEXT.loadFailed}: ${error.message}`;
    document.getElementById("detail-features").innerHTML = "";
    document.getElementById("listings-container").innerHTML = "";
    document.getElementById("btn-reserve-zakupka").disabled = true;
    document.getElementById("btn-favorite").disabled = true;
});
