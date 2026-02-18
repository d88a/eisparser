"""Service for downloading and parsing purchases from zakupki.gov.ru."""

import os
import re
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from config.settings import settings
from models.zakupka import Zakupka
from repositories.zakupka_repo import ZakupkaRepository
from utils.logger import get_logger


class EISDownloaderService:
    """Downloader + parser for Stage 1 source data."""

    BASE_SEARCH_URL = (
        "https://zakupki.gov.ru/epz/order/extendedsearch/results.html"
        "?morphology=on"
        "&search-filter=%D0%94%D0%B0%D1%82%D0%B5+%D0%BE%D0%B1%D0%BD%D0%BE%D0%B2%D0%BB%D0%B5%D0%BD%D0%B8%D1%8F"
        "&sortDirection=false"
        "&recordsPerPage=_10"
        "&showLotsInfoHidden=false"
        "&sortBy=UPDATE_DATE"
        "&fz44=on"
        "&af=on"
        "&orderStages=AF"
        "&currencyIdGeneral=-1"
        "&okpd2Ids=8890776"
        "&okpd2IdsCodes=68.10.11.000"
        "&pageNumber={page}"
    )

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    EXCLUDED_KEYWORDS = [
        "многолотовый",
        "несколько объектов",
        "комплекс",
        "долевое строительство",
        "дду",
        "первичном",
        "две",
        "три",
        "четыре",
        "помещений",
    ]

    def __init__(self, zakupka_repo: ZakupkaRepository = None, zakupki_dir: str = None):
        self.repo = zakupka_repo
        self.zakupki_dir = Path(zakupki_dir or settings.zakupki_dir)
        self.logger = get_logger("EISDownloaderService")

    def search_zakupki(self, limit: int = 10, pages_to_scan: int = 20) -> List[Dict]:
        self.logger.info("Stage1 search started: limit=%s", limit)

        all_purchases: List[Dict] = []
        page = 1

        while page <= pages_to_scan and len(all_purchases) < limit * 5:
            html = self._fetch_search_page(page)
            if not html:
                if page == 1:
                    self.logger.error("EIS search page is unavailable")
                    return []
                page += 1
                continue

            page_purchases = self._parse_purchases_from_html(html)
            if not page_purchases:
                page += 1
                continue

            for p in page_purchases:
                desc_lower = (p.get("description") or "").lower()
                if any(keyword in desc_lower for keyword in self.EXCLUDED_KEYWORDS):
                    continue
                all_purchases.append(p)

            page += 1
            time.sleep(1)

        all_purchases.sort(key=lambda x: x.get("update_date", datetime.min), reverse=True)
        selected = all_purchases[:limit]
        self.logger.info("Stage1 search complete: found=%s", len(selected))
        return selected

    def download_documents(self, reg_number: str) -> Optional[str]:
        zakupka_dir = self.zakupki_dir / reg_number
        zakupka_dir.mkdir(parents=True, exist_ok=True)

        combined_path = zakupka_dir / "combined_text.txt"
        if combined_path.exists():
            return str(combined_path)

        all_texts: List[str] = []

        print_form_text = self._get_print_form(reg_number)
        if print_form_text:
            all_texts.append(f"=== PRINT FORM ===\\n{print_form_text}\\n")

        docs = self._get_documents_list(reg_number)
        if docs:
            docs_dir = zakupka_dir / "documents"
            docs_dir.mkdir(exist_ok=True)

            for doc in docs:
                file_path = self._download_document(doc, docs_dir)
                if not file_path:
                    continue
                text = self._extract_text(file_path)
                if text:
                    all_texts.append(f"=== Document: {doc['name']} ===\\n{text}\\n")

        if not all_texts:
            self.logger.warning("No extracted text for %s", reg_number)
            return None

        with open(combined_path, "w", encoding="utf-8") as f:
            f.write("\\n".join(all_texts))

        return str(combined_path)

    def _get_print_form(self, reg_number: str) -> Optional[str]:
        url = f"https://zakupki.gov.ru/epz/order/notice/printForm/view.html?regNumber={reg_number}"

        try:
            resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=30)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator="\\n", strip=True)
            lines = [line.strip() for line in text.split("\\n") if line.strip()]
            result = "\\n".join(lines)

            if result and len(result) > 100:
                return result
        except Exception as e:
            self.logger.debug("Print form load failed for %s: %s", reg_number, e)

        return None

    def download_and_save(self, limit: int = 10) -> Tuple[int, List[str]]:
        errors: List[str] = []
        saved = 0

        purchases = self.search_zakupki(limit)
        for p in purchases:
            reg_number = p.get("reg_number", "")
            try:
                combined_path = self.download_documents(reg_number)
                combined_text = ""
                if combined_path and os.path.exists(combined_path):
                    with open(combined_path, "r", encoding="utf-8") as f:
                        combined_text = f.read()

                zakupka = Zakupka(
                    reg_number=reg_number,
                    description=p.get("description", ""),
                    update_date=str(p.get("update_date", "")),
                    bid_end_date=p.get("bid_end_date", ""),
                    initial_price=p.get("initial_price"),
                    link=p.get("link", ""),
                    combined_text=combined_text,
                )

                if self.repo and self.repo.save(zakupka):
                    saved += 1
            except Exception as e:
                errors.append(f"{reg_number}: {e}")
                self.logger.error("Processing failed for %s: %s", reg_number, e)

        return saved, errors

    def _fetch_search_page(self, page: int) -> Optional[str]:
        url = self.BASE_SEARCH_URL.format(page=page)

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=30)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                self.logger.warning("Search page fetch attempt %s/3 failed: %s", attempt + 1, e)
                time.sleep(5)

        return None

    def _parse_purchases_from_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "html.parser")
        blocks = soup.find_all("div", class_="search-registry-entry-block")
        if not blocks:
            blocks = soup.find_all("div", class_="registry-entry__form")

        results = []
        for block in blocks:
            try:
                num_block = block.find("div", class_="registry-entry__header-mid__number")
                if not num_block:
                    continue

                link_el = num_block.find("a", href=True)
                if not link_el:
                    continue

                href = link_el["href"]
                if "regNumber=" in href:
                    reg_number = href.split("regNumber=")[1].split("&")[0]
                else:
                    reg_number = link_el.get_text(strip=True)

                purchase_link = "https://zakupki.gov.ru" + href if href.startswith("/") else href

                desc_el = block.find("div", class_="registry-entry__body-value")
                description = desc_el.get_text(strip=True) if desc_el else ""

                date_el = block.find("div", class_="data-block__value")
                date_text = date_el.get_text(strip=True) if date_el else ""
                update_date = self._parse_date(date_text)

                bid_end_date = ""
                initial_price: Optional[float] = None

                possible_blocks = block.select(".data-block, .registry-entry__body-block, .price-block")
                for db in possible_blocks:
                    title_el = db.select_one(".data-block__title, .registry-entry__body-title, .price-block__title")
                    if not title_el:
                        continue

                    title_text = title_el.get_text(strip=True).lower().replace("\xa0", " ")
                    value_el = db.select_one(".data-block__value, .registry-entry__body-value, .price-block__value")
                    if not value_el:
                        continue

                    bid_stems = [
                        "окончан",
                        "подач",
                        "заяв",
                        "срок",
                    ]
                    price_stems = [
                        "начальн",
                        "цен",
                        "нмцк",
                        "контракт",
                    ]

                    is_bid_label = (
                        (bid_stems[0] in title_text and bid_stems[1] in title_text)
                        or (bid_stems[1] in title_text and bid_stems[2] in title_text)
                        or (" ".join([bid_stems[3], bid_stems[1], bid_stems[2]]) in title_text)
                    )
                    is_price_label = (
                        (price_stems[0] in title_text and price_stems[1] in title_text)
                        or price_stems[2] in title_text
                        or (price_stems[1] in title_text and price_stems[3] in title_text)
                    )

                    if is_bid_label:
                        bid_end_date = value_el.get_text(strip=True)
                    elif is_price_label:
                        price_text = value_el.get_text(strip=True)
                        initial_price = self._parse_price_to_float(price_text)

                block_text = block.get_text(" ", strip=True)
                if not bid_end_date:
                    bid_end_date = self._extract_bid_end_date_from_text(block_text)
                if initial_price is None:
                    initial_price = self._extract_initial_price_from_text(block_text)

                results.append(
                    {
                        "reg_number": reg_number,
                        "description": description,
                        "update_date": update_date,
                        "bid_end_date": bid_end_date,
                        "initial_price": initial_price,
                        "link": purchase_link,
                    }
                )
            except Exception as e:
                self.logger.debug("Purchase block parse failed: %s", e)

        return results

    def _extract_bid_end_date_from_text(self, text: str) -> str:
        if not text:
            return ""

        normalized = str(text).replace("\xa0", " ")
        date_pattern = r"([0-3]?\d\.[01]?\d\.\d{4}(?:\s+[0-2]?\d:[0-5]\d(?::[0-5]\d)?)?)"
        patterns = [
            rf"(?:Окончание\s+подачи\s+заявок|Окончание\s+срока\s+подачи\s+заявок)\s*[:\-]?\s*{date_pattern}",
            rf"(?:Дата\s+и\s+время\s+окончания\s+подачи\s+заявок)\s*[:\-]?\s*{date_pattern}",
            rf"(?:Срок\s+подачи\s+заявок)\s*[:\-]?\s*{date_pattern}",
            rf"(?:подач[а-я]*\s+заявк[а-я]*)[^\d]{{0,40}}{date_pattern}",
        ]

        for pattern in patterns:
            m = re.search(pattern, normalized, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()

        for line in normalized.splitlines():
            line_low = line.lower()
            if "подач" in line_low and "заявк" in line_low:
                m = re.search(date_pattern, line)
                if m:
                    return m.group(1).strip()

        return ""

    def _parse_price_to_float(self, price_text: str) -> Optional[float]:
        if not price_text:
            return None

        text = str(price_text).replace("\xa0", " ").strip()
        clean = re.sub(r"[^\d,.\s]", "", text).replace(" ", "")
        if not clean:
            return None

        if "," in clean and "." in clean:
            clean = clean.replace(".", "").replace(",", ".")
        elif "," in clean:
            clean = clean.replace(",", ".")

        try:
            return float(clean)
        except ValueError:
            return None

    def _extract_initial_price_from_text(self, text: str) -> Optional[float]:
        if not text:
            return None

        normalized = str(text).replace("\xa0", " ")
        patterns = [
            r"(?:начальная(?:\s*\(максимальная\))?\s*цена|нмцк|цена\s*контракта)[^\d]{0,40}([\d\s]+(?:[.,]\d{1,2})?)",
            r"([\d\s]+(?:[.,]\d{1,2})?)\s*(?:₽|руб\.?)",
        ]

        for pattern in patterns:
            m = re.search(pattern, normalized, flags=re.IGNORECASE)
            if m:
                price = self._parse_price_to_float(m.group(1))
                if price is not None:
                    return price

        return None

    def _parse_date(self, date_str: str) -> datetime:
        if not date_str:
            return datetime.min
        date_str = date_str.strip()
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return datetime.min

    def _get_documents_list(self, reg_number: str) -> List[Dict]:
        url = f"https://zakupki.gov.ru/epz/order/notice/zk20/view/documents.html?regNumber={reg_number}"

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=30)
                resp.raise_for_status()
                break
            except Exception as e:
                self.logger.warning("Documents list attempt %s/3 failed: %s", attempt + 1, e)
                time.sleep(5)
        else:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        docs = []

        for block in soup.find_all("div", class_="attachment"):
            try:
                name_el = block.find("span", class_="section__value")
                if not name_el:
                    continue

                link_el = block.find("a", href=lambda href: href and "uid=" in href)
                if not link_el:
                    continue

                href = link_el["href"]
                uid = href.split("uid=")[1].split("&")[0]
                download_url = (
                    "https://zakupki.gov.ru/44fz/filestore/public/1.0/download/priz/file.html?uid="
                    f"{uid}"
                )

                docs.append({"name": name_el.get_text(strip=True), "url": download_url})
            except Exception:
                continue

        return docs

    def _download_document(self, doc_info: Dict, target_dir: Path) -> Optional[str]:
        name = doc_info.get("name", "document")
        url = doc_info.get("url")
        if not url:
            return None

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=self.DEFAULT_HEADERS, timeout=60)
                resp.raise_for_status()
                break
            except Exception as e:
                self.logger.warning("Document download attempt %s/3 failed: %s", attempt + 1, e)
                time.sleep(5)
        else:
            return None

        ext = self._detect_extension(resp.content, resp.headers)
        safe_name = re.sub(r"[^\w\s-]", "", name)[:50]
        hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
        filename = f"{safe_name}_{hash_suffix}{ext}"
        filepath = target_dir / filename

        with open(filepath, "wb") as f:
            f.write(resp.content)

        return str(filepath)

    def _detect_extension(self, content: bytes, headers: dict) -> str:
        header = content[:20]

        if header.startswith(b"%PDF"):
            return ".pdf"
        if header.startswith(b"PK\x03\x04"):
            snippet = str(content[:200])
            if "word/" in snippet:
                return ".docx"
            if "xl/" in snippet:
                return ".xlsx"
            return ".zip"
        if header.startswith(b"\xd0\xcf\x11\xe0"):
            return ".doc"

        return ".bin"

    def _extract_text(self, file_path: str) -> Optional[str]:
        try:
            import sys

            src_dir = Path(__file__).parent.parent
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))

            from text_extraction import extract_text_from_any_file

            text = extract_text_from_any_file(file_path)
            if text and not text.startswith("Error extracting") and not text.startswith("Unknown file type"):
                return text
        except ImportError as e:
            self.logger.warning("text_extraction import failed: %s", e)
        except Exception as e:
            self.logger.warning("Document text extraction failed: %s", e)

        return None
