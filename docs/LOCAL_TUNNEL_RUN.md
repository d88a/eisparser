# Запуск туннеля и админки на ПК

## 1) Поднять SSH-туннель к PostgreSQL NetAngels

Откройте отдельное окно терминала (PowerShell/Tabby) и выполните:

```bash
ssh -4 -L 15434:postgres.c77461.h2:5432 c77461@priv-mag.ru
```

Важно: это окно не закрывать, пока работает админка.

## 2) Проверить, что порт туннеля слушается на ПК

В новом окне PowerShell:

```powershell
netstat -ano | findstr 15434
```

Ожидается `LISTENING` на `127.0.0.1:15434`.

## 3) Проверить доступ к БД через туннель

```powershell
D:\Anna\eisparser\.venv\Scripts\python.exe -c "import psycopg2; psycopg2.connect('postgresql://c77461_priv_mag_ru:jMLF9%5EbCh%21nh_nT@127.0.0.1:15434/c77461_priv_mag_ru?sslmode=require').close(); print('DB OK')"
```

Если вывод `DB OK` - туннель рабочий.

## 4) Настройка DATABASE_URL локально

Файл: `D:\Anna\eisparser\src\.env`

```env
DATABASE_URL=postgresql://c77461_priv_mag_ru:jMLF9%5EbCh%21nh_nT@127.0.0.1:15434/c77461_priv_mag_ru?sslmode=require
```

## 5) Запуск админки на ПК

```powershell
cd D:\Anna\eisparser
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
D:\Anna\eisparser\.venv\Scripts\python.exe src\main.py server --host 127.0.0.1 --port 8000
```

Открыть:
```text
http://127.0.0.1:8000/
```

## 6) Остановка
- остановить сервер: `Ctrl+C` в окне с `main.py server`;
- остановить туннель: `Ctrl+C` в окне SSH.

## Типовые проблемы
1. `connection refused` на `127.0.0.1:15434`:
- туннель не поднят или закрыт;
- проверьте `netstat -ano | findstr 15434`.

2. `password authentication failed`:
- проверьте логин/пароль в `DATABASE_URL`;
- оставляйте URL-encoding спецсимволов в пароле (`%5E`, `%21`, и т.д.).

3. `server closed the connection unexpectedly`:
- туннель оборвался;
- переподключите SSH и снова выполните шаги 2-3.
