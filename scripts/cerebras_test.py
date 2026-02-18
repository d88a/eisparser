import json
import os
import sys
from pathlib import Path

import requests


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]
    load_env(base_dir / "src" / ".env")

    api_key = os.getenv("CEREBRAS_API_KEY")
    model = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
    base_url = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")

    if not api_key:
        print("CEREBRAS_API_KEY не задан в src/.env")
        return 1

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Отвечай кратко."},
            {"role": "user", "content": "Ответь одним словом: тест"},
        ],
        "temperature": 0.1,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.RequestException as exc:
        print(f"Ошибка запроса: {exc}")
        return 1

    print(f"HTTP {resp.status_code}")
    if resp.headers.get("Content-Type", "").startswith("application/json"):
        try:
            data = resp.json()
            print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
        except Exception:
            print(resp.text[:1000])
    else:
        print(resp.text[:1000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
