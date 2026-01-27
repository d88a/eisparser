# project_real/project_root/gis/parser.py
"""
Упрощённый асинхронный парсер 2ГИС на Playwright.
Возвращает список объявлений (карточек) с базовыми полями.
"""
import asyncio
import re
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from .generator import find_coordinates_by_city, build_2gis_realty_url


async def close_popups(page):
    """
    Закрывает возможные всплывающие окна (cookies, модалки и т.п.).
    """
    selectors = [
        'button[role="button"][aria-label*="Согласен"]',
        'button[role="button"][aria-label*="Хорошо"]',
        'button[role="button"]:has-text("Понятно")',
    ]
    for sel in selectors:
        try:
            await page.click(sel, timeout=2000)
        except Exception:
            pass


async def parse_2gis_listings_async(
    city: str,
    rooms=None,  # Может быть int, list[int], или None
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    price_max: Optional[float] = None,
    max_count: int = 5,
) -> List[Dict]:
    """
    Асинхронный парсер объявлений 2ГИС.
    На практике можно допилить фильтры, пока берём первые несколько карточек из выдачи.
    """
    # Получаем координаты по городу
    coords = find_coordinates_by_city(city)
    if not coords:
        print(f"Координаты для города '{city}' не найдены")
        return []
    
    lat, lon = coords
    
    # Нормализуем rooms в rooms_counts
    rooms_counts = None
    if rooms is not None:
        if isinstance(rooms, int):
            rooms_counts = [rooms]
        elif isinstance(rooms, list):
            rooms_counts = rooms
    
    url = build_2gis_realty_url(
        lon=lon,
        lat=lat,
        area_min=area_min,
        area_max=area_max,
        rooms_counts=rooms_counts,
        price_max=price_max,
    )
    print(f"Открываем 2ГИС: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, timeout=60000)
            await asyncio.sleep(5)
            await close_popups(page)
            cards = await page.query_selector_all('[data-testid="list-item"]')
            results: List[Dict] = []
            for card in cards:
                # Попробуем извлечь количество комнат из карточки
                rooms_el = await card.query_selector('div:has-text("к"), div:has-text("комн"), span:has-text("к"), span:has-text("комн"), [data-icon*="room"]')
                rooms_text = ""
                parsed_rooms = None
                if rooms_el:
                    rooms_text = await rooms_el.inner_text()
                    rooms_match = re.search(r'(\d+)(?:-|\s)*(?:комнатн|комн|к)', rooms_text, re.IGNORECASE)
                    if rooms_match:
                        parsed_rooms = int(rooms_match.group(1))
                        # --- ФИЛЬТРАЦИЯ ПО КОМНАМ ---
                        if rooms is not None:
                            if isinstance(rooms, list):
                                if parsed_rooms not in rooms:
                                    continue
                            elif isinstance(rooms, int):
                                if parsed_rooms != rooms:
                                    continue
                        # --- КОНЕЦ ФИЛЬТРАЦИИ ---
                # --- (Продолжение извлечения других данных) ---
                address_el = await card.query_selector('[data-testid="address"]')
                address = await address_el.inner_text() if address_el else ""
                title_el = await card.query_selector('h3, h2')
                title = await title_el.inner_text() if title_el else ""
                price_el = await card.query_selector('[data-testid="price"]')
                price_text = await price_el.inner_text() if price_el else ""
                link_el = await card.query_selector('a[href]')
                link = await link_el.get_attribute("href") if link_el else ""
                results.append(
                    {
                        "title": title.strip(),
                        "address": address.strip(),
                        "price_raw": price_text.strip(),
                        "link": link,
                        "parsed_rooms": parsed_rooms,
                        "rooms_filter_applied": rooms,
                    }
                )
                if len(results) >= max_count:
                    break
            await browser.close()
            print(f"Найдено объявлений в 2ГИС: {len(results)}")
            return results
        except Exception as e:
            print(f"Ошибка при работе с 2ГИС: {e}")
            await browser.close()
            return []


def parse_2gis_listings(
    city: str,
    rooms=None,
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    price_max: Optional[float] = None,
    max_count: int = 5,
) -> List[Dict]:
    """
    Синхронная обёртка над асинхронным парсером.
    """
    return asyncio.run(
        parse_2gis_listings_async(
            city=city,
            rooms=rooms,
            area_min=area_min,
            area_max=area_max,
            price_max=price_max,
            max_count=max_count,
        )
    )
