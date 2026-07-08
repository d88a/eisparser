from pathlib import Path


def _read_utf8(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_public_reservations_template_has_readable_russian():
    text = _read_utf8("src/web/templates/public_reservations.html")
    assert "Личный кабинет" in text
    assert "Активные брони" in text
    assert "История" in text
    assert "Избранное" in text


def test_public_reservations_js_has_readable_russian():
    text = _read_utf8("src/web/static/js/public_reservations.js")
    assert "Активные брони" in text
    assert "История броней" in text
    assert "Избранные закупки" in text
    assert "Снять бронь" in text


def test_view_service_status_labels_are_readable_russian():
    text = _read_utf8("src/services/view_service.py")
    assert "Новая" in text
    assert "ИИ готов" in text
    assert "Ошибка ИИ" in text
    assert "Есть варианты квартир" in text
    assert "Нет вариантов квартир" in text
