"""
Сервис для загрузки закупок с ЕИС (zakupki.gov.ru).
"""
import os
import re
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup

from config.settings import settings
from models.zakupka import Zakupka
from repositories.zakupka_repo import ZakupkaRepository
from utils.logger import get_logger


class EISDownloaderService:
    """
    Сервис для загрузки закупок с ЕИС.
    
    Методы:
        search_zakupki: Поиск закупок по запросу
        download_documents: Загрузка документов закупки
        download_and_save: Полный цикл загрузки и сохранения
    """
    
    # URL для поиска закупок (ОКПД2 68.10.11 = покупка жилья)
    # Параметры:
    #   - sortBy=UPDATE_DATE — сортировка по дате обновления
    #   - fz44=on — только 44-ФЗ
    #   - orderStages=AF — стадия "подача заявок" (AF = Application Filing)
    #   - okpd2IdsCodes=68.10.11.000 — код ОКПД2 (покупка жилья)
    BASE_SEARCH_URL = (
        "https://zakupki.gov.ru/epz/order/extendedsearch/results.html"
        "?morphology=on"
        "&search-filter=%D0%94%D0%B0%D1%82%D0%B5+%D0%BE%D0%B1%D0%BD%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%B8%D1%8F"
        "&sortDirection=false"
        "&recordsPerPage=_10"
        "&showLotsInfoHidden=false"
        "&sortBy=UPDATE_DATE"
        "&fz44=on"
        "&af=on"
        "&orderStages=AF"
        "&currencyIdGeneral=-1"
        "&okpd2Ids=8890776"
        "&okpd2IdsCodes=68.10.11.000"
        "&pageNumber={page}"
    )
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    # Ключевые слова для исключения
    EXCLUDED_KEYWORDS = [
        "многолотовый", "несколько объектов", "комплекс",
        "долевое строительство", "ДДУ", "первичном",
        "две", "три", "четыре", "помещений"
    ]
    
    def __init__(
        self,
        zakupka_repo: ZakupkaRepository = None,
        zakupki_dir: str = None
    ):
        """
        Args:
            zakupka_repo: Репозиторий для сохранения закупок
            zakupki_dir: Директория для хранения документов
        """
        self.repo = zakupka_repo
        self.zakupki_dir = Path(zakupki_dir or settings.zakupki_dir)
        self.logger = get_logger("EISDownloaderService")
    
    def search_zakupki(
        self,
        limit: int = 10,
        pages_to_scan: int = 20
    ) -> List[Dict]:
        """
        Поиск закупок на ЕИС по ОКП2 68.10.11 (покупка жилья).
        
        Args:
            limit: Максимальное количество результатов
            pages_to_scan: Количество страниц для сканирования
        
        Returns:
            Список словарей с данными закупок
        """
        self.logger.info(f"Поиск закупок ОКПД2 68.10.11, лимит: {limit}")
        
        all_purchases: List[Dict] = []
        page = 1
        
        while page <= pages_to_scan and len(all_purchases) < limit * 5:
            self.logger.debug(f"Загружаем страницу {page}...")
            
            html = self._fetch_search_page(page)
            if not html:
                # Если первая страница не загрузилась — сайт недоступен, прерываем
                if page == 1:
                    self.logger.error("Сайт ЕИС недоступен (первая страница не загрузилась после 3 попыток)")
                    return []
                # Для остальных страниц — продолжаем, возможно временный сбой
                page += 1
                continue
            
            page_purchases = self._parse_purchases_from_html(html)
            if not page_purchases:
                page += 1
                continue
            
            # Фильтруем по исключающим ключевым словам
            for p in page_purchases:
                desc_lower = (p.get("description") or "").lower()
                excluded = False
                for keyword in self.EXCLUDED_KEYWORDS:
                    if keyword in desc_lower:
                        self.logger.debug(f"Пропуск {p['reg_number']}: '{keyword}'")
                        excluded = True
                        break
                if not excluded:
                    all_purchases.append(p)
            
            page += 1
            time.sleep(1)
        
        # Сортируем по дате и берём нужное количество
        all_purchases.sort(key=lambda x: x.get("update_date", datetime.min), reverse=True)
        selected = all_purchases[:limit]
        
        self.logger.info(f"Найдено {len(selected)} закупок")
        return selected
    
    def download_documents(self, reg_number: str) -> Optional[str]:
        """
        Загружает все документы закупки и создаёт combined_text.txt.
        Сначала загружается печатная форма, затем документы.
        
        Args:
            reg_number: Регистрационный номер закупки
        
        Returns:
            Путь к combined_text.txt или None
        """
        zakupka_dir = self.zakupki_dir / reg_number
        zakupka_dir.mkdir(parents=True, exist_ok=True)
        
        combined_path = zakupka_dir / "combined_text.txt"
        
        # Если уже существует — пропускаем
        if combined_path.exists():
            self.logger.debug(f"combined_text.txt для {reg_number} уже существует")
            return str(combined_path)
        
        all_texts = []
        
        # 1. Загружаем печатную форму
        print_form_text = self._get_print_form(reg_number)
        if print_form_text:
            all_texts.append(f"=== ПЕЧАТНАЯ ФОРМА ===\n{print_form_text}\n")
            self.logger.debug(f"Печатная форма загружена для {reg_number}")
        
        # 2. Получаем список документов
        docs = self._get_documents_list(reg_number)
        if docs:
            # Скачиваем и извлекаем текст
            docs_dir = zakupka_dir / "documents"
            docs_dir.mkdir(exist_ok=True)
            
            for doc in docs:
                file_path = self._download_document(doc, docs_dir)
                if not file_path:
                    continue
                
                text = self._extract_text(file_path)
                if text:
                    all_texts.append(f"=== Документ: {doc['name']} ===\n{text}\n")
        
        if not all_texts:
            self.logger.warning(f"Не удалось извлечь текст для {reg_number}")
            return None
        
        # Сохраняем объединённый текст
        combined_text = "\n".join(all_texts)
        with open(combined_path, "w", encoding="utf-8") as f:
            f.write(combined_text)
        
        self.logger.info(f"Сохранён combined_text.txt для {reg_number}")
        return str(combined_path)
    
    def _get_print_form(self, reg_number: str) -> Optional[str]:
        """
        Получает текст печатной формы закупки.
        
        Args:
            reg_number: Регистрационный номер закупки
        
        Returns:
            Текст печатной формы или None
        """
        # URL печатной формы (универсальный для всех типов закупок)
        url = f"https://zakupki.gov.ru/epz/order/notice/printForm/view.html?regNumber={reg_number}"
        
        try:
            resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Удаляем скрипты и стили
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Извлекаем весь текст страницы
            text = soup.get_text(separator="\n", strip=True)
            
            # Убираем лишние пустые строки
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            result = "\n".join(lines)
            
            if result and len(result) > 100:
                self.logger.debug(f"Печатная форма загружена для {reg_number}: {len(result)} символов")
                return result
                
        except Exception as e:
            self.logger.debug(f"Ошибка загрузки печатной формы: {e}")
        
        return None
    
    def download_and_save(
        self,
        limit: int = 10
    ) -> Tuple[int, List[str]]:
        """
        Полный цикл: поиск, загрузка документов, сохранение в БД.
        
        Args:
            limit: Максимальное количество
        
        Returns:
            Кортеж (количество сохранённых, список ошибок)
        """
        errors = []
        saved = 0
        
        # Поиск закупок
        purchases = self.search_zakupki(limit)
        
        for p in purchases:
            reg_number = p.get("reg_number", "")
            try:
                # Загружаем документы
                combined_path = self.download_documents(reg_number)
                
                # Читаем текст
                combined_text = ""
                if combined_path and os.path.exists(combined_path):
                    with open(combined_path, "r", encoding="utf-8") as f:
                        combined_text = f.read()
                
                # Создаём объект Zakupka
                zakupka = Zakupka(
                    reg_number=reg_number,
                    description=p.get("description", ""),
                    update_date=str(p.get("update_date", "")),
                    bid_end_date=p.get("bid_end_date", ""),
                    initial_price=p.get("initial_price"),
                    link=p.get("link", ""),
                    combined_text=combined_text
                )
                
                # Сохраняем
                if self.repo and self.repo.save(zakupka):
                    saved += 1
                    self.logger.info(f"Сохранена закупка: {reg_number}")
                    
            except Exception as e:
                errors.append(f"{reg_number}: {e}")
                self.logger.error(f"Ошибка обработки {reg_number}: {e}")
        
        return saved, errors
    
    # ---- Приватные методы ----
    
    def _fetch_search_page(self, page: int) -> Optional[str]:
        """Загружает HTML страницы поиска."""
        url = self.BASE_SEARCH_URL.format(page=page)
        
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=30)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                self.logger.warning(f"Попытка {attempt+1}/3: {e}")
                time.sleep(5)
        
        return None
    
    def _parse_purchases_from_html(self, html: str) -> List[Dict]:
        """Парсит HTML страницы поиска."""
        soup = BeautifulSoup(html, "html.parser")
        blocks = soup.find_all("div", class_="search-registry-entry-block")
        if not blocks:
            blocks = soup.find_all("div", class_="registry-entry__form")
        
        results = []
        for block in blocks:
            try:
                # Номер и ссылка
                num_block = block.find("div", class_="registry-entry__header-mid__number")
                if not num_block:
                    continue
                
                link_el = num_block.find("a", href=True)
                if not link_el:
                    continue
                
                href = link_el["href"]
                if "regNumber=" in href:
                    reg_number = href.split("regNumber=")[1].split("&")[0]
                else:
                    reg_number = link_el.get_text(strip=True)
                
                purchase_link = "https://zakupki.gov.ru" + href if href.startswith("/") else href
                
                # Описание
                desc_el = block.find("div", class_="registry-entry__body-value")
                description = desc_el.get_text(strip=True) if desc_el else ""
                
                # Дата обновления
                date_el = block.find("div", class_="data-block__value")
                date_text = date_el.get_text(strip=True) if date_el else ""
                update_date = self._parse_date(date_text)
                
                # --- Логика извлечения цены и даты окончания ---
                bid_end_date = ""
                initial_price = None

                # Собираем все возможные блоки с информацией
                possible_blocks = block.select(".data-block, .registry-entry__body-block, .price-block")
                
                for db in possible_blocks:
                    # Ищем заголовок (title)
                    title_el = db.select_one(".data-block__title, .registry-entry__body-title, .price-block__title")
                    
                    if not title_el:
                        continue
                        
                    title_text = title_el.get_text(strip=True).lower()
                    
                    # Ищем значение (value)
                    value_el = db.select_one(".data-block__value, .registry-entry__body-value, .price-block__value")
                    
                    if not value_el:
                        continue
                        
                    if "окончани" in title_text:
                        bid_end_date = value_el.get_text(strip=True)
                    elif "начальная цена" in title_text:
                        price_text = value_el.get_text(strip=True)
                        # Парсим цену: "1 234 567,89 ₽" -> 1234567.89
                        # Убираем пробелы, '₽', 'р', 'руб'
                        price_clean = (
                            price_text.replace(" ", "")
                            .replace("\xa0", "")
                            .replace("₽", "")
                            .replace("руб", "")
                            .replace("р", "")
                            .replace(",", ".")
                            .strip()
                        )
                        try:
                            initial_price = float(price_clean)
                        except ValueError:
                            self.logger.warning(f"Ошибка парсинга цены '{price_clean}' (исходная: '{price_text}') для {reg_number}")
                            initial_price = None

                
                results.append({
                    "reg_number": reg_number,
                    "description": description,
                    "update_date": update_date,
                    "bid_end_date": bid_end_date,
                    "initial_price": initial_price,
                    "link": purchase_link,
                })
            except Exception as e:
                self.logger.debug(f"Ошибка парсинга блока: {e}")
                continue
        
        return results
    
    def _parse_date(self, date_str: str) -> datetime:
        """Парсит дату из строки."""
        if not date_str:
            return datetime.min
        date_str = date_str.strip()
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return datetime.min
    
    def _get_documents_list(self, reg_number: str) -> List[Dict]:
        """Получает список документов закупки."""
        url = f"https://zakupki.gov.ru/epz/order/notice/zk20/view/documents.html?regNumber={reg_number}"
        
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=30)
                resp.raise_for_status()
                break
            except Exception as e:
                self.logger.warning(f"Попытка {attempt+1}/3 загрузки документов: {e}")
                time.sleep(5)
        else:
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []
        
        for block in soup.find_all("div", class_="attachment"):
            try:
                name_el = block.find("span", class_="section__value")
                if not name_el:
                    continue
                
                link_el = block.find("a", href=lambda href: href and "uid=" in href)
                if not link_el:
                    continue
                
                href = link_el["href"]
                uid = href.split("uid=")[1].split("&")[0]
                download_url = f"https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid={uid}"
                
                docs.append({
                    "name": name_el.get_text(strip=True),
                    "url": download_url
                })
            except Exception:
                continue
        
        return docs
    
    def _download_document(self, doc_info: Dict, target_dir: Path) -> Optional[str]:
        """Скачивает документ."""
        name = doc_info.get("name", "document")
        url = doc_info.get("url")
        if not url:
            return None
        
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=60)
                resp.raise_for_status()
                break
            except Exception as e:
                self.logger.warning(f"Попытка {attempt+1}/3 скачивания: {e}")
                time.sleep(5)
        else:
            return None
        
        # Определяем расширение
        ext = self._detect_extension(resp.content, resp.headers)
        safe_name = re.sub(r'[^\w\s-]', '', name)[:50]
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
        filename = f"{safe_name}_{hash_suffix}{ext}"
        filepath = target_dir / filename
        
        with open(filepath, "wb") as f:
            f.write(resp.content)
        
        return str(filepath)
    
    def _detect_extension(self, content: bytes, headers: dict) -> str:
        """Определяет расширение файла по содержимому."""
        header = content[:20]
        
        if header.startswith(b"%PDF"):
            return ".pdf"
        if header.startswith(b"PK\x03\x04"):
            snippet = str(content[:200])
            if "word/" in snippet:
                return ".docx"
            if "xl/" in snippet:
                return ".xlsx"
            return ".zip"
        if header.startswith(b"\xd0\xcf\x11\xe0"):
            return ".doc"
        
        return ".bin"
    
    def _extract_text(self, file_path: str) -> Optional[str]:
        """Извлекает текст из документа."""
        try:
            # Импортируем из корня src/
            import sys
            from pathlib import Path
            src_dir = Path(__file__).parent.parent
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            
            from text_extraction import extract_text_from_any_file
            text = extract_text_from_any_file(file_path)
            if text and not text.startswith("Ошибка") and not text.startswith("Неизвестный"):
                return text
        except ImportError as e:
            self.logger.warning(f"text_extraction не найден: {e}")
        except Exception as e:
            self.logger.warning(f"Ошибка извлечения текста: {e}")
        
        return None
