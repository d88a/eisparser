"""
РЎРµСЂРІРёСЃ РґР»СЏ РїРѕРґРіРѕС‚РѕРІРєРё view-РјРѕРґРµР»РµР№.
"""
from typing import List, Optional

from services.database_service import DatabaseService
from models.view_models import ZakupkaStageView
from utils.logger import get_logger


class ViewService:
    """
    РЎРµСЂРІРёСЃ РґР»СЏ Р°РіСЂРµРіР°С†РёРё РґР°РЅРЅС‹С… Рё РїРѕРґРіРѕС‚РѕРІРєРё view-РјРѕРґРµР»РµР№.
    """
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.logger = get_logger("ViewService")
        
    def get_zakupka_stage_view(self, user_id: int, stage: int, limit: int = 100) -> List[ZakupkaStageView]:
        """
        РџРѕР»СѓС‡Р°РµС‚ СЃРїРёСЃРѕРє view-РјРѕРґРµР»РµР№ РґР»СЏ СЌС‚Р°РїР°.
        
        Args:
            user_id: ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
            stage: РќРѕРјРµСЂ СЌС‚Р°РїР°
            limit: РњР°РєСЃРёРјР°Р»СЊРЅРѕРµ РєРѕР»РёС‡РµСЃС‚РІРѕ Р·Р°РїРёСЃРµР№ (РґР»СЏ Stage 1)
            
        Returns:
            РЎРїРёСЃРѕРє ZakupkaStageView
        """
        result = []
        
        try:
            # SPECIAL HANDLING FOR STAGE 1 (Initial Intake/Selection)
            if stage == 1:
                # 1. Get ALL raw purchases
                all_zakupki = self.db.zakupki.get_all()
                
                # 2. Sort by processed_at descending (newest loaded first)
                zakupki = sorted(
                    all_zakupki, 
                    key=lambda x: str(x.processed_at) if x.processed_at else "",
                    reverse=True
                )
                
                # 3. Apply limit
                zakupki = zakupki[:limit]
            
            # SPECIAL HANDLING FOR STAGE 2 (AI Review)
            elif stage == 2:
                # Stage 2 uses unified pending source (raw/ai_error).
                zakupki = self.db.get_stage2_pending_items(overwrite=False, limit=None)
                self.logger.info("Stage2 view selection: selected=%s", len(zakupki))
            
            else:
                # For stage > 2 (future)
                prev_stage = stage - 1
                zakupki = self.db.get_zakupki_for_stage(user_id, prev_stage)
            
            for z in zakupki:
                # 2. РџРѕР»СѓС‡Р°РµРј РїРѕСЃР»РµРґРЅРµРµ СЂРµС€РµРЅРёРµ (РѕРЅРѕ Р±СѓРґРµС‚ None РґР»СЏ Stage 1, РµСЃР»Рё РјС‹ РѕС‚С„РёР»СЊС‚СЂРѕРІР°Р»Рё)
                decision = self.db.decisions.get_last_decision(user_id, z.reg_number, stage)
                
                # 3. РџРѕР»СѓС‡Р°РµРј AIResult
                ai_result = self.db.ai_results.get_by_id(z.reg_number)
                
                # 4. РџРѕР»СѓС‡Р°РµРј Listings
                listings = self.db.listings.get_for_zakupka(z.reg_number)
                
                # 5. РЎС‡РёС‚Р°РµРј Р°РіСЂРµРіР°С‚С‹ (Null-safety)
                listings_count = len(listings) if listings else 0
                
                listings_min_price = None
                listings_max_price = None
                
                if listings_count > 0:
                    prices = [L.price_rub for L in listings if L.price_rub is not None]
                    if prices:
                        listings_min_price = min(prices)
                        listings_max_price = max(prices)
                
                # 6. РЎРѕР·РґР°РµРј View СЃ Р’РЎР•РњР РїРѕР»СЏРјРё AI
                view = ZakupkaStageView(
                    reg_number=z.reg_number,
                    description=z.description or "",
                    update_date=z.update_date or "",
                    bid_end_date=z.bid_end_date or "",
                    initial_price=z.initial_price,
                    stage=stage,
                    processed_at=z.processed_at.isoformat() if z.processed_at else None,
                    my_decision=decision.decision if decision else None,
                    my_decision_comment=decision.comment if decision else None,
                    has_ai_result=ai_result is not None,
                    # Р’СЃРµ AI РїРѕР»СЏ
                    ai_zakupka_name=ai_result.zakupka_name if ai_result else None,
                    ai_address=ai_result.address if ai_result else None,
                    ai_city=ai_result.city if ai_result else None,
                    ai_area_min=ai_result.area_min_m2 if ai_result else None,
                    ai_area_max=ai_result.area_max_m2 if ai_result else None,
                    ai_rooms=ai_result.rooms if ai_result else None,
                    ai_rooms_parsed=ai_result.rooms_parsed if ai_result else None,
                    ai_floor=ai_result.floor if ai_result else None,
                    ai_building_floors_min=ai_result.building_floors_min if ai_result else None,
                    ai_year_build=ai_result.year_build_str if ai_result else None,
                    ai_wear_percent=ai_result.wear_percent if ai_result else None,
                    ai_zakazchik=ai_result.zakazchik if ai_result else None,
                    # РђРіСЂРµРіР°С‚С‹
                    listings_count=listings_count,
                    listings_min_price=listings_min_price,
                    listings_max_price=listings_max_price,
                    combined_text=z.combined_text or ""
                )
                
                result.append(view)
                
        except Exception as e:
            self.logger.error(f"РћС€РёР±РєР° С„РѕСЂРјРёСЂРѕРІР°РЅРёСЏ view-РјРѕРґРµР»РµР№: {e}")
            # РўР—: "РќРёРєР°РєРёС… РёСЃРєР»СЋС‡РµРЅРёР№" - РІРѕР·РІСЂР°С‰Р°РµРј С‚Рѕ, С‡С‚Рѕ СѓСЃРїРµР»Рё СЃРѕР±СЂР°С‚СЊ РёР»Рё РїСѓСЃС‚РѕР№ СЃРїРёСЃРѕРє?
            # "РЎРїРёСЃРѕРє РІРѕР·РІСЂР°С‰Р°РµС‚СЃСЏ Р±РµР· РѕС€РёР±РѕРє" -> Р»СѓС‡С€Рµ РІРµСЂРЅСѓС‚СЊ РїСѓСЃС‚РѕР№ РёР»Рё С‡Р°СЃС‚РёС‡РЅС‹Р№, РЅРѕ РЅРµ РєСЂР°С€РёС‚СЊ
            # Р’ РґР°РЅРЅРѕРј СЃР»СѓС‡Р°Рµ РІРµСЂРЅРµРј С‚Рѕ, С‡С‚Рѕ РµСЃС‚СЊ, РµСЃР»Рё СѓРїР°Р»Рѕ РІ С†РёРєР»Рµ, 
            # РёР»Рё РїСѓСЃС‚РѕР№, РµСЃР»Рё СѓРїР°Р»Рѕ РІС‹С€Рµ.
            # РќРѕ РµСЃР»Рё СѓРїР°Р»Рѕ РЅР° РєРѕРЅРєСЂРµС‚РЅРѕР№ Р·Р°РєСѓРїРєРµ, Р»СѓС‡С€Рµ РїСЂРѕРїСѓСЃС‚РёС‚СЊ РµС‘.
            pass
            
        return result
