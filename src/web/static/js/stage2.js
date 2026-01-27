// stage2.js - AI Review with Overrides

const USER_ID = 1;
const API_BASE = '/api';

let currentData = [];
let selectedRegNumber = null;
let selectedItems = new Set(); // For Stage 3 selection
let currentOverrides = {}; // {field_name: value}
let currentEditField = null;

// Field definitions for display
const AI_FIELDS = [
    { key: 'ai_zakupka_name', label: 'Название' },
    { key: 'ai_city', label: 'Город' },
    { key: 'ai_address', label: 'Адрес' },
    { key: 'initial_price', label: 'Начальная цена', format: v => v ? v.toLocaleString('ru-RU') + ' ₽' : '-' },
    { key: 'area', label: 'Площадь', custom: true }, // Custom handling for min-max
    { key: 'ai_rooms', label: 'Комнаты' },
    { key: 'ai_floor', label: 'Этаж' },
    { key: 'ai_building_floors_min', label: 'Этажность здания' },
    { key: 'ai_year_build', label: 'Год постройки' },
    { key: 'ai_wear_percent', label: 'Износ %' },
    { key: 'ai_zakazchik', label: 'Заказчик' },
];

document.addEventListener('DOMContentLoaded', () => {
    loadList();
    document.getElementById('btn-run-stage3').addEventListener('click', runStage3);
});

async function loadList() {
    try {
        const response = await fetch(`${API_BASE}/stage2?user_id=${USER_ID}`);
        if (!response.ok) throw new Error('Failed to load');

        currentData = await response.json();
        renderList(currentData);
        updateStats();

        document.getElementById('review-workspace').innerHTML = '<div class="empty-state">Выберите закупку слева для проверки</div>';
        selectedRegNumber = null;
    } catch (e) {
        console.error(e);
        alert('Ошибка загрузки данных');
    }
}

function renderList(data) {
    const list = document.getElementById('review-list');
    list.innerHTML = '';

    if (data.length === 0) {
        list.innerHTML = '<div style="padding:20px; text-align:center; color:#999">Нет закупок для проверки.<br>Добавьте их на Stage 1.</div>';
        return;
    }

    data.forEach(item => {
        const div = document.createElement('div');
        div.className = 'list-item' + (selectedItems.has(item.reg_number) ? ' checked' : '');
        div.dataset.reg = item.reg_number;

        div.innerHTML = `
            <input type="checkbox" class="stage3-checkbox" ${selectedItems.has(item.reg_number) ? 'checked' : ''} 
                   onclick="event.stopPropagation(); toggleStage3Selection('${item.reg_number}', this.checked)">
            <div class="list-item-content" onclick="selectItem('${item.reg_number}')">
                <div class="list-item-header">${item.reg_number}</div>
                <div class="list-item-desc">
                    ${item.ai_city || '?'} | ${item.ai_area_min || '?'} м² | ${item.initial_price ? (item.initial_price / 1000000).toFixed(1) + 'М' : '-'}
                </div>
            </div>
        `;
        list.appendChild(div);
    });
}

function toggleStage3Selection(regNumber, checked) {
    if (checked) {
        selectedItems.add(regNumber);
    } else {
        selectedItems.delete(regNumber);
    }
    updateStats();
    // Update list item styling
    const listItem = document.querySelector(`.list-item[data-reg="${regNumber}"]`);
    if (listItem) listItem.classList.toggle('checked', checked);
}

async function selectItem(regNumber) {
    selectedRegNumber = regNumber;
    const item = currentData.find(i => i.reg_number === regNumber);
    if (!item) return;

    // Highlight list item
    document.querySelectorAll('.list-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`.list-item[data-reg="${regNumber}"]`)?.classList.add('active');

    // Fetch overrides for this item
    try {
        const resp = await fetch(`${API_BASE}/overrides/${regNumber}?user_id=${USER_ID}`);
        currentOverrides = await resp.json();
    } catch (e) {
        currentOverrides = {};
    }

    renderWorkspace(item);
}

function renderWorkspace(item) {
    const workspace = document.getElementById('review-workspace');

    let fieldsHtml = '';
    AI_FIELDS.forEach(f => {
        let aiValue, displayValue, overrideKey;

        if (f.custom && f.key === 'area') {
            // Custom area handling: combine min and max
            const areaMin = item.ai_area_min;
            const areaMax = item.ai_area_max;
            if (areaMin && areaMax && areaMin !== areaMax) {
                aiValue = `${areaMin} м² - ${areaMax} м²`;
            } else if (areaMin) {
                aiValue = `${areaMin} м²`;
            } else if (areaMax) {
                aiValue = `${areaMax} м²`;
            } else {
                aiValue = null;
            }
            displayValue = aiValue ?? '-';
            overrideKey = 'area';  // Use 'area' for override
        } else {
            aiValue = item[f.key];
            displayValue = f.format ? f.format(aiValue) : (aiValue ?? '-');
            overrideKey = f.key.replace('ai_', '');
        }

        const override = currentOverrides[overrideKey];
        const hasOverride = override !== undefined && override !== null;

        fieldsHtml += `
            <div class="field-row ${hasOverride ? 'has-override' : ''}">
                <div class="field-label">
                    <span>${f.label}</span>
                    <span class="edit-btn" onclick="openEditModal('${overrideKey}', '${f.label}', '${String(aiValue ?? '').replace(/'/g, "\\'")}')">✏️ изменить</span>
                </div>
                <div class="field-values">
                    <span class="ai-value">${displayValue}</span>
                    ${hasOverride ? `<span class="override-value">→ ${override}</span>` : ''}
                </div>
            </div>
        `;
    });

    workspace.innerHTML = `
        <div class="review-header">
            <div>
                <h3>${item.reg_number}</h3>
                <span style="font-size:0.8em; color:#666">${item.update_date ? item.update_date.substring(0, 10) : ''}</span>
            </div>
            <a href="https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=${item.reg_number}" 
               target="_blank" class="btn btn-sm">Открыть на ЕИС</a>
        </div>
        <div class="review-body">
            <div class="fields-panel">${fieldsHtml}</div>
            <div class="text-panel">
                <div class="text-panel-header">Документация</div>
                <div class="text-panel-content">${item.combined_text || 'Текст закупки отсутствует...'}</div>
            </div>
        </div>
    `;
}

function openEditModal(fieldKey, fieldLabel, aiValue) {
    currentEditField = fieldKey;
    document.getElementById('modal-field-name').textContent = fieldLabel;
    document.getElementById('modal-ai-value').textContent = aiValue || '-';
    document.getElementById('modal-input').value = currentOverrides[fieldKey] || aiValue || '';
    document.getElementById('edit-modal').classList.add('active');
    document.getElementById('modal-input').focus();
}

function closeModal() {
    document.getElementById('edit-modal').classList.remove('active');
    currentEditField = null;
}

async function saveOverride() {
    if (!currentEditField || !selectedRegNumber) return;

    const newValue = document.getElementById('modal-input').value.trim();

    try {
        const resp = await fetch(`${API_BASE}/overrides`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: USER_ID,
                reg_number: selectedRegNumber,
                field_name: currentEditField,
                value: newValue
            })
        });

        const result = await resp.json();
        if (result.status === 'ok') {
            currentOverrides[currentEditField] = newValue;
            // Re-render workspace
            const item = currentData.find(i => i.reg_number === selectedRegNumber);
            if (item) renderWorkspace(item);
        } else {
            alert('Ошибка сохранения');
        }
    } catch (e) {
        console.error(e);
        alert('Ошибка соединения');
    }

    closeModal();
}

async function runStage3() {
    if (selectedItems.size === 0) {
        alert('Выберите закупки галочками для генерации ссылок');
        return;
    }

    if (!confirm(`Сгенерировать ссылки для ${selectedItems.size} закупок?`)) return;

    const btn = document.getElementById('btn-run-stage3');
    btn.disabled = true;
    btn.textContent = 'Генерация...';

    try {
        // First, save decisions for selected items
        for (const regNumber of selectedItems) {
            await fetch(`${API_BASE}/decisions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: USER_ID,
                    reg_number: regNumber,
                    stage: 2,
                    decision: 'approved',
                    comment: null
                })
            });
        }

        // Then run Stage 3
        const response = await fetch(`${API_BASE}/actions/run_stage3`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: USER_ID })
        });

        const result = await response.json();
        alert(result.status === 'ok'
            ? `Успешно! Сгенерировано ссылок: ${result.generated || 0}`
            : `Ошибка: ${result.message}`);

        // Reload list
        loadList();
        selectedItems.clear();
        updateStats();
    } catch (e) {
        console.error(e);
        alert('Ошибка соединения');
    } finally {
        btn.disabled = false;
        updateStats();
    }
}

function updateStats() {
    document.getElementById('stat-count').textContent = currentData.length;
    document.getElementById('stat-selected').textContent = selectedItems.size;

    const btn = document.getElementById('btn-run-stage3');
    btn.disabled = selectedItems.size === 0;
    btn.textContent = `🚀 Запустить Stage 3 (${selectedItems.size} выбрано)`;
}
