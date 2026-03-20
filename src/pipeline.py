"""
Pipeline вЂ” РѕСЂРєРµСЃС‚СЂР°С‚РѕСЂ РґР»СЏ РѕР±СЉРµРґРёРЅРµРЅРёСЏ РІСЃРµС… СЃС‚Р°РґРёР№ РѕР±СЂР°Р±РѕС‚РєРё.
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
from models.statuses import STAGE2_PENDING_STATUSES, ZakupkaStatus
from models.stage_result import StageResult
from utils.logger import get_logger


class Pipeline:
    """
    РћСЂРєРµСЃС‚СЂР°С‚РѕСЂ РґР»СЏ РІС‹РїРѕР»РЅРµРЅРёСЏ РїРѕР»РЅРѕРіРѕ РїР°Р№РїР»Р°Р№РЅР° РѕР±СЂР°Р±РѕС‚РєРё Р·Р°РєСѓРїРѕРє.
    
    РЎС‚Р°РґРёРё:
    1. Р—Р°РіСЂСѓР·РєР° Р·Р°РєСѓРїРѕРє СЃ Р•РРЎ
    2. РР-Р°РЅР°Р»РёР· С‚РµРєСЃС‚РѕРІ
    3. Р“РµРЅРµСЂР°С†РёСЏ СЃСЃС‹Р»РѕРє 2Р“РРЎ
    4. РЎР±РѕСЂ РѕР±СЉСЏРІР»РµРЅРёР№
    """
    
    def __init__(self, db_path: str = None):
        """
        Args:
            db_path: РџСѓС‚СЊ Рє Р‘Р”. Р•СЃР»Рё РЅРµ СѓРєР°Р·Р°РЅ, Р±РµСЂС‘С‚СЃСЏ РёР· settings.
        """
        self.logger = get_logger("Pipeline")
        
        # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј DatabaseService
        self.db = DatabaseService(db_path)
        
        # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј СЃРµСЂРІРёСЃС‹ СЃ СЂРµРїРѕР·РёС‚РѕСЂРёСЏРјРё РёР· DatabaseService
        self.eis = EISService(self.db.zakupki)
        self.ai = AIService(self.db.ai_results)
        self.gis = GISService()
        self.scraper = ScraperService(self.db.listings)
        
        # РќРѕРІС‹Рµ РћРћРџ-СЃРµСЂРІРёСЃС‹ РґР»СЏ Stage 1 Рё 2
        self.eis_downloader = EISDownloaderService(self.db.zakupki)
        self.ai_processor = AIProcessorService(self.db.ai_results)
        
        self.logger.info("Pipeline инициализирован")
    
    def init_database(self) -> bool:
        """РРЅРёС†РёР°Р»РёР·РёСЂСѓРµС‚ Р±Р°Р·Сѓ РґР°РЅРЅС‹С…."""
        return self.db.init_database()

    def _log_stage_progress(self, stage: int, reg_number: str, result: str, reason: str = ""):
        """Unified progress log format for per-item diagnostics."""
        self.logger.info(
            "stage_progress reg_number=%s stage=%s result=%s reason=%s",
            reg_number,
            stage,
            result,
            reason or "-",
        )

    def _stage2_eligibility_reason(
        self,
        zakupka: Zakupka,
        ai_result: Optional[AIResult],
        overwrite: bool = False,
    ) -> tuple[bool, Optional[str]]:
        """Checks whether purchase is eligible for Stage 2."""
        if overwrite:
            if not (zakupka.combined_text or "").strip():
                return False, "no_combined_text"
            return True, None

        status = (zakupka.status or "").strip()

        if status not in STAGE2_PENDING_STATUSES:
            return False, "status_not_pending"

        if not (zakupka.combined_text or "").strip():
            return False, "no_combined_text"

        # If we already have a usable AI result in DB, avoid repeated AI calls.
        if ai_result is not None and not overwrite:
            if self._is_ai_result_usable(ai_result):
                return False, "already_has_ai_result"
            # Retry is allowed only for ai_error when stored AI row is incomplete.
            if status != ZakupkaStatus.AI_ERROR:
                return False, "already_has_ai_result"

        return True, None

    @staticmethod
    def _is_ai_result_usable(ai_result: Optional[AIResult]) -> bool:
        """Returns True when AI result contains minimum data for Stage 3 usage."""
        if ai_result is None:
            return False
        city = (ai_result.city or "").strip()
        address = (ai_result.address or "").strip()
        has_area = ai_result.area_min_m2 is not None or ai_result.area_max_m2 is not None
        return bool(city) and (bool(address) or has_area)

    def get_stage2_pending_items(self, limit: Optional[int] = None, offset: int = 0) -> List[Zakupka]:
        """Returns Stage 2 pending items (full queue by default)."""
        items = self.db.get_stage2_pending_items(overwrite=False, limit=limit, offset=offset)
        if limit is None:
            self.logger.info(
                "Stage2 pending full selection: returned=%s offset=%s",
                len(items),
                offset,
            )
        else:
            self.logger.info(
                "Stage2 pending page selection: returned=%s offset=%s limit=%s",
                len(items),
                offset,
                limit,
            )
        return items

    def get_stage2_pending_page(self, offset: int = 0, limit: int = 20) -> tuple[List[Zakupka], int]:
        """Returns paginated Stage 2 pending list."""
        return self.db.get_stage2_pending_page(offset=offset, limit=limit)
    
    def run_stage3_for_zakupka(
        self,
        reg_number: str,
        ai_result: AIResult,
        user_id: int = 1
    ) -> Optional[str]:
        """
        РЎС‚Р°РґРёСЏ 3: Р“РµРЅРµСЂР°С†РёСЏ СЃСЃС‹Р»РєРё 2Р“РРЎ РґР»СЏ РѕРґРЅРѕР№ Р·Р°РєСѓРїРєРё.
        Uses effective_value = user_override ?? ai_value.
        
        Args:
            reg_number: РќРѕРјРµСЂ Р·Р°РєСѓРїРєРё
            ai_result: Р РµР·СѓР»СЊС‚Р°С‚ РР-Р°РЅР°Р»РёР·Р°
            user_id: ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РґР»СЏ overrides
        
        Returns:
            РЎРіРµРЅРµСЂРёСЂРѕРІР°РЅРЅС‹Р№ URL РёР»Рё None
        """
        # РџРѕР»СѓС‡Р°РµРј user overrides
        overrides = self.db.user_overrides.get_for_zakupka(reg_number, user_id)
        
        # Р’С‹С‡РёСЃР»СЏРµРј effective values
        city = overrides.get('city') or ai_result.city
        # price_rub РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РІ AIResult; РёСЃРїРѕР»СЊР·СѓРµРј override -> Р·Р°РєСѓРїРєР°.initial_price
        if overrides.get('price_rub'):
            price_rub = float(overrides.get('price_rub'))
        else:
            zakupka = self.eis.get_zakupka(reg_number)
            price_rub = zakupka.initial_price if zakupka else None
        area_min = float(overrides.get('area_min_m2')) if overrides.get('area_min_m2') else ai_result.area_min_m2
        rooms_str = overrides.get('rooms') or ai_result.rooms
        floor_str = overrides.get('floor') or ai_result.floor

        if not city:
            city = self._derive_city_from_address(ai_result.address)
        
        self.logger.info(
            f"Stage3 source values {reg_number}: city={city!r}, ai_city={ai_result.city!r}, "
            f"override_city={overrides.get('city')!r}, address={ai_result.address!r}, "
            f"price_rub={price_rub!r}"
        )
        
        if not city:
            self.logger.warning(f"[SKIP] Нет города для {reg_number}")
            return None
        
        # РџР°СЂСЃРёРј РєРѕРјРЅР°С‚С‹
        rooms_list = []
        if rooms_str:
            try:
                # РџСЂРѕСЃС‚РѕР№ РїР°СЂСЃРёРЅРі: "1,2,3" РёР»Рё "1-3"
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
        
        # РџР°СЂСЃРёРј СЌС‚Р°Р¶
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
            
            # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ РЅР° URL_READY (Р­С‚Р°Рї 3)
            self.db.zakupki.update_status(reg_number, ZakupkaStatus.URL_READY, prepared_by_user_id=user_id)
            
            self.logger.info(f"[OK] Ссылка сгенерирована для {reg_number} (city={city})")
        
        return url

    def _derive_city_from_address(self, address: Optional[str]) -> Optional[str]:
        """Пытается извлечь город из адресной строки."""
        if not address:
            return None
        import re
        text = str(address)
        patterns = [
            r"г\.?\s*([А-ЯЁ][А-ЯЁа-яё\-\s]+)",
            r"город\s+([А-ЯЁ][А-ЯЁа-яё\-\s]+)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                city = m.group(1).strip()
                city = city.split(",")[0].strip()
                return city
        return None
    
    def run_stage4_for_zakupka(
        self,
        reg_number: str,
        url: str,
        top_n: int = 20,
        get_details: bool = False
    ) -> ListingResult:
        """
        РЎС‚Р°РґРёСЏ 4: РЎР±РѕСЂ РѕР±СЉСЏРІР»РµРЅРёР№ РґР»СЏ РѕРґРЅРѕР№ Р·Р°РєСѓРїРєРё.
        
        Args:
            reg_number: РќРѕРјРµСЂ Р·Р°РєСѓРїРєРё
            url: URL РїРѕРёСЃРєР° 2Р“РРЎ
            top_n: РљРѕР»РёС‡РµСЃС‚РІРѕ РѕР±СЉСЏРІР»РµРЅРёР№
            get_details: РџРѕР»СѓС‡Р°С‚СЊ РґРµС‚Р°Р»Рё (РіРѕРґ РїРѕСЃС‚СЂРѕР№РєРё)
        
        Returns:
            ListingResult
        """
        result = self.scraper.collect_listings(
            url=url,
            top_n=top_n,
            get_details=get_details
        )

        if result.error:
            self.db.zakupki.update_status(reg_number, ZakupkaStatus.STAGE4_ERROR)
            self._log_stage_progress(4, reg_number, "error", result.error)
            return result

        if result.items:
            self.scraper.save_listings(reg_number, result.items, url)

        self.db.zakupki.update_status(reg_number, ZakupkaStatus.STAGE4_DONE)
        self._log_stage_progress(4, reg_number, "ok", f"listings={result.actual_n}")
        return result
    
    def get_statistics(self) -> dict:
        """Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃС‚Р°С‚РёСЃС‚РёРєСѓ РїРѕ РІСЃРµРјСѓ РїР°Р№РїР»Р°Р№РЅСѓ."""
        return {
            "zakupki": self.eis.count(),
            "ai_results": self.ai.count(),
            "listings": self.scraper.count()
        }
    
    def process_zakupka(
        self,
        reg_number: str,
        run_stage3: bool = True,
        run_stage4: bool = False,
        top_n: int = 20,
        get_details: bool = False
    ) -> dict:
        """
        РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚ РѕРґРЅСѓ Р·Р°РєСѓРїРєСѓ С‡РµСЂРµР· РІРµСЃСЊ РїР°Р№РїР»Р°Р№РЅ.
        
        Args:
            reg_number: РќРѕРјРµСЂ Р·Р°РєСѓРїРєРё
            run_stage3: Р’С‹РїРѕР»РЅРёС‚СЊ РіРµРЅРµСЂР°С†РёСЋ СЃСЃС‹Р»РѕРє
            run_stage4: Р’С‹РїРѕР»РЅРёС‚СЊ СЃР±РѕСЂ РѕР±СЉСЏРІР»РµРЅРёР№
            top_n: РљРѕР»РёС‡РµСЃС‚РІРѕ РѕР±СЉСЏРІР»РµРЅРёР№
            get_details: РџРѕР»СѓС‡Р°С‚СЊ РґРµС‚Р°Р»Рё
        
        Returns:
            Р РµР·СѓР»СЊС‚Р°С‚С‹ РѕР±СЂР°Р±РѕС‚РєРё
        """
        result = {
            "reg_number": reg_number,
            "stage3_url": None,
            "stage4_listings": 0,
            "errors": []
        }
        
        # РџРѕР»СѓС‡Р°РµРј ai_result
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
    # РњРµС‚РѕРґС‹ РґР»СЏ Р·Р°РїСѓСЃРєР° РєР°Р¶РґРѕРіРѕ СЌС‚Р°РїР° РѕС‚РґРµР»СЊРЅРѕ (РґР»СЏ CLI Рё РґР°С€Р±РѕСЂРґР°)
    # ================================================================
    
    def run_stage1(self, limit: int = 10) -> StageResult:
        """
        Stage 1: Р—Р°РіСЂСѓР·РєР° Р·Р°РєСѓРїРѕРє СЃ Р•РРЎ С‡РµСЂРµР· EISDownloaderService (РћРљРџР”2 68.10.11).
        
        Р›РѕРіРёРєР°:
        1. РС‰РµРј Р·Р°РєСѓРїРєРё РЅР° Р•РРЎ
        2. РџСЂРѕРїСѓСЃРєР°РµРј С‚Рµ, С‡С‚Рѕ СѓР¶Рµ РµСЃС‚СЊ РІ Р‘Р”
        3. Р—Р°РіСЂСѓР¶Р°РµРј РґРѕРєСѓРјРµРЅС‚С‹ Рё СЃРѕР·РґР°С‘Рј combined_text
        4. РЎРѕС…СЂР°РЅСЏРµРј РІ Р‘Р”
        5. РЈРґР°Р»СЏРµРј РїР°РїРєСѓ СЃ РґРѕРєСѓРјРµРЅС‚Р°РјРё (С‚РµРєСЃС‚ СѓР¶Рµ РІ Р‘Р”)
        
        Args:
            limit: РљРѕР»РёС‡РµСЃС‚РІРѕ РќРћР’Р«РҐ Р·Р°РєСѓРїРѕРє РґР»СЏ Р·Р°РіСЂСѓР·РєРё
        
        Returns:
            StageResult СЃ РґР°РЅРЅС‹РјРё Рѕ Р·Р°РіСЂСѓР·РєРµ
        """
        import os
        import shutil
        
        self.logger.info(f"Stage 1: Загрузка закупок ОКПД2 68.10.11 (limit={limit})")
        
        errors = []
        saved_new = 0
        skipped_existing = 0
        processed_reg_numbers = set()  # Р”Р»СЏ РґРµРґСѓРїР»РёРєР°С†РёРё
        
        try:
            page = 1
            try:
                max_pages = max(1, int(os.getenv("STAGE1_MAX_PAGES", "10")))
            except Exception:
                max_pages = 10
            self.logger.info("Stage 1 max_pages=%s", max_pages)
            
            while saved_new < limit and page <= max_pages:
                self.logger.info(f"Страница {page}...")
                
                # РСЃРїРѕР»СЊР·СѓРµРј РћРћРџ-СЃРµСЂРІРёСЃ EISDownloaderService
                html = self.eis_downloader._fetch_search_page(page)
                if not html:
                    if page == 1:
                        fail_msg = "Stage 1 aborted: EIS page 1 is unavailable after retries"
                        self.logger.error(fail_msg)
                        errors.append(fail_msg)
                        break
                    page += 1
                    continue
                
                page_purchases = self.eis_downloader._parse_purchases_from_html(html)
                if not page_purchases:
                    page += 1
                    continue
                
                for p in page_purchases:
                    if saved_new >= limit:
                        break
                    
                    reg_number = p.get('reg_number', '')
                    
                    # РџСЂРѕРїСѓСЃРєР°РµРј РґСѓР±Р»РёРєР°С‚С‹ РЅР° С‚РµРєСѓС‰РµР№ СЃС‚СЂР°РЅРёС†Рµ
                    if reg_number in processed_reg_numbers:
                        continue
                    processed_reg_numbers.add(reg_number)
                    
                    # РџСЂРѕРІРµСЂСЏРµРј РµСЃС‚СЊ Р»Рё РІ Р‘Р”
                    existing = self.eis.get_zakupka(reg_number)
                    if existing and existing.combined_text:
                        self.logger.info(f"  [SKIP] {reg_number} — уже в БД")
                        skipped_existing += 1
                        continue
                    
                    # Р—Р°РіСЂСѓР¶Р°РµРј РґРѕРєСѓРјРµРЅС‚С‹ С‡РµСЂРµР· РћРћРџ-СЃРµСЂРІРёСЃ
                    try:
                        self.logger.info(f"[INFO] Обработка {reg_number}...")
                        
                        # EISDownloaderService.download_documents СѓР¶Рµ Р·Р°РіСЂСѓР¶Р°РµС‚ 
                        # РїРµС‡Р°С‚РЅСѓСЋ С„РѕСЂРјСѓ Рё РґРѕРєСѓРјРµРЅС‚С‹, СЃРѕР·РґР°С‘С‚ combined_text.txt
                        combined_path = self.eis_downloader.download_documents(reg_number)
                        
                        # Р§РёС‚Р°РµРј С‚РµРєСЃС‚
                        combined_text = ""
                        if combined_path and os.path.exists(combined_path):
                            with open(combined_path, 'r', encoding='utf-8') as f:
                                combined_text = f.read()
                        
                        if not combined_text.strip():
                            self.logger.warning(f"[SKIP] Нет текста для {reg_number}")
                            continue
                        
                        # РЎРѕС…СЂР°РЅСЏРµРј РІ Р‘Р”
                        zakupka = Zakupka(
                            reg_number=reg_number,
                            description=p.get('description', ''),
                            update_date=str(p.get('update_date', '')),
                            bid_end_date=(
                                p.get('bid_end_date')
                                or self.eis_downloader._extract_bid_end_date_from_text(combined_text)
                                or ""
                            ),
                            initial_price=(
                                p.get('initial_price')
                                if p.get('initial_price') is not None
                                else self.eis_downloader._extract_initial_price_from_text(combined_text)
                            ),
                            link=p.get('link', ''),
                            combined_text=combined_text
                        )
                        if self.eis.save_zakupka(zakupka):
                            saved_new += 1
                            
                            # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ РЅР° RAW (Р­С‚Р°Рї 1 -> 2)
                            self.db.zakupki.update_status(reg_number, ZakupkaStatus.RAW)
                            
                            self.logger.info(f"[OK] Сохранена закупка {reg_number} ({saved_new}/{limit})")
                            
                            # РЈРґР°Р»СЏРµРј РїР°РїРєСѓ вЂ” С‚РµРєСЃС‚ СѓР¶Рµ РІ Р‘Р”
                            zakupka_dir = self.eis_downloader.zakupki_dir / reg_number
                            if zakupka_dir.exists():
                                shutil.rmtree(zakupka_dir, ignore_errors=True)
                                self.logger.debug(f"Удалена папка {reg_number}")
                        
                    except Exception as e:
                        errors.append(f"{reg_number}: {e}")
                        self.logger.error(f"[ERROR] Ошибка обработки {reg_number}: {e}")
                
                page += 1
            
            if saved_new >= limit:
                self.logger.info(f"Достигнут лимит {limit} новых закупок")
            
            self.logger.info(
                "Stage 1 counters: saved_new=%s skipped_existing=%s errors=%s",
                saved_new,
                skipped_existing,
                len(errors),
            )
            
            success = len(errors) == 0
            message = (
                f"Загружено {saved_new} новых закупок "
                f"(пропущено {skipped_existing} существующих, ошибок {len(errors)})"
            )
            
        except Exception as e:
            success = False
            message = f"Ошибка загрузки: {e}"
            errors.append(str(e))
        
        self.logger.info(message)
        
        return StageResult(
            stage=1,
            success=success,
            message=message,
            data={
                "limit": limit,
                "saved_new": saved_new,
                "downloaded": saved_new,
                "skipped_existing": skipped_existing,
                "skipped": skipped_existing,
                "errors": len(errors),
            },
            errors=errors
        )
    
    def _get_print_form(self, reg_number: str) -> str:
        """
        РџРѕР»СѓС‡Р°РµС‚ С‚РµРєСЃС‚ РїРµС‡Р°С‚РЅРѕР№ С„РѕСЂРјС‹ Р·Р°РєСѓРїРєРё СЃ Р•РРЎ.
        
        Args:
            reg_number: Р РµРіРёСЃС‚СЂР°С†РёРѕРЅРЅС‹Р№ РЅРѕРјРµСЂ Р·Р°РєСѓРїРєРё
        
        Returns:
            РўРµРєСЃС‚ РїРµС‡Р°С‚РЅРѕР№ С„РѕСЂРјС‹ РёР»Рё РїСѓСЃС‚Р°СЏ СЃС‚СЂРѕРєР°
        """
        import requests
        from bs4 import BeautifulSoup
        from config import DEFAULT_HEADERS
        
        url = f"https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber={reg_number}"
        
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # РЈРґР°Р»СЏРµРј СЃРєСЂРёРїС‚С‹ Рё СЃС‚РёР»Рё
            for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()
            
            # РС‰РµРј РѕСЃРЅРѕРІРЅРѕР№ РєРѕРЅС‚РµРЅС‚
            main_content = soup.find('div', class_='wrapper')
            if not main_content:
                main_content = soup.find('main')
            if not main_content:
                main_content = soup
            
            # РР·РІР»РµРєР°РµРј С‚РµРєСЃС‚
            text = main_content.get_text(separator='\n', strip=True)
            
            # РћС‡РёС‰Р°РµРј РѕС‚ Р»РёС€РЅРёС… РїСѓСЃС‚С‹С… СЃС‚СЂРѕРє
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            result = '\n'.join(lines[:200])  # РџРµСЂРІС‹Рµ 200 СЃС‚СЂРѕРє
            
            if result:
                self.logger.info(f"Печатная форма загружена для {reg_number} ({len(result)} символов)")
                return result
                
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить печатную форму для {reg_number}: {e}")
        
        return ""
    def run_stage2(self, limit: int = None, reg_numbers: List[str] = None, overwrite: bool = False) -> StageResult:
        """
        Stage 2: ИИ-обработка текстов закупок через AIProcessorService (Cerebras).

        Args:
            limit: Количество закупок для обработки (None = все).
            reg_numbers: Список ID для обработки. Если передан, limit игнорируется.
            overwrite: Перезаписывать существующие AI-результаты.

        Returns:
            StageResult с итогом обработки.
        """
        self.logger.info(
            f"Stage 2: ИИ-обработка (limit={limit}, reg_numbers={len(reg_numbers) if reg_numbers else 'All'}, overwrite={overwrite})"
        )
        import time

        delay_s = getattr(settings, "ai_stage2_delay_s", 0.0)
        status_counts = self.db.zakupki.get_status_counts()
        raw_total = int(status_counts.get(ZakupkaStatus.RAW, 0))
        ai_error_total = int(status_counts.get(ZakupkaStatus.AI_ERROR, 0))
        self.logger.info("Stage 2 queue snapshot: raw=%s ai_error=%s", raw_total, ai_error_total)

        errors = []
        processed = 0
        processed_reg_numbers: List[str] = []
        failed_reg_numbers: List[str] = []
        cities = []
        skipped_no_text = 0
        skipped_already_processed = 0
        skipped_not_pending = 0

        try:
            if reg_numbers:
                zakupki = self.eis.get_by_reg_numbers(reg_numbers)
                if not zakupki:
                    self.logger.warning(f"[SKIP] Нет закупок по переданным reg_numbers: {reg_numbers}")
            else:
                if limit:
                    batch_limit = int(limit)
                    zakupki, pending_total = self.get_stage2_pending_page(offset=0, limit=batch_limit)
                    self.logger.info(
                        "Stage 2 page selection: pending_total=%s selected_now=%s limit=%s",
                        pending_total,
                        len(zakupki),
                        batch_limit,
                    )
                else:
                    zakupki = self.get_stage2_pending_items(limit=None, offset=0)
                    self.logger.info(
                        "Stage 2 full pending selection: selected_now=%s",
                        len(zakupki),
                    )

            self.logger.info(f"Найдено закупок для Stage 2: {len(zakupki)}")

            for i, zakupka in enumerate(zakupki, 1):
                reg_number = zakupka.reg_number

                existing = self.ai.get_result(reg_number)
                eligible, reason = self._stage2_eligibility_reason(zakupka, existing, overwrite=overwrite)
                if not eligible:
                    if reason == "no_combined_text":
                        self.logger.info(f"[SKIP] {reg_number}: отсутствует combined_text")
                        skipped_no_text += 1
                        self._log_stage_progress(2, reg_number, "skip", "no_combined_text")
                    elif reason == "already_has_ai_result":
                        self.logger.info(f"[SKIP] {reg_number}: AI-результат уже существует")
                        skipped_already_processed += 1
                        if (
                            (zakupka.status or "").strip() == ZakupkaStatus.AI_ERROR
                            and self._is_ai_result_usable(existing)
                        ):
                            self.db.zakupki.update_status(reg_number, ZakupkaStatus.AI_READY)
                            self._log_stage_progress(2, reg_number, "ok", "reused_existing_ai_result")
                        else:
                            self._log_stage_progress(2, reg_number, "skip", "already_has_ai_result")
                    else:
                        self.logger.info(
                            f"[SKIP] {reg_number}: статус '{zakupka.status}' не подходит для Stage 2"
                        )
                        skipped_not_pending += 1
                        self._log_stage_progress(2, reg_number, "skip", reason or "status_not_pending")
                    continue

                try:
                    self.logger.info(f"[{i}/{len(zakupki)}] Обработка AI: {reg_number}")

                    ai_result = self.ai_processor.process_zakupka(zakupka)

                    if ai_result is None:
                        err = f"{reg_number}: AI returned empty result"
                        errors.append(err)
                        failed_reg_numbers.append(reg_number)
                        self.logger.error(f"[ERROR] {err}")
                        self.db.zakupki.update_status(reg_number, ZakupkaStatus.AI_ERROR)
                        self._log_stage_progress(2, reg_number, "error", "empty_ai_result")
                        continue

                    if not self.ai.save_result(ai_result):
                        err = f"{reg_number}: failed to save AI result"
                        errors.append(err)
                        failed_reg_numbers.append(reg_number)
                        self.logger.error(f"[ERROR] {err}")
                        self.db.zakupki.update_status(reg_number, ZakupkaStatus.AI_ERROR)
                        self._log_stage_progress(2, reg_number, "error", "save_failed")
                        continue

                    processed += 1
                    processed_reg_numbers.append(reg_number)
                    if ai_result.city and ai_result.city not in cities:
                        cities.append(ai_result.city)

                    self.db.zakupki.update_status(reg_number, ZakupkaStatus.AI_READY)
                    self.logger.info(f"[OK] AI-результат сохранён: {reg_number}")
                    self._log_stage_progress(2, reg_number, "ok", ZakupkaStatus.AI_READY)

                except Exception as e:
                    errors.append(f"{reg_number}: {e}")
                    failed_reg_numbers.append(reg_number)
                    self.logger.error(f"[ERROR] Ошибка Stage 2 для {reg_number}: {e}")
                    self.db.zakupki.update_status(reg_number, ZakupkaStatus.AI_ERROR)
                    self._log_stage_progress(2, reg_number, "error", str(e))

                if delay_s and i < len(zakupki):
                    time.sleep(delay_s)

            self.logger.info("Итоги Stage 2:")
            self.logger.info(f"  [SKIP] Без текста: {skipped_no_text}")
            self.logger.info(f"  [SKIP] Уже обработано: {skipped_already_processed}")
            self.logger.info(f"  [SKIP] Не подходит по статусу: {skipped_not_pending}")
            self.logger.info(f"  [OK] Обработано: {processed}")
            self.logger.info(f"  [ERROR] Ошибок: {len(errors)}")

            success = processed > 0 or len(errors) == 0

            msg_parts = []
            if processed > 0:
                msg_parts.append(f"обработано {processed}")
            if skipped_already_processed > 0:
                msg_parts.append(f"пропущено (уже было) {skipped_already_processed}")
            if skipped_no_text > 0:
                msg_parts.append(f"пропущено (без текста) {skipped_no_text}")
            if skipped_not_pending > 0:
                msg_parts.append(f"пропущено (статус) {skipped_not_pending}")

            message = ", ".join(msg_parts) if msg_parts else "данные для обработки не найдены"
            if errors:
                message += f". ошибок: {len(errors)}"

        except Exception as e:
            success = False
            message = f"ошибка обработки Stage 2: {e}"
            errors.append(str(e))

        self.logger.info(message)

        return StageResult(
            stage=2,
            success=success,
            message=message,
            data={
                "limit": limit,
                "processed": processed,
                "processed_reg_numbers": processed_reg_numbers,
                "failed_reg_numbers": failed_reg_numbers,
            },
            errors=errors
        )
    def run_stage3(self, limit: int = None, reg_numbers: List[str] = None, overwrite: bool = False) -> StageResult:
        """
        Stage 3: РіРµРЅРµСЂР°С†РёСЏ СЃСЃС‹Р»РѕРє 2Р“РРЎ.
        
        Args:
            limit: РљРѕР»РёС‡РµСЃС‚РІРѕ Р·Р°РєСѓРїРѕРє РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё (None = РІСЃРµ)
            reg_numbers: РЎРїРёСЃРѕРє ID РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё
            overwrite: РџРµСЂРµР·Р°РїРёСЃС‹РІР°С‚СЊ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёРµ СЃСЃС‹Р»РєРё
        
        Returns:
            StageResult СЃ РґР°РЅРЅС‹РјРё Рѕ РіРµРЅРµСЂР°С†РёРё
        """
        self.logger.info(f"Stage 3: генерация ссылок (limit={limit}, reg_numbers={len(reg_numbers) if reg_numbers else 'All'}, overwrite={overwrite})")
        
        errors = []
        generated = 0
        items = []
        
        # ???????? ai_results
        if reg_numbers:
            ai_results = []
            for reg in reg_numbers:
                res = self.ai.get_result(reg)
                if res:
                    ai_results.append(res)
                else:
                    self.logger.warning(f"[SKIP] Нет AI-результата для {reg}")
        else:
            ai_results = self.ai.get_all_results()
            if limit:
                ai_results = ai_results[:limit]
        
        for ai_result in ai_results:
            try:
                self.logger.info(f"Stage 3 item: {ai_result.reg_number}")
                existing = self.eis.get_zakupka(ai_result.reg_number)
                if existing and existing.two_gis_url and not overwrite:
                    self.logger.info(f"Stage 3 skip existing url: {ai_result.reg_number}")
                    items.append({"reg_number": ai_result.reg_number, "two_gis_url": existing.two_gis_url})
                    continue

                self.logger.info(f"Stage 3 generate url for: {ai_result.reg_number}")
                url = self.run_stage3_for_zakupka(ai_result.reg_number, ai_result)
                self.logger.info(f"Stage 3 url result for {ai_result.reg_number}: {url!r}")
                if url:
                    generated += 1
                else:
                    self.logger.warning(f"Stage 3 no url generated: {ai_result.reg_number}")
                items.append({"reg_number": ai_result.reg_number, "two_gis_url": url})
            except Exception as e:
                self.logger.error(f"Stage 3 error for {ai_result.reg_number}: {e}")
                errors.append(f"{ai_result.reg_number}: {e}")
        
        success = generated > 0
        message = f"Сформировано {generated} ссылок из {len(ai_results)}"
        
        self.logger.info(message)
        
        return StageResult(
            stage=3,
            success=success,
            message=message,
            data={
                "total": len(ai_results),
                "generated": generated,
                "items": items
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
        Stage 4: РЎР±РѕСЂ РѕР±СЉСЏРІР»РµРЅРёР№ СЃ 2Р“РРЎ.
        
        Args:
            top_n: РљРѕР»РёС‡РµСЃС‚РІРѕ РѕР±СЉСЏРІР»РµРЅРёР№ РЅР° Р·Р°РєСѓРїРєСѓ
            limit: РљРѕР»РёС‡РµСЃС‚РІРѕ Р·Р°РєСѓРїРѕРє РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё (None = РІСЃРµ)
            get_details: РџРѕР»СѓС‡Р°С‚СЊ РґРµС‚Р°Р»Рё (РіРѕРґ РїРѕСЃС‚СЂРѕР№РєРё)
        
        Returns:
            StageResult СЃ РґР°РЅРЅС‹РјРё Рѕ СЃР±РѕСЂРµ
        """
        self.logger.info(f"Stage 4: сбор объявлений (top_n={top_n}, limit={limit}, details={get_details})")
        
        errors = []
        total_listings = 0
        processed = 0
        
        # РџРѕР»СѓС‡Р°РµРј Р·Р°РєСѓРїРєРё СЃ URL
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





