# Синхронизация кода с VDS на ПК (1-в-1)

Цель: сделать локальный `D:\Anna\eisparser` максимально точной копией `/opt/eisparser`.

## 1) На ПК: скачать snapshot с сервера
```powershell
cd D:\Anna
ssh root@213.189.219.55 "cd /opt && tar \
  --exclude='eisparser/.venv' \
  --exclude='eisparser/results' \
  --exclude='eisparser/zakupki' \
  --exclude='eisparser/__pycache__' \
  --exclude='eisparser/.pytest_cache' \
  --exclude='eisparser/*.sql' \
  --exclude='eisparser/*.sql.gz' \
  --exclude='eisparser/*.tar.gz' \
  --exclude='eisparser/*.zip' \
  -czf /tmp/eisparser_sync.tar.gz eisparser"

scp root@213.189.219.55:/tmp/eisparser_sync.tar.gz D:\Anna\eisparser_sync.tar.gz
```

## 2) Распаковать во временную папку
```powershell
Remove-Item -Recurse -Force D:\Anna\_sync_eisparser -ErrorAction SilentlyContinue
New-Item -ItemType Directory D:\Anna\_sync_eisparser | Out-Null
tar -xzf D:\Anna\eisparser_sync.tar.gz -C D:\Anna\_sync_eisparser
```

## 3) Зеркально обновить локальный репозиторий
```powershell
robocopy D:\Anna\_sync_eisparser\eisparser D:\Anna\eisparser /MIR /R:2 /W:2 /NFL /NDL /NP `
  /XD .git .venv results zakupki __pycache__ .pytest_cache `
  /XF *.sql *.sql.gz *.tar.gz *.zip
```

## 4) Проверка
```powershell
cd D:\Anna\eisparser
git status --short
```

## 5) Очистка
```powershell
Remove-Item -Recurse -Force D:\Anna\_sync_eisparser
Remove-Item -Force D:\Anna\eisparser_sync.tar.gz
```

Примечание: команды запросят пароль `root` от VDS.
