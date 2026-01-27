"""
Сервис для ИИ-обработки закупок через OpenRouter.
"""
import json
import os
import re
from typing import Optional, Dict, Any, List
import requests
from requests.exceptions import JSONDecodeError

from config import (
    OPENROUTER_API_KEY_ENV,
    OPENROUTER_API_URL,
    OPENROUTER_MODEL,
)
from models.ai_result import AIResult
from models.zakupka import Zakupka
from repositories.ai_result_repo import AIResultRepository
from utils.logger import get_logger


class AIProcessorService:
    """
    Сервис для ИИ-обработки закупок через OpenRouter.
    
    Извлекает структурированные данные из текстов закупок
    (город, площадь, комнаты, цена и т.д.).
    """
    
    MAX_PROMPT_CHARS = 200_000
    HEAD_CHARS = 100_000
    TAIL_CHARS = 50_000
    
    # Системный промпт для ИИ
    SYSTEM_PROMPT = '''Ты — эксперт по анализу документов государственных закупок недвижимости в России.
Работаешь с русскоязычными документами (ЕИС, ФЗ-44 и т.п.).
Тебе даётся объединённый текст всех документов по ОДНОЙ закупке, включая печатную форму.
Нужно извлечь характеристики ОБЪЕКТА недвижимости и информацию о закупке.

Верни строго JSON, БЕЗ пояснений:
{
  "zakupka_name": string | null,
  "address": string | null,
  "rooms": number | string | null,
  "wear_percent": number | null,
  "zakazchik": string | null,
  "rooms_parsed": string | null,
  "area_min_m2": number | null,
  "area_max_m2": number | null,
  "building_floors_min": string | null,
  "floor": string | null,
  "year_build_str": string | null
}

ВАЖНЫЕ ИНСТРУКЦИИ:
1) Отвечай ТОЛЬКО JSON-объектом, без текста до или после.
2) НЕ выдумывай значения. Если информации нет — ставь null.
3) Числа (area_min_m2, area_max_m2) — без пробелов и разделителей.

ГДЕ ИСКАТЬ ДАННЫЕ:
- address: РЕГИОН и НАСЕЛЁННЫЙ ПУНКТ объекта недвижимости. 
  Регион: область, край, республика, округ, автономная область/округ.
  Населённый пункт: г. (город), с. (село), п. (посёлок), д. (деревня), пгт (посёлок городского типа), ст. (станица).
  Формат: "[Регион], [тип н.п.] [название]". 
  Примеры: "Пермский край, г. Пермь", "Республика Саха (Якутия), с. Зырянка", "Московская область, г. Балашиха", "Краснодарский край, ст. Новотитаровская".
  НЕ включай улицу, дом, квартиру — только регион и населённый пункт!
  Ищи в наименовании закупки, описании объекта, "Место поставки товара".
- rooms: ищи "Количество комнат" в характеристиках. Может быть "≥ 1", "не менее 2", "1", "2" и т.д.
- area_min_m2/area_max_m2: ищи "Общая площадь жилых помещений". Может быть "≥ 47.8" (значит min=47.8).
- floor: этаж квартиры.
- building_floors_min: этажность здания.'''

    def __init__(
        self,
        ai_result_repo: AIResultRepository = None,
        api_key: str = None,
        model_name: str = None
    ):
        """
        Args:
            ai_result_repo: Репозиторий для сохранения результатов
            api_key: API ключ OpenRouter (по умолчанию из env)
            model_name: Название модели (по умолчанию из config)
        """
        self.repo = ai_result_repo
        self.api_key = api_key or os.getenv(OPENROUTER_API_KEY_ENV)
        self.model_name = model_name or OPENROUTER_MODEL
        self.logger = get_logger("AIProcessorService")
    
    def _prepare_text(self, text: str) -> tuple[str, bool]:
        """Подготавливает текст для промпта (обрезает если нужно)."""
        if len(text) <= self.MAX_PROMPT_CHARS:
            return text, False
        head = text[:self.HEAD_CHARS]
        tail = text[-self.TAIL_CHARS:] if self.TAIL_CHARS < len(text) else ""
        marker = "\n*** Текст был сокращён для ограничений LLM ***\n"
        return head + marker + tail, True
    
    def _call_openrouter(self, text: str) -> Dict[str, Any]:
        """Вызывает OpenRouter API и возвращает извлечённые поля."""
        if not self.api_key:
            raise RuntimeError(f"Не найден API ключ в переменной окружения {OPENROUTER_API_KEY_ENV}")
        
        prepared_text, truncated = self._prepare_text(text)
        user_prompt = (
            "Ниже приведён объединённый текст по закупке.\n"
            "=== Начало объединённого текста ===\n"
            f"{prepared_text}\n"
            "=== Конец объединённого текста ===\n"
        )
        if truncated:
            user_prompt += "\n(Текст был автоматически сокращён.)"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "transforms": ["middle-out"],
        }
        
        resp = requests.post(
            OPENROUTER_API_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )
        
        self.logger.debug(f"OpenRouter status: {resp.status_code}")
        
        if resp.status_code != 200:
            self.logger.error(f"Ошибка API: {resp.status_code}, {resp.text[:500]}")
            return self._empty_result()
        
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except (JSONDecodeError, KeyError, IndexError) as e:
            self.logger.error(f"Ошибка парсинга ответа API: {e}")
            return self._empty_result()
        
        # Парсим JSON из content
        try:
            content = content.strip()
            if content.startswith("```"):
                content = content.strip("`")
                idx = content.find("{")
                if idx != -1:
                    content = content[idx:]
            result = json.loads(content)
            # Проверяем что это словарь, а не список
            if isinstance(result, list):
                self.logger.warning("OpenRouter вернул список, используем первый элемент или пустой результат")
                if result and isinstance(result[0], dict):
                    return result[0]
                return self._empty_result()
            return result
        except Exception as e:
            self.logger.error(f"Ошибка парсинга JSON от модели: {e}")
            return self._empty_result()
    
    def _empty_result(self) -> Dict[str, Any]:
        """Возвращает пустую структуру результата."""
        return {
            "zakupka_name": None, "address": None, "price_rub": None,
            "rooms": None, "wear_percent": None,
            "zakazchik": None,
            "city": None, "rooms_parsed": None, "area_min_m2": None,
            "area_max_m2": None, "building_floors_min": None,
            "floor_min": None, "floor_max": None, "year_build_str": None,
        }
    
    def _parse_rooms_value(self, rooms_raw) -> Optional[str]:
        """
        Преобразует значение rooms в формат, подходящий для rooms_parsed.
        
        Примеры:
        - 1, 2, 3 → "1", "2", "3"
        - "Однокомнатная" → "1"
        - "Двухкомнатная квартира" → "2"
        - "не менее 1" → "[1, 2, 3, 4, 5]"
        - ">= 2" → "[2, 3, 4, 5]"
        """
        if rooms_raw is None:
            return None
        if isinstance(rooms_raw, int):
            return str(rooms_raw)
        if isinstance(rooms_raw, str):
            s = rooms_raw.lower().strip()
            
            # Парсинг текстовых описаний комнат
            room_words = {
                'однокомнатн': 1, '1-комнатн': 1, '1 комнатн': 1,
                'двухкомнатн': 2, '2-комнатн': 2, '2 комнатн': 2,
                'трехкомнатн': 3, 'трёхкомнатн': 3, '3-комнатн': 3, '3 комнатн': 3,
                'четырехкомнатн': 4, 'четырёхкомнатн': 4, '4-комнатн': 4, '4 комнатн': 4,
                'пятикомнатн': 5, '5-комнатн': 5, '5 комнатн': 5,
            }
            
            # Проверяем текстовые описания (без условий "не менее", ">=" и т.д.)
            if not any(x in s for x in ['не менее', 'не более', 'больше', 'меньше', '>=', '<=', '>', '<', '≥', '≤']):
                for word, num in room_words.items():
                    if word in s:
                        return str(num)
            
            # Ищем числа в строке
            numbers = re.findall(r'\d+', s)
            if not numbers:
                return None
            
            # Если строка просто "2", "3", "4" - возвращаем число
            if s.replace(" ", "") in [str(n) for n in range(1, 10)]:
                return s.strip()
            
            # Если строка "2,3,4" - возвращаем список
            if ',' in s:
                try:
                    rooms_list = [int(n) for n in numbers]
                    return str(rooms_list)
                except ValueError:
                    return None
            
            # "не менее N", ">= N", ">N", "больше или равно N" → [N, N+1, ..., 5]
            if 'не менее' in s or '>=' in s or 'больше или равно' in s:
                try:
                    min_num = int(numbers[0])
                    possible_rooms = list(range(min_num, 6))
                    return str(possible_rooms)
                except ValueError:
                    return None
            
            # "> N", "больше N" → [N+1, N+2, ..., 5]
            if s.startswith('>') or 'больше' in s:
                try:
                    min_num = int(numbers[0]) + 1
                    possible_rooms = list(range(min_num, 6))
                    return str(possible_rooms)
                except ValueError:
                    return None
            
            # "не более N", "<= N" → [1, 2, ..., N]
            if 'не более' in s or '<=' in s:
                try:
                    max_num = int(numbers[0])
                    possible_rooms = list(range(1, max_num + 1))
                    return str(possible_rooms)
                except ValueError:
                    return None
            
            # "< N", "меньше N" → [1, 2, ..., N-1]
            if s.startswith('<') or 'меньше' in s:
                try:
                    max_num = int(numbers[0]) - 1
                    possible_rooms = list(range(1, max_num + 1))
                    return str(possible_rooms)
                except ValueError:
                    return None
            
            # Если просто одно число в строке, возвращаем его
            try:
                return str(int(numbers[0]))
            except ValueError:
                return None
        return None
    
    def _clean_city(self, city: str) -> str:
        """Убирает префиксы населённых пунктов (г., п., с., д. и т.д.)"""
        if not city:
            return city
        prefixes = ["г.", "г ", "п.", "п ", "с.", "с ", "д.", "д ",
                   "пос.", "пос ", "село ", "город ", "деревня "]
        clean = city.strip()
        for prefix in prefixes:
            if clean.lower().startswith(prefix.lower()):
                clean = clean[len(prefix):].strip()
                break
        return clean
    
    def process_zakupka(self, zakupka: Zakupka) -> Optional[AIResult]:
        """
        Обрабатывает одну закупку через ИИ.
        
        Args:
            zakupka: Объект закупки с текстом
        
        Returns:
            AIResult или None при ошибке
        """
        if not zakupka.combined_text:
            self.logger.warning(f"Нет текста для {zakupka.reg_number}")
            return None
        
        try:
            # Вызываем OpenRouter
            fields = self._call_openrouter(zakupka.combined_text)
            
            # Обработка rooms_parsed
            # 1. Если есть rooms — парсим его
            # 2. Если rooms пустой, но rooms_parsed — текст, парсим rooms_parsed
            rooms_raw = fields.get("rooms")
            rooms_parsed_raw = fields.get("rooms_parsed")
            
            self.logger.debug(f"rooms_raw={rooms_raw}, rooms_parsed_raw={rooms_parsed_raw}")
            
            if rooms_raw is not None:
                parsed = self._parse_rooms_value(rooms_raw)
                self.logger.debug(f"Parsed rooms: {rooms_raw} -> {parsed}")
                fields["rooms_parsed"] = parsed
            elif rooms_parsed_raw is not None:
                # ИИ вернул rooms_parsed напрямую (например "Однокомнатная квартира")
                parsed = self._parse_rooms_value(rooms_parsed_raw)
                self.logger.debug(f"Parsed rooms_parsed: {rooms_parsed_raw} -> {parsed}")
                if parsed:
                    fields["rooms_parsed"] = parsed
            
            # Очистка города от префиксов
            city = fields.get("city")
            if city:
                fields["city"] = self._clean_city(city)
            
            # Обратная совместимость: floor_min → floor
            if not fields.get("floor") and fields.get("floor_min"):
                fields["floor"] = fields.get("floor_min")
            
            # Если нет zakupka_name, используем description
            if not fields.get("zakupka_name"):
                fields["zakupka_name"] = zakupka.description
            
            # Создаём AIResult
            fields["reg_number"] = zakupka.reg_number
            ai_result = AIResult.from_dict(fields)
            
            self.logger.info(f"Обработана закупка: {zakupka.reg_number}, город: {ai_result.city}")
            return ai_result
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки {zakupka.reg_number}: {e}")
            return None
    
    def process_and_save(
        self,
        zakupki: List[Zakupka],
        skip_existing: bool = True
    ) -> tuple[int, List[str], List[str]]:
        """
        Обрабатывает список закупок и сохраняет результаты.
        
        Args:
            zakupki: Список закупок
            skip_existing: Пропускать уже обработанные
        
        Returns:
            Кортеж (обработано, список городов, список ошибок)
        """
        processed = 0
        cities = []
        errors = []
        
        for zakupka in zakupki:
            # Проверяем существующий результат
            if skip_existing and self.repo:
                existing = self.repo.get_by_id(zakupka.reg_number)
                if existing:
                    self.logger.debug(f"Пропуск {zakupka.reg_number} — уже обработан")
                    continue
            
            try:
                ai_result = self.process_zakupka(zakupka)
                if ai_result:
                    # Сохраняем
                    if self.repo and self.repo.save(ai_result):
                        processed += 1
                        if ai_result.city and ai_result.city not in cities:
                            cities.append(ai_result.city)
                            
            except Exception as e:
                errors.append(f"{zakupka.reg_number}: {e}")
        
        self.logger.info(f"Обработано: {processed}, городов: {len(cities)}")
        return processed, cities, errors
