# realty_scraper/two_gis_playwright.py
"""
Playwright-based scraper для сбора объявлений из 2ГИС.
Использует playwright-stealth для обхода детекции ботов.
"""
import asyncio
import re
import time
from typing import List, Optional
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from .models import Listing, ListingResult
from .parsers import (
    parse_price, parse_area, parse_floor, parse_rooms,
    parse_building_year, classify_external_source
)

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    STAGE4_HEADLESS, STAGE4_RATE_LIMIT_S,
    STAGE4_MAX_RETRIES, STAGE4_SCROLL_TIMEOUT_S,
    STAGE4_PAGE_TIMEOUT_S, STAGE4_USE_REAL_CHROME
)


async def close_popups(page):
    """Закрывает возможные всплывающие окна (cookies, модалки и т.п.)."""
    selectors = [
        'button[role="button"][aria-label*="Согласен"]',
        'button[role="button"][aria-label*="Хорошо"]',
        'button[role="button"]:has-text("Понятно")',
        'button:has-text("OK")',
        'button:has-text("Принять")',
    ]
    for sel in selectors:
        try:
            await page.click(sel, timeout=2000)
        except Exception:
            pass


async def scroll_listings_panel(page, scroll_count: int = 5):
    """
    Прокручивает панель со списком объявлений.
    Скроллим внутри левой панели, а не всю страницу.
    """
    # Позиция мыши над панелью списка (левая часть экрана)
    panel_x = 200
    panel_y = 400
    
    await page.mouse.move(panel_x, panel_y)
    await asyncio.sleep(0.5)
    
    for i in range(scroll_count):
        await page.mouse.wheel(0, 500)
        await asyncio.sleep(1)
        print(f"  Прокрутка {i + 1}/{scroll_count}")


async def collect_listings_async(
    url: str,
    top_n: int = 20,
    headless: bool = True,
    proxy: str = None,
    get_details: bool = False
) -> ListingResult:
    """
    Асинхронный сбор объявлений из 2ГИС с использованием stealth режима.
    
    Args:
        proxy: Прокси в формате "http://user:pass@host:port" или "http://host:port"
        get_details: Если True, кликает по каждой карточке для получения года постройки и этажности
    """
    result = ListingResult(
        query_url=url,
        top_n=top_n
    )
    
    print(f"Открываю {url[:80]}...")
    
    async with async_playwright() as p:
        # Аргументы для обхода детекции
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
        ]
        
        if STAGE4_USE_REAL_CHROME:
            try:
                browser = await p.chromium.launch(
                    headless=headless,
                    channel='chrome',
                    args=browser_args
                )
                print("Используется реальный Chrome")
            except Exception:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=browser_args
                )
                print("Fallback: используется Chromium")
        else:
            browser = await p.chromium.launch(
                headless=headless,
                args=browser_args
            )
            print("Используется Chromium (режим для хостинга)")
        
        # Настройки контекста
        context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'locale': 'ru-RU',
            'timezone_id': 'Asia/Novosibirsk',
        }
        
        # Добавляем прокси если указан
        if proxy:
            context_options['proxy'] = {'server': proxy}
            print(f"Используется прокси: {proxy[:30]}...")
        
        # Создаём контекст и страницу
        context = await browser.new_context(**context_options)
        page = await context.new_page()
        
        # Применяем stealth для обхода детекции ботов
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        
        try:
            # Случайная задержка перед загрузкой (human-like)
            await asyncio.sleep(1 + (hash(url) % 3))
            
            # Timeout из конфига
            await page.goto(url, timeout=STAGE4_PAGE_TIMEOUT_S * 1000)
            print("Страница загружена, ожидаю рендеринг...")
            await asyncio.sleep(20)  # Увеличено до 20 сек для медленных ПК
            await close_popups(page)
            
            # Ищем карточки по разным селекторам
            cards = await page.query_selector_all('[data-testid="list-item"]')
            print(f"Найдено {len(cards)} карточек по [data-testid='list-item']")
            
            if not cards:
                cards = await page.query_selector_all('article')
                print(f"Fallback: найдено {len(cards)} карточек по 'article'")
            
            if not cards:
                # Попробуем найти любые элементы с ценой
                all_elements = await page.query_selector_all('*')
                print(f"Всего элементов на странице: {len(all_elements)}")
                
                # Сделаем скриншот для диагностики
                try:
                    screenshot_path = os.path.join(os.path.dirname(__file__), '..', 'results', 'debug_screenshot.png')
                    await page.screenshot(path=screenshot_path, full_page=False)
                    print(f"Скриншот сохранён: {screenshot_path}")
                except Exception as e:
                    print(f"Не удалось сохранить скриншот: {e}")
            
            # Если карточек меньше чем нужно, прокручиваем
            if len(cards) < top_n and len(cards) > 0:
                scroll_needed = (top_n - len(cards)) // 3 + 2
                print(f"Прокрутка панели списка...")
                await scroll_listings_panel(page, scroll_needed)
                
                cards = await page.query_selector_all('[data-testid="list-item"]')
                if not cards:
                    cards = await page.query_selector_all('article')
                print(f"После прокрутки найдено {len(cards)} карточек")
            
            listings = []
            
            for idx, card in enumerate(cards[:top_n]):
                try:
                    listing = await parse_card_async(card, idx + 1)
                    if listing:
                        # Если нужны детали — кликаем по карточке
                        if get_details:
                            listing = await get_listing_details_async(page, card, listing)
                        listings.append(listing)
                except Exception as e:
                    print(f"Ошибка при парсинге карточки {idx + 1}: {e}")
            
            result.items = listings
            result.actual_n = len(listings)
            print(f"Собрано {len(listings)} объявлений")
            
        except Exception as e:
            result.error = f"Error: {str(e)}"
            print(f"Ошибка: {e}")
        finally:
            await browser.close()
    
    return result


async def parse_card_async(card, rank: int) -> Optional[Listing]:
    """Асинхронно парсит данные с одной карточки."""
    try:
        # Получаем весь текст карточки
        card_text = await card.inner_text()
        
        # Заголовок
        title_el = await card.query_selector('h3, h2, a')
        title = await title_el.inner_text() if title_el else card_text.split('\n')[0]
        
        # Парсим цену из текста карточки
        price = parse_price(card_text)
        
        if not price:
            return None
        
        # Адрес
        address_el = await card.query_selector('[data-testid="address"]')
        if address_el:
            address = await address_el.inner_text()
        else:
            # Ищем строку похожую на адрес
            address = ""
            lines = card_text.split('\n')
            for line in lines:
                line = line.strip()
                if any(kw in line.lower() for kw in ['улица', 'ул.', 'пр.', 'пр-т', 'район', 'мкр']):
                    address = line
                    break
            
            if not address and len(lines) > 1:
                for line in lines[1:]:
                    if line.strip() and '₽' not in line:
                        address = line.strip()
                        break
        
        # Ссылка 2ГИС
        link_el = await card.query_selector('a[href]')
        link = await link_el.get_attribute("href") if link_el else ""
        if link and link.startswith('/'):
            link = f"https://2gis.ru{link}"
        
        # Ищем внешнюю ссылку на ДомКлик/Циан
        external_url = None
        external_source = None
        all_links = await card.query_selector_all('a[href]')
        for a in all_links:
            href = await a.get_attribute("href")
            if href:
                href_lower = href.lower()
                if 'domclick' in href_lower or 'dom.click' in href_lower:
                    external_url = href
                    external_source = 'domclick'
                    break
                elif 'cian' in href_lower:
                    external_url = href
                    external_source = 'cian'
                    break
                elif 'avito' in href_lower:
                    external_url = href
                    external_source = 'avito'
                    break
        
        # Парсим характеристики
        rooms = parse_rooms(title)
        area = parse_area(title)
        floor_info = parse_floor(title)
        floor = floor_info[0] if floor_info else None
        building_floors = floor_info[1] if floor_info and len(floor_info) > 1 else None
        
        return Listing(
            rank=rank,
            price_rub=price,
            address=address or "Адрес не указан",
            rooms=rooms,
            area_m2=area,
            floor=floor,
            building_floors=building_floors,
            two_gis_url=link,
            external_url=external_url,
            external_source=external_source
        )
        
    except Exception as e:
        print(f"Ошибка парсинга карточки: {e}")
        return None


async def get_listing_details_async(page, card, listing: Listing) -> Listing:
    """
    Кликает по карточке и извлекает дополнительные данные из детальной панели.
    
    Извлекает:
    - building_year (год постройки)
    - building_floors (этажность здания, если не было получено из превью)
    """
    try:
        print(f"  Получение деталей для #{listing.rank}...")
        
        # Клик по карточке
        await card.click()
        await asyncio.sleep(2)  # Ждём появления панели
        
        # Ищем текст страницы для извлечения данных
        page_text = await page.inner_text('body')
        
        # Ищем год постройки (паттерны: "1985 год", "построен в 1985", "год постройки: 1985")
        import re
        year_patterns = [
            r'(\d{4})\s*(?:год|г\.?)\b',
            r'построен\w*\s+(?:в\s+)?(\d{4})',
            r'год\s+постройки[\s:]+(\d{4})',
            r'дата\s+постройки[\s:]+(\d{4})',
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                # Проверяем разумность года (1900-2025)
                if 1900 <= year <= 2025:
                    listing.building_year = year
                    break
        
        # Ищем этажность здания если не была извлечена ранее
        if not listing.building_floors:
            floor_patterns = [
                r'(\d+)[/-]этажн',
                r'этаж(?:ей|а)?\s*(?:в\s+доме)?[\s:]+(\d+)',
                r'(\d+)\s*этаж\w*\s+(?:дом|здани)',
            ]
            for pattern in floor_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    floors = int(match.group(1))
                    if 1 <= floors <= 100:
                        listing.building_floors = floors
                        break
        
        # Закрываем панель (клик вне или кнопка закрытия)
        try:
            close_btn = await page.query_selector('[aria-label="close"], [aria-label="Закрыть"], .close-button, button:has-text("×")')
            if close_btn:
                await close_btn.click()
            else:
                # Кликаем на карту или другую область
                await page.keyboard.press('Escape')
        except:
            pass
        
        await asyncio.sleep(0.5)
        
        if listing.building_year:
            print(f"    Год постройки: {listing.building_year}")
        
    except Exception as e:
        print(f"    Ошибка получения деталей: {e}")
    
    return listing


def collect_top_listings(url: str, top_n: int = 20, headless: bool = True, proxy: str = None, get_details: bool = False) -> ListingResult:
    """Синхронная обёртка над асинхронным парсером."""
    return asyncio.run(
        collect_listings_async(url=url, top_n=top_n, headless=headless, proxy=proxy, get_details=get_details)
    )


class TwoGisScraper:
    """Скрапер для сбора объявлений недвижимости из 2ГИС."""
    
    def __init__(self, headless: bool = None, proxy: str = None, get_details: bool = False):
        self.headless = headless if headless is not None else STAGE4_HEADLESS
        self.proxy = proxy
        self.get_details = get_details
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def collect_listings(self, url: str, top_n: int = 20) -> ListingResult:
        """Собирает top_n объявлений по заданной ссылке."""
        return collect_top_listings(url, top_n, self.headless, self.proxy, self.get_details)
    
    def get_listing_details(self, listing: Listing) -> Listing:
        """Получает дополнительные детали объявления."""
        return listing
