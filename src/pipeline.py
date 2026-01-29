"""
Pipeline — оркестратор для объединения всех стадий обработки.
"""
from typing import Optional, List
from config.settings import settings
from services.database_service import DatabaseService
from services.eis_service import EISService
from services.ai_service import AIService
from services.gis_service import GISService
from services.scraper_service import ScraperService
from services.eis_downloader_service import EISDownloaderService
from services.ai_processor_service import AIProcessorService
from models.zakupka import Zakupka
from models.ai_result import AIResult
from models.listing import ListingResult
from models.stage_result import StageResult
from utils.logger import get_logger


class Pipeline:
    """
    Оркестратор для выполнения полного пайплайна обработки закупок.
    
    Стадии:
    1. Загрузка закупок с ЕИС
    2. ИИ-анализ текстов
    3. Генерация ссылок 2ГИС
    4. Сбор объявлений
    """
    
    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: Путь к БД. Если не указан, берётся из settings.
        """
        self.logger = get_logger("Pipeline")
        
        # Инициализируем DatabaseService
        self.db = DatabaseService(db_path)
        
        # Инициализируем сервисы с репозиториями из DatabaseService
        self.eis = EISService(self.db.zakupki)
        self.ai = AIService(self.db.ai_results)
        self.gis = GISService()
        self.scraper = ScraperService(self.db.listings)
        
        # Новые ООП-сервисы для Stage 1 и 2
        self.eis_downloader = EISDownloaderService(self.db.zakupki)
        self.ai_processor = AIProcessorService(self.db.ai_results)
        
        self.logger.info("Pipeline инициализирован")
    
    def init_database(self) -> bool:
        """Инициализирует базу данных."""
        return self.db.init_database()
    
    def run_stage3_for_zakupka(
        self,
        reg_number: str,
        ai_result: AIResult,
        user_id: int = 1
    ) -> Optional[str]:
        """
        Стадия 3: Генерация ссылки 2ГИС для одной закупки.
        Uses effective_value = user_override ?? ai_value.
        
        Args:
            reg_number: Номер закупки
            ai_result: Результат ИИ-анализа
            user_id: ID пользователя для overrides
        
        Returns:
            Сгенерированный URL или None
        """
        # Получаем user overrides
        overrides = self.db.user_overrides.get_for_zakupka(reg_number, user_id)
        
        # Вычисляем effective values
        city = overrides.get('city') or ai_result.city
        price_rub = float(overrides.get('price_rub')) if overrides.get('price_rub') else ai_result.price_rub
        area_min = float(overrides.get('area_min_m2')) if overrides.get('area_min_m2') else ai_result.area_min_m2
        rooms_str = overrides.get('rooms') or ai_result.rooms
        floor_str = overrides.get('floor') or ai_result.floor
        
        if not city:
            self.logger.warning(f"Нет города для {reg_number}")
            return None
        
        # Парсим комнаты
        rooms_list = []
        if rooms_str:
            try:
                # Простой парсинг: "1,2,3" или "1-3"
                import re
                if ',' in str(rooms_str):
                    rooms_list = [int(x.strip()) for x in str(rooms_str).split(',') if x.strip().isdigit()]
                elif '-' in str(rooms_str):
                    match = re.match(r'(\d+)\s*[-–]\s*(\d+)', str(rooms_str))
                    if match:
                        rooms_list = list(range(int(match.group(1)), int(match.group(2)) + 1))
                elif str(rooms_str).strip().isdigit():
                    rooms_list = [int(rooms_str)]
            except:
                rooms_list = ai_result.get_rooms_list()
        else:
            rooms_list = ai_result.get_rooms_list()
        
        # Парсим этаж
        floor_min = None
        if floor_str:
            try:
                import re
                match = re.search(r'\d+', str(floor_str))
                if match:
                    floor_min = int(match.group())
            except:
                pass
        
        url = self.gis.build_url_for_city(
            city=city,
            area_min=area_min,
            rooms_counts=rooms_list if rooms_list else None,
            floor_min=floor_min,
            price_max=price_rub
        )
        
        if url:
            self.eis.update_two_gis_url(reg_number, url)
            
            # Обновляем статус на 'url_ready' (Этап 2)
            self.db_service.zakupki.update_status(reg_number, 'url_ready', prepared_by_user_id=user_id)
            
            self.logger.info(f"Ссылка сгенерирована для {reg_number} (city={city})")
        
        return url
    
    def run_stage4_for_zakupka(
        self,
        reg_number: str,
        url: str,
        top_n: int = 20,
        get_details: bool = False
    ) -> ListingResult:
        """
        Стадия 4: Сбор объявлений для одной закупки.
        
        Args:
            reg_number: Номер закупки
            url: URL поиска 2ГИС
            top_n: Количество объявлений
            get_details: Получать детали (год постройки)
        
        Returns:
            ListingResult
        """
        result = self.scraper.collect_listings(
            url=url,
            top_n=top_n,
            get_details=get_details
        )
        
        if result.items:
            self.scraper.save_listings(reg_number, result.items, url)
            
            # Обновляем статус на 'listings_fresh' (Этап 2)
            self.db_service.zakupki.update_status(reg_number, 'listings_fresh')
        
        return result
    
    def get_statistics(self) -> dict:
        """Возвращает статистику по всему пайплайну."""
        return {
            "zakupki": self.eis.count(),
            "ai_results": self.ai.count(),
            "listings": self.scraper.count()
        }
    
    def process_zakupka(
        self,
        reg_number: str,
        run_stage3: bool = True,
        run_stage4: bool = True,
        top_n: int = 20,
        get_details: bool = False
    ) -> dict:
        """
        Обрабатывает одну закупку через весь пайплайн.
        
        Args:
            reg_number: Номер закупки
            run_stage3: Выполнить генерацию ссылок
            run_stage4: Выполнить сбор объявлений
            top_n: Количество объявлений
            get_details: Получать детали
        
        Returns:
            Результаты обработки
        """
        result = {
            "reg_number": reg_number,
            "stage3_url": None,
            "stage4_listings": 0,
            "errors": []
        }
        
        # Получаем ai_result
        ai_result = self.ai.get_result(reg_number)
        if not ai_result:
            result["errors"].append("Нет результата ИИ-анализа")
            return result
        
        # Stage 3
        if run_stage3:
            try:
                url = self.run_stage3_for_zakupka(reg_number, ai_result)
                result["stage3_url"] = url
            except Exception as e:
                result["errors"].append(f"Stage 3: {e}")
        
        # Stage 4
        if run_stage4:
            zakupka = self.eis.get_zakupka(reg_number)
            url = result["stage3_url"] or (zakupka.two_gis_url if zakupka else None)
            
            if url:
                try:
                    listing_result = self.run_stage4_for_zakupka(
                        reg_number, url, top_n, get_details
                    )
                    result["stage4_listings"] = listing_result.actual_n
                    if listing_result.error:
                        result["errors"].append(f"Stage 4: {listing_result.error}")
                except Exception as e:
                    result["errors"].append(f"Stage 4: {e}")
            else:
                result["errors"].append("Нет URL для Stage 4")
        
        return result
    
    # ================================================================
    # Методы для запуска каждого этапа отдельно (для CLI и дашборда)
    # ================================================================
    
    def run_stage1(self, limit: int = 10) -> StageResult:
        """
        Stage 1: Загрузка закупок с ЕИС через EISDownloaderService (ОКПД2 68.10.11).
        
        Логика:
        1. Ищем закупки на ЕИС
        2. Пропускаем те, что уже есть в БД
        3. Загружаем документы и создаём combined_text
        4. Сохраняем в БД
        5. Удаляем папку с документами (текст уже в БД)
        
        Args:
            limit: Количество НОВЫХ закупок для загрузки
        
        Returns:
            StageResult с данными о загрузке
        """
        import os
        import shutil
        
        self.logger.info(f"Stage 1: Загрузка закупок ОКПД2 68.10.11 (limit={limit})")
        
        errors = []
        saved = 0
        skipped = 0
        found = 0  # Все найденные подходящие закупки (для остановки)
        processed_reg_numbers = set()  # Для дедупликации
        
        try:
            page = 1
            max_pages = 50
            
            while found < limit and page <= max_pages:
                self.logger.info(f"Страница {page}...")
                
                # Используем ООП-сервис EISDownloaderService
                html = self.eis_downloader._fetch_search_page(page)
                if not html:
                    page += 1
                    continue
                
                page_purchases = self.eis_downloader._parse_purchases_from_html(html)
                if not page_purchases:
                    page += 1
                    continue
                
                for p in page_purchases:
                    if found >= limit:
                        break
                    
                    reg_number = p.get('reg_number', '')
                    
                    # Пропускаем дубликаты на текущей странице
                    if reg_number in processed_reg_numbers:
                        continue
                    processed_reg_numbers.add(reg_number)
                    
                    # Проверяем есть ли в БД
                    existing = self.eis.get_zakupka(reg_number)
                    if existing and existing.combined_text:
                        self.logger.info(f"  ⏭️ {reg_number} — уже в БД")
                        skipped += 1
                        found += 1
                        continue
                    
                    # Загружаем документы через ООП-сервис
                    try:
                        self.logger.info(f"📥 Обработка {reg_number}...")
                        
                        # EISDownloaderService.download_documents уже загружает 
                        # печатную форму и документы, создаёт combined_text.txt
                        combined_path = self.eis_downloader.download_documents(reg_number)
                        
                        # Читаем текст
                        combined_text = ""
                        if combined_path and os.path.exists(combined_path):
                            with open(combined_path, 'r', encoding='utf-8') as f:
                                combined_text = f.read()
                        
                        if not combined_text.strip():
                            self.logger.warning(f"Нет текста для {reg_number}")
                            continue
                        
                        # Сохраняем в БД
                        zakupka = Zakupka(
                            reg_number=reg_number,
                            description=p.get('description', ''),
                            update_date=str(p.get('update_date', '')),
                            link=p.get('link', ''),
                            combined_text=combined_text
                        )
                        if self.eis.save_zakupka(zakupka):
                            saved += 1
                            found += 1
                            
                            # Обновляем статус на 'raw' (Этап 2)
                            self.db_service.zakupki.update_status(reg_number, 'raw')
                            
                            self.logger.info(f"✅ Сохранена закупка {reg_number} ({found}/{limit})")
                            
                            # Удаляем папку — текст уже в БД
                            zakupka_dir = self.eis_downloader.zakupki_dir / reg_number
                            if zakupka_dir.exists():
                                shutil.rmtree(zakupka_dir, ignore_errors=True)
                                self.logger.debug(f"Удалена папка {reg_number}")
                        
                    except Exception as e:
                        errors.append(f"{reg_number}: {e}")
                        self.logger.error(f"Ошибка обработки {reg_number}: {e}")
                
                page += 1
            
            if found >= limit:
                self.logger.info(f"Достигнут лимит {limit} закупок")
            
            success = saved > 0 or len(errors) == 0
            message = f"Загружено {saved} новых закупок (пропущено {skipped} существующих)"
            
        except Exception as e:
            success = False
            message = f"Ошибка загрузки: {e}"
            errors.append(str(e))
        
        self.logger.info(message)
        
        return StageResult(
            stage=1,
            success=success,
            message=message,
            data={"limit": limit, "downloaded": saved, "skipped": skipped},
            errors=errors
        )
    
    def _get_print_form(self, reg_number: str) -> str:
        """
        Получает текст печатной формы закупки с ЕИС.
        
        Args:
            reg_number: Регистрационный номер закупки
        
        Returns:
            Текст печатной формы или пустая строка
        """
        import requests
        from bs4 import BeautifulSoup
        from config import DEFAULT_HEADERS
        
        url = f"https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber={reg_number}"
        
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Удаляем скрипты и стили
            for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            
            # Ищем основной контент
            main_content = soup.find('div', class_='wrapper')
            if not main_content:
                main_content = soup.find('main')
            if not main_content:
                main_content = soup
            
            # Извлекаем текст
            text = main_content.get_text(separator='\n', strip=True)
            
            # Очищаем от лишних пустых строк
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            result = '\n'.join(lines[:200])  # Первые 200 строк
            
            if result:
                self.logger.info(f"Печатная форма загружена для {reg_number} ({len(result)} символов)")
                return result
                
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить печатную форму для {reg_number}: {e}")
        
        return ""
    
    def run_stage2(self, limit: int = None, reg_numbers: List[str] = None) -> StageResult:
        """
        Stage 2: ИИ-обработка закупок через AIProcessorService (OpenRouter).
        
        Args:
            limit: Количество закупок для обработки (None = все)
            reg_numbers: Список ID для обработки (если задан, limit игнорируется или применяется к фильтрованному списку)
        
        Returns:
            StageResult с данными об обработке
        """
        self.logger.info(f"Stage 2: ИИ-обработка (limit={limit}, reg_numbers={len(reg_numbers) if reg_numbers else 'All'})")
        
        errors = []
        processed = 0
        cities = []
        skipped_no_text = 0
        skipped_already_processed = 0
        
        try:
            # Получаем закупки для обработки (ПОСЛЕДНИЕ)
            # Если заданы reg_numbers, используем их
            if reg_numbers:
                zakupki = self.eis.get_by_reg_numbers(reg_numbers)
                if not zakupki:
                     self.logger.warning(f"Не найдены закупки для переданных reg_numbers: {reg_numbers}")
            else:
                zakupki = self.eis.get_all_zakupki()
                if limit:
                    zakupki = zakupki[-limit:]
            
            self.logger.info(f"Найдено {len(zakupki)} закупок для ИИ-обработки")
            
            for i, zakupka in enumerate(zakupki, 1):
                reg_number = zakupka.reg_number
                
                if not zakupka.combined_text:
                    self.logger.info(f"  ⏭️ {reg_number} — нет combined_text")
                    skipped_no_text += 1
                    continue
                
                # Проверяем существующий результат
                existing = self.ai.get_result(reg_number)
                if existing:
                    self.logger.info(f"  ⏭️ {reg_number} — уже обработан ИИ")
                    skipped_already_processed += 1
                    continue
                
                try:
                    self.logger.info(f"[{i}/{len(zakupki)}] Обработка ИИ: {reg_number}...")
                    
                    # Используем ООП-сервис AIProcessorService
                    ai_result = self.ai_processor.process_zakupka(zakupka)
                    
                    if ai_result and self.ai.save_result(ai_result):
                        processed += 1
                        if ai_result.city and ai_result.city not in cities:
                            cities.append(ai_result.city)
                        
                        # Обновляем статус на 'ai_ready' (Этап 2)
                        self.db_service.zakupki.update_status(reg_number, 'ai_ready')
                        
                        self.logger.info(f"✅ Сохранён результат для {reg_number}")
                    
                except Exception as e:
                    errors.append(f"{reg_number}: {e}")
                    self.logger.error(f"Ошибка ИИ для {reg_number}: {e}")
            
            # Итоговая статистика
            self.logger.info(f"📊 Статистика:")
            self.logger.info(f"   Пропущено (нет текста): {skipped_no_text}")
            self.logger.info(f"   Пропущено (уже обработаны): {skipped_already_processed}")
            self.logger.info(f"   Обработано успешно: {processed}")
            self.logger.info(f"   Ошибок: {len(errors)}")
            
            success = processed > 0 or len(errors) == 0
            
            msg_parts = []
            if processed > 0:
                msg_parts.append(f"Обработано {processed} закупок")
            if skipped_already_processed > 0:
                msg_parts.append(f"Уже готово {skipped_already_processed}")
            if skipped_no_text > 0:
                msg_parts.append(f"Пропущено (нет текста) {skipped_no_text}")
            
            message = ", ".join(msg_parts) if msg_parts else "Ничего не обработано"
            if errors:
                message += f". Ошибок: {len(errors)}"
            
        except Exception as e:
            success = False
            message = f"Ошибка обработки: {e}"
            errors.append(str(e))
        
        self.logger.info(message)
        
        return StageResult(
            stage=2,
            success=success,
            message=message,
            data={"limit": limit, "processed": processed},
            errors=errors
        )
    
    def run_stage3(self, limit: int = None, reg_numbers: List[str] = None) -> StageResult:
        """
        Stage 3: Генерация ссылок 2ГИС.
        
        Args:
            limit: Количество закупок для обработки (None = все)
            reg_numbers: Список ID для обработки
        
        Returns:
            StageResult с данными о генерации
        """
        self.logger.info(f"Stage 3: Генерация ссылок (limit={limit}, reg_numbers={len(reg_numbers) if reg_numbers else 'All'})")
        
        errors = []
        generated = 0
        urls = []
        
        # Получаем ai_results
        if reg_numbers:
            # Если переданы конкретные ID, берем их
            # Примечание: лучше бы иметь метод get_many в репозитории, но пока так
            ai_results = []
            for reg in reg_numbers:
                res = self.ai.get_result(reg)
                if res:
                    ai_results.append(res)
                else:
                    self.logger.warning(f"Нет AI результат для {reg}")
        else:
            ai_results = self.ai.get_all_results()
            if limit:
                ai_results = ai_results[:limit]
        
        for ai_result in ai_results:
            try:
                url = self.run_stage3_for_zakupka(ai_result.reg_number, ai_result)
                if url:
                    generated += 1
                    urls.append({"reg_number": ai_result.reg_number, "url": url[:80]})
            except Exception as e:
                errors.append(f"{ai_result.reg_number}: {e}")
        
        success = generated > 0
        message = f"Сгенерировано {generated} ссылок из {len(ai_results)}"
        
        self.logger.info(message)
        
        return StageResult(
            stage=3,
            success=success,
            message=message,
            data={
                "total": len(ai_results),
                "generated": generated,
                "urls": urls[:10]  # Первые 10 для отображения
            },
            errors=errors
        )
    
    def run_stage4(
        self,
        top_n: int = 20,
        limit: int = None,
        get_details: bool = False
    ) -> StageResult:
        """
        Stage 4: Сбор объявлений с 2ГИС.
        
        Args:
            top_n: Количество объявлений на закупку
            limit: Количество закупок для обработки (None = все)
            get_details: Получать детали (год постройки)
        
        Returns:
            StageResult с данными о сборе
        """
        self.logger.info(f"Stage 4: Сбор объявлений (top_n={top_n}, limit={limit}, details={get_details})")
        
        errors = []
        total_listings = 0
        processed = 0
        
        # Получаем закупки с URL
        zakupki = self.eis.get_zakupki_with_links()
        if limit:
            zakupki = zakupki[:limit]
        
        for zakupka in zakupki:
            if not zakupka.two_gis_url:
                continue
            
            try:
                result = self.run_stage4_for_zakupka(
                    zakupka.reg_number,
                    zakupka.two_gis_url,
                    top_n,
                    get_details
                )
                total_listings += result.actual_n
                processed += 1
                
                if result.error:
                    errors.append(f"{zakupka.reg_number}: {result.error}")
                    
            except Exception as e:
                errors.append(f"{zakupka.reg_number}: {e}")
        
        success = total_listings > 0
        message = f"Собрано {total_listings} объявлений из {processed} закупок"
        
        self.logger.info(message)
        
        return StageResult(
            stage=4,
            success=success,
            message=message,
            data={
                "processed": processed,
                "total_zakupki": len(zakupki),
                "total_listings": total_listings,
                "top_n": top_n,
                "details": get_details
            },
            errors=errors
        )
