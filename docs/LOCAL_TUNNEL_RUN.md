# Локальный запуск через SSH-туннель к VDS (Windows + PowerShell)

## 1) Окно №1: поднять туннель
```powershell
cd D:\Anna\eisparser
ssh -vvv -4 -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 15440:127.0.0.1:5432 root@213.189.219.55
```

## 2) Окно №2: проверить порт и БД
```powershell
netstat -ano | findstr 15440
D:\Anna\eisparser\.venv\Scripts\python.exe -c "import psycopg2; psycopg2.connect('postgresql://eisparser_user:<PASSWORD>@127.0.0.1:15440/eisparser_db').close(); print('DB OK')"
```

## 3) Настроить `src/.env` локально
```env
DATABASE_URL=postgresql://eisparser_user:<PASSWORD>@127.0.0.1:15440/eisparser_db
```

## 4) Запуск API локально
```powershell
cd D:\Anna\eisparser
$env:PYTHONPATH="src"
D:\Anna\eisparser\.venv\Scripts\python.exe src\main.py server --host 127.0.0.1 --port 8000
```

Открыть: `http://127.0.0.1:8000`.

## Если не подключается
1. Проверить, что окно туннеля не закрыто.
2. Проверить порт `15440` через `netstat`.
3. Убить зависший `ssh.exe` по PID:
```powershell
taskkill /PID 12345 /F
```
4. Поднять туннель заново.
