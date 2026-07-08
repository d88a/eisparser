function showSuccess(msgId) {
    const el = document.getElementById(msgId);
    if (!el) return;
    el.style.display = "flex";
    setTimeout(() => { el.style.display = "none"; }, 3000);
}

async function loadAccount() {
    const resp = await fetch("/api/public/account");
    if (resp.status === 401) {
        window.location.href = `/public/login?next=${encodeURIComponent("/public/account")}`;
        return;
    }
    if (!resp.ok) {
        throw new Error("Не удалось загрузить данные. Повторите позже.");
    }

    const data = await resp.json();
    document.getElementById("acc-display-name").value = data.display_name || "";
    document.getElementById("acc-email").value = data.email || "";

    // Set avatar initial
    const avatarEl = document.getElementById("acc-avatar");
    if (avatarEl && data.display_name) {
        const initials = data.display_name.split(" ").map(p => p[0]).join("").toUpperCase().slice(0, 2);
        avatarEl.textContent = initials;
    }
}

async function submitProfile(e) {
    e.preventDefault();

    const btn = document.getElementById("btn-save-profile");
    const displayName = String(document.getElementById("acc-display-name").value || "").trim();

    if (displayName.length < 2 || displayName.length > 120) {
        return;
    }

    btn.disabled = true;
    try {
        const resp = await fetch("/api/public/account/profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ display_name: displayName }),
        });

        if (resp.status === 401) {
            window.location.href = `/public/login?next=${encodeURIComponent("/public/account")}`;
            return;
        }
        if (!resp.ok) {
            const detail = await publicExtractFriendlyError(resp, "обновление профиля");
            throw new Error(detail);
        }

        showSuccess("profile-saved-msg");

        // Update avatar
        const avatarEl = document.getElementById("acc-avatar");
        if (avatarEl) {
            const initials = displayName.split(" ").map(p => p[0]).join("").toUpperCase().slice(0, 2);
            avatarEl.textContent = initials;
        }
    } catch (err) {
        alert(err.message || "Не удалось сохранить имя.");
    } finally {
        btn.disabled = false;
    }
}

async function submitPassword(e) {
    e.preventDefault();

    const btn = document.getElementById("btn-save-password");
    const currentPassword = document.getElementById("acc-current-password").value || "";
    const newPassword = document.getElementById("acc-new-password").value || "";
    const confirmPassword = document.getElementById("acc-confirm-password").value || "";

    if (newPassword.length < 8) {
        alert("Новый пароль должен быть не короче 8 символов.");
        return;
    }
    if (newPassword !== confirmPassword) {
        alert("Подтверждение пароля не совпадает.");
        return;
    }

    btn.disabled = true;
    try {
        const resp = await fetch("/api/public/account/password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword,
                confirm_password: confirmPassword,
            }),
        });

        if (resp.status === 401) {
            window.location.href = `/public/login?next=${encodeURIComponent("/public/account")}`;
            return;
        }
        if (!resp.ok) {
            const detail = await publicExtractFriendlyError(resp, "смена пароля");
            throw new Error(detail);
        }

        document.getElementById("password-form").reset();
        showSuccess("password-saved-msg");
    } catch (err) {
        alert(err.message || "Не удалось сменить пароль.");
    } finally {
        btn.disabled = false;
    }
}

document.getElementById("profile-form").addEventListener("submit", submitProfile);
document.getElementById("password-form").addEventListener("submit", submitPassword);

loadAccount().catch((err) => {
    alert(err.message || "Не удалось загрузить данные. Повторите позже.");
});
