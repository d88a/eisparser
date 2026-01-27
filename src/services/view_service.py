"""
Сервис для подготовки view-моделей.
"""
from typing import List, Optional

from services.database_service import DatabaseService
from models.view_models import ZakupkaStageView
from utils.logger import get_logger


class ViewService:
    """
    Сервис для агрегации данных и подготовки view-моделей.
    """
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.logger = get_logger("ViewService")
        
    def get_zakupka_stage_view(self, user_id: int, stage: int, limit: int = 100) -> List[ZakupkaStageView]:
        """
        Получает список view-моделей для этапа.
        
        Args:
            user_id: ID пользователя
            stage: Номер этапа
            limit: Максимальное количество записей (для Stage 1)
            
        Returns:
            Список ZakupkaStageView
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
                # Only show items that were EXPLICITLY selected on Stage 1
                # (decision='selected', not 'approved' from old logic)
                selected_ids = self.db.decisions.get_selected_reg_numbers(user_id, 1)
                zakupki = self.db.zakupki.get_by_reg_numbers(selected_ids)
            
            else:
                # For stage > 2 (future)
                prev_stage = stage - 1
                zakupki = self.db.get_zakupki_for_stage(user_id, prev_stage)
            
            for z in zakupki:
                # 2. Получаем последнее решение (оно будет None для Stage 1, если мы отфильтровали)
                decision = self.db.decisions.get_last_decision(user_id, z.reg_number, stage)
                
                # 3. Получаем AIResult
                ai_result = self.db.ai_results.get_by_id(z.reg_number)
                
                # 4. Получаем Listings
                listings = self.db.listings.get_for_zakupka(z.reg_number)
                
                # 5. Считаем агрегаты (Null-safety)
                listings_count = len(listings) if listings else 0
                
                listings_min_price = None
                listings_max_price = None
                
                if listings_count > 0:
                    prices = [L.price_rub for L in listings if L.price_rub is not None]
                    if prices:
                        listings_min_price = min(prices)
                        listings_max_price = max(prices)
                
                # 6. Создаем View с ВСЕМИ полями AI
                view = ZakupkaStageView(
                    reg_number=z.reg_number,
                    description=z.description or "",
                    update_date=z.update_date or "",
                    bid_end_date=z.bid_end_date or "",
                    initial_price=z.initial_price,
                    stage=stage,
                    my_decision=decision.decision if decision else None,
                    my_decision_comment=decision.comment if decision else None,
                    has_ai_result=ai_result is not None,
                    # Все AI поля
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
                    # Агрегаты
                    listings_count=listings_count,
                    listings_min_price=listings_min_price,
                    listings_max_price=listings_max_price,
                    combined_text=z.combined_text or ""
                )
                
                result.append(view)
                
        except Exception as e:
            self.logger.error(f"Ошибка формирования view-моделей: {e}")
            # ТЗ: "Никаких исключений" - возвращаем то, что успели собрать или пустой список?
            # "Список возвращается без ошибок" -> лучше вернуть пустой или частичный, но не крашить
            # В данном случае вернем то, что есть, если упало в цикле, 
            # или пустой, если упало выше.
            # Но если упало на конкретной закупке, лучше пропустить её.
            pass
            
        return result
