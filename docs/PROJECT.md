# EIS Parser — админ-панель модерации закупок (MVP)

## Назначение
Система автоматизирует обработку закупок недвижимости по этапам:
1. Stage 1: загрузка списка закупок с ЕИС и сохранение выбранных.
2. Stage 2: ручной ИИ-анализ выбранных закупок.
3. Stage 3: генерация ссылок 2ГИС по ИИ-результатам.
4. Stage 4: сбор объявлений по ссылке, сформированной на Stage 3.

Текущий продуктовый фокус: стабильная админка Stage 1–4.

## Контракт Stage 3 -> Stage 4
- Каноническая рабочая ссылка процесса хранится в `zakupki.two_gis_url` и формируется на Stage 3.
- Stage 4 запускается только по этой канонической ссылке и не пересчитывает ее.
- Если `zakupki.two_gis_url` отсутствует, в UI показывается предупреждение: `Ссылки нет (Этап 3)`.
- Ссылки карточек объявлений (`.../ad/...`) и внешние ссылки (`cian`, `domclick`, `avito`) не являются ссылкой процесса Stage 3.

## Структура проекта
```text
eisparser/
├── src/
│   ├── api/                # FastAPI + роуты
│   ├── config/             # настройки и .env
│   ├── gis/                # генерация URL 2ГИС
│   ├── models/             # dataclass-модели
│   ├── repositories/       # доступ к SQLite
│   ├── services/           # бизнес-логика
│   ├── web/                # templates + static
│   ├── pipeline.py         # оркестратор стадий
│   └── main.py             # CLI и запуск сервера
├── docs/
├── results/                # БД SQLite
├── map/                    # геоданные
└── zakupki/                # временные файлы загрузки
```

## Конфигурация
Файл: `src/.env`

Ключевые переменные:
- `CEREBRAS_API_KEY`
- `CEREBRAS_BASE_URL`
- `CEREBRAS_MODEL`
- `ADMIN_PASSWORD`
- `DATABASE_PATH`
- `COORDINATES_CSV_PATH`
- `AI_STAGE2_DELAY_S`
- `STAGE4_HEADLESS`
- `STAGE4_USE_REAL_CHROME`
- `PROXY_URL` (опционально)

## Развёртывание на новом Windows ПК

### 1. Установка Python
- Ставим Python 3.11.x (x64).
- Проверяем:
```powershell
python --version
where.exe python
```
Ожидается путь к реальному `python.exe` (например `C:\Program Files\Python311\python.exe`), а не только `WindowsApps`.

### 2. Создание виртуального окружения
В корне проекта:
```powershell
cd D:\Anna\eisparser
python -m venv .venv
```

### 3. Активация `.venv`
Если PowerShell блокирует скрипты:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
Затем:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Установка зависимостей
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Проверка `.env`
- Убедиться, что в `src/.env` заданы минимум:
  - `ADMIN_PASSWORD`
  - `CEREBRAS_API_KEY`
  - `DATABASE_PATH` (если нужен нестандартный путь)

### 6. Запуск сервера
```powershell
python src\main.py server --host 127.0.0.1 --port 8000
```

### 7. Вход в админку
- Открыть `http://127.0.0.1:8000/admin/login`
- Ввести пароль из `ADMIN_PASSWORD`.

## Полезные команды
```powershell
python src\main.py stats
python src\main.py stage1 --limit 10
python src\main.py stage2 --limit 5
python src\main.py stage3 --limit 5
python src\main.py stage4 --top-n 5 --limit 2 --details
```

## Примечания
- Для парсинга 2ГИС на Stage 4 может понадобиться российский IP/прокси.
- Если страница не открывается, сначала проверьте, не занят ли порт 8000.
