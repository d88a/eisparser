// app.js - Stage 1: Selection Screen

const USER_ID = 1;
const API_BASE = '/api';

document.addEventListener('DOMContentLoaded', () => {
    setupGlobalActions();
});

// Warn on reload
window.onbeforeunload = function () {
    return true;
};

let zakupkiData = [];
let currentLimit = 10;

async function loadData() {
    try {
        const response = await fetch(`${API_BASE}/stage1?user_id=${USER_ID}&limit=${currentLimit}`);
        if (!response.ok) throw new Error('Не удалось загрузить данные');

        zakupkiData = await response.json();
        renderTable(zakupkiData);
        updateStats();
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка загрузки данных');
    }
}

function renderTable(data) {
    const tbody = document.getElementById('zakupki-body');
    tbody.innerHTML = '';

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:40px; color:#999">Нет данных. Нажмите "Загрузить закупки с ЕИС"</td></tr>';
        return;
    }

    data.forEach(item => {
        const tr = document.createElement('tr');
        tr.dataset.reg = item.reg_number;

        tr.innerHTML = `
            <td><input type="checkbox" class="row-select" value="${item.reg_number}" onchange="updateSelectionStats()"></td>
            <td><a href="https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=${item.reg_number}" target="_blank">${item.reg_number}</a></td>
            <td>${item.update_date ? item.update_date.substring(0, 10) : '-'}</td>
            <td>${item.bid_end_date || '-'}</td>
            <td title="${item.description}">${item.description || '-'}</td>
        `;
        tbody.appendChild(tr);
    });
}

function toggleSelectAll(source) {
    const checkboxes = document.querySelectorAll('.row-select');
    checkboxes.forEach(cb => cb.checked = source.checked);
    updateSelectionStats();
}

function updateSelectionStats() {
    const selected = document.querySelectorAll('.row-select:checked').length;
    const btn = document.getElementById('btn-add-to-stage2');

    document.getElementById('stat-selected').textContent = selected;

    if (selected > 0) {
        btn.textContent = `➕ Добавить закупки (${selected})`;
        btn.disabled = false;
    } else {
        btn.textContent = `➕ Добавить закупки`;
        btn.disabled = true;
    }
}

function updateStats() {
    const total = zakupkiData.length;
    document.getElementById('stat-total').textContent = total;
    document.getElementById('stat-selected').textContent = 0;

    // Reset button
    const btn = document.getElementById('btn-add-to-stage2');
    btn.textContent = `➕ Добавить закупки`;
    btn.disabled = true;
}

function setupGlobalActions() {
    // "Add to Stage 2" button
    document.getElementById('btn-add-to-stage2').addEventListener('click', async () => {
        const btn = document.getElementById('btn-add-to-stage2');
        const status = document.getElementById('stage2-status');

        // Get selection
        const checkboxes = document.querySelectorAll('.row-select:checked');
        const selectedIds = Array.from(checkboxes).map(cb => cb.value);

        if (selectedIds.length === 0) {
            alert('Пожалуйста, выберите закупки галочками.');
            return;
        }

        if (!confirm(`Добавить ${selectedIds.length} закупок для ИИ-анализа?`)) return;

        btn.disabled = true;
        status.textContent = 'Добавление...';

        try {
            const response = await fetch(`${API_BASE}/actions/add_to_stage2`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: USER_ID,
                    reg_numbers: selectedIds
                })
            });

            const result = await response.json();

            if (result.status === 'ok') {
                status.textContent = 'Добавлено!';
                alert(`Добавлено ${result.count} закупок. Перейдите на вкладку "Stage 2: AI Review".`);
                // Reset selection
                document.getElementById('select-all').checked = false;
                document.querySelectorAll('.row-select:checked').forEach(cb => cb.checked = false);
                updateSelectionStats();
            } else {
                status.textContent = 'Ошибка';
                alert(`Ошибка: ${result.message}`);
            }
        } catch (error) {
            console.error(error);
            status.textContent = 'Ошибка соединения';
        } finally {
            btn.disabled = false;
        }
    });

    // Load from EIS button
    document.getElementById('btn-run-stage1').addEventListener('click', async () => {
        const btn = document.getElementById('btn-run-stage1');
        const status = document.getElementById('stage1-status');

        const input = prompt('Сколько новых закупок загрузить?', '10');
        if (input === null) return;

        const limit = parseInt(input, 10);
        if (isNaN(limit) || limit <= 0) {
            alert('Пожалуйста, введите корректное число');
            return;
        }

        currentLimit = limit;

        btn.disabled = true;
        status.textContent = 'Загрузка...';

        try {
            const response = await fetch(`${API_BASE}/actions/run_stage1`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ limit: limit })
            });

            const result = await response.json();

            if (result.status === 'ok') {
                status.textContent = 'Готово!';
                alert(result.message);
                loadData();
            } else {
                status.textContent = 'Ошибка';
                alert(`Ошибка: ${result.message}`);
            }
        } catch (error) {
            console.error(error);
            status.textContent = 'Ошибка соединения';
        } finally {
            btn.disabled = false;
        }
    });
}
