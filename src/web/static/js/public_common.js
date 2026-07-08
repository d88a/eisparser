function publicFormatPrice(value) {
    if (value === null || value === undefined || value === "") return "—";
    const num = Number(value);
    if (!Number.isFinite(num)) return "—";
    return `${new Intl.NumberFormat("ru-RU").format(Math.round(num))}\u00A0₽`;
}

function publicTextOrDash(value) {
    if (value === null || value === undefined || value === "") return "—";
    return String(value);
}

function publicFormatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return publicTextOrDash(value);
    return new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    }).format(date);
}

async function publicReadApiError(resp, fallbackText) {
    try {
        const data = await resp.json();
        if (data && data.detail) {
            return String(data.detail);
        }
    } catch (error) {
        // ignore malformed JSON errors
    }
    return fallbackText;
}

function publicFriendlyErrorMessage(status, actionText) {
    if (status === 401) return "Требуется авторизация.";
    if (status === 403) return "Недостаточно прав для этого действия.";
    if (status === 404) return "Запись не найдена.";
    if (status === 409) return "Операция не может быть выполнена: объект уже занят или его состояние изменилось.";
    if (status === 422) return "Операция недоступна для текущего состояния записи.";
    if (status >= 500) return `Сервис временно недоступен. Попробуйте позже (${actionText}).`;
    return `Не удалось выполнить действие: ${actionText}.`;
}

async function publicExtractFriendlyError(resp, actionText) {
    const fallback = publicFriendlyErrorMessage(resp.status, actionText);
    const detail = await publicReadApiError(resp, fallback);
    if (!detail || /^HTTP\s+\d+/i.test(String(detail).trim())) {
        return fallback;
    }
    return detail;
}

function publicCabinetMessage(kind) {
    if (kind === "load") return "Не удалось загрузить данные. Повторите позже.";
    if (kind === "unreserve") return "Не удалось снять бронь. Обновите страницу и повторите.";
    if (kind === "unfavorite") return "Не удалось обновить избранное. Повторите позже.";
    return "Не удалось выполнить действие. Повторите позже.";
}

function initAccountMenu() {
    const menu = document.querySelector("[data-account-menu]");
    if (!menu) return;

    const trigger = menu.querySelector("[data-account-trigger]");
    if (!trigger) return;

    const closeMenu = () => {
        menu.classList.remove("open");
    };

    trigger.addEventListener("click", (event) => {
        event.stopPropagation();
        menu.classList.toggle("open");
    });

    document.addEventListener("click", (event) => {
        if (!menu.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeMenu();
        }
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAccountMenu);
} else {
    initAccountMenu();
}

// Logout button
document.querySelectorAll(".btn-logout").forEach((btn) => {
    btn.addEventListener("click", async () => {
        try {
            await fetch("/api/public/logout", { method: "POST" });
        } catch (_) { /* ignore */ }
        window.location.href = "/public/zakupki";
    });
});
