# Локальный запуск через SSH-туннель (Windows + PowerShell)

## 1) Открой окно №1: туннель (держать открытым)

```powershell
cd D:\Anna\eisparser
ssh -vvv -4 -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 15440:10.19.4.2:5432 c77461@priv-mag.ru
```

Если в этом окне появился prompt `c77461@h43:~$` и соединение не закрывается — туннель активен.

## 2) Открой окно №2: проверка порта и БД

```powershell
netstat -ano | findstr 15440
D:\Anna\eisparser\.venv\Scripts\python.exe -c "import psycopg2; psycopg2.connect('postgresql://c77461_priv_mag_ru:jMLF9%5EbCh%21nh_nT@127.0.0.1:15440/c77461_priv_mag_ru?sslmode=require').close(); print('DB OK')"
```

Ожидаемый результат: `DB OK`.

## 3) Настрой src/.env

```env
DATABASE_URL=postgresql://c77461_priv_mag_ru:jMLF9%5EbCh%21nh_nT@127.0.0.1:15440/c77461_priv_mag_ru?sslmode=require
```

Важно: пароль в URL должен быть закодирован (`^` -> `%5E`, `!` -> `%21`).

## 4) В этом же окне №2 запусти админку

```powershell
cd D:\Anna\eisparser
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
D:\Anna\eisparser\.venv\Scripts\python.exe src\main.py server --host 127.0.0.1 --port 8000
```

Открыть в браузере: `http://127.0.0.1:8000`.

---

## Если снова ошибка подключения к БД

1. Проверь, что туннель (окно №1) не закрылся.
2. Проверь локальный порт:

```powershell
netstat -ano | findstr 15440
```

3. Если порт занят «битым» `ssh.exe`, убей процесс по PID:

```powershell
taskkill /PID 12345 /F
```

(подставь реальный PID, без `< >`).
4. Подними туннель заново и снова выполни тест `DB OK`.
