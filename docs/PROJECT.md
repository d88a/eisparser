# EIS Parser - Парсер закупок недвижимости

## Обзор

Автоматизированная система для:
1. Загрузки закупок с сайта ЕИС (zakupki.gov.ru)
2. Анализа ИИ (извлечение параметров квартир)
3. Генерации ссылок на 2ГИС
4. Сбора объявлений с 2ГИС для сравнения цен

## Структура проекта

```
eisparser/
├── src/                    # Исходный код
│   ├── gis/                # Генерация URL 2ГИС
│   ├── realty_scraper/     # Парсер 2ГИС
│   ├── config.py           # Конфигурация
│   ├── database.py         # Работа с SQLite
│   ├── ai_extractor.py     # ИИ-анализ (Gemini)
│   ├── eis_downloader.py   # Загрузка с ЕИС
│   ├── run_pipeline.py     # Основной пайплайн
│   ├── stage1_*.py         # Загрузка закупок
│   ├── stage2_*.py         # ИИ-обработка
│   ├── stage3_*.py         # Генерация ссылок
│   └── stage4_*.py         # Сбор объявлений
├── results/                # Результаты (БД)
│   └── eis_data.db
├── map/                    # Геоданные
│   └── ru_localities_geoapify.csv
├── backup/                 # Бэкап
└── requirements.txt
```

## База данных (SQLite)

### Таблица `zakupki`
| Поле | Тип | Описание |
|------|-----|----------|
| reg_number | TEXT PK | Регистрационный номер |
| description | TEXT | Название закупки |
| link | TEXT | Ссылка на ЕИС |
| combined_text | TEXT | Полный текст |
| two_gis_url | TEXT | Сгенерированная ссылка |

### Таблица `ai_results`
| Поле | Тип | Описание |
|------|-----|----------|
| reg_number | TEXT PK | Связь с zakupki |
| city | TEXT | Город |
| area_min_m2 | REAL | Мин. площадь |
| rooms_parsed | TEXT | Комнаты (JSON) |
| floor | TEXT | Этаж (текст) |
| price_rub | REAL | Цена |

### Таблица `listings`
| Поле | Тип | Описание |
|------|-----|----------|
| zakupka_reg_number | TEXT | Связь с zakupki |
| rank | INTEGER | Позиция в выдаче |
| price_rub | INTEGER | Цена объявления |
| address | TEXT | Адрес |
| rooms | INTEGER | Комнаты |
| area_m2 | REAL | Площадь |
| building_year | INTEGER | Год постройки |
| external_url | TEXT | Ссылка ДомКлик/Циан |

## Стадии пайплайна

### Stage 1: Загрузка закупок
```bash
cd src
python stage1_download_to_db.py --search "квартира" --limit 10
```

### Stage 2: ИИ-обработка
```bash
python stage2_ai_processing.py --from-db
```

### Stage 3: Генерация ссылок 2ГИС
```bash
python stage3_links.py --from-db
```

### Stage 4: Сбор объявлений
```bash
# Без деталей (быстро)
python stage4_collect_listings.py --from-db --top-n 5

# С деталями (год постройки)
python stage4_collect_listings.py --from-db --top-n 5 --details

# С прокси
python stage4_collect_listings.py --from-db --top-n 5 --proxy "http://host:port"
```

### Полный пайплайн
```bash
python run_pipeline.py --search "квартира" --limit 10 --stage1 --stage2 --stage3 --stage4
```

## Конфигурация

Файл `src/config.py`:
- `GEMINI_API_KEY` — ключ API Gemini
- `STAGE4_HEADLESS` — безголовый режим браузера
- `STAGE4_USE_REAL_CHROME` — использовать Chrome

## Зависимости

```bash
pip install -r requirements.txt
```

Основные:
- playwright (браузер)
- playwright-stealth (anti-detection)
- google-generativeai (Gemini)
- sqlite3 (БД)

## Важно

- **VPN**: 2ГИС блокирует иностранные IP. Нужен российский VPN.
- **Stealth**: Используется playwright-stealth для обхода детекции.
- **Координаты**: Берутся из `map/ru_localities_geoapify.csv`
