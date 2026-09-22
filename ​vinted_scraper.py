"""
vinted_scraper.py
------------------
Interogheaza API-ul public folosit de vinted.ro (acelasi pe care il foloseste
site-ul in browser) pentru a gasi anunturi dintr-o categorie/cautare data si
extrage tendintele: cuvinte cheie frecvente, brand-uri frecvente, interval de preturi.

IMPORTANT (citeste inainte de folosire):
- Acesta NU este un API oficial/documentat de Vinted. E endpoint-ul intern folosit
  de site cand cauti. Vinted poate schimba structura oricand sau poate bloca
  cereri automate (rate limiting / Cloudflare). Codul include:
    * un User-Agent realist
    * o sesiune care ia intai cookie-uri de pe pagina principala
    * pauze intre cereri
  ...dar NU garanteaza functionare pe termen lung. Daca Vinted incepe sa
  returneze 403, va trebui probabil sa adaugi un proxy/rotatie de headere.
- Foloseste responsabil: nu bombarda serverul cu cereri, respecta un interval
  rezonabil intre cautari (implicit 2-3 secunde).
"""

from __future__ import annotations
import time
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Dict, Optional

import requests

BASE_HOST = "https://www.vinted.ro"
SEARCH_ENDPOINT = f"{BASE_HOST}/api/v2/catalog/items"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.vinted.ro/catalog",
}


@dataclass
class VintedItem:
    id: int
    title: str
    price: float
    currency: str
    brand: Optional[str]
    size: Optional[str]
    url: str
    photo_url: Optional[str] = None


@dataclass
class TrendReport:
    query: str
    sample_size: int
    top_keywords: List[str] = field(default_factory=list)
    top_brands: List[str] = field(default_factory=list)
    avg_price: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    example_titles: List[str] = field(default_factory=list)


class VintedClient:
    def __init__(self, delay_range=(1.5, 3.0)):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.delay_range = delay_range
        self._warmed_up = False

    def _warm_up(self):
        """Ia cookie-uri reale accesand intai homepage-ul (necesar de multe ori
        pentru ca API-ul sa nu respinga cererea)."""
        if self._warmed_up:
            return
        try:
            self.session.get(BASE_HOST, timeout=10)
        except requests.RequestException:
            pass
        self._warmed_up = True

    def _sleep(self):
        time.sleep(random.uniform(*self.delay_range))

    def search(self, query: str, per_page: int = 40, max_pages: int = 2) -> List[VintedItem]:
        """Cauta anunturi pentru un text (ex: 'geaca de piele barbati')."""
        self._warm_up()
        items: List[VintedItem] = []

        for page in range(1, max_pages + 1):
            params = {
                "search_text": query,
                "per_page": per_page,
                "page": page,
                "order": "newest_first",
            }
            try:
                resp = self.session.get(SEARCH_ENDPOINT, params=params, timeout=15)
            except requests.RequestException as e:
                print(f"[vinted_scraper] Eroare de retea la pagina {page}: {e}")
                break

            if resp.status_code != 200:
                print(
                    f"[vinted_scraper] Vinted a returnat status {resp.status_code} "
                    f"(posibil blocare anti-bot). Ma opresc aici."
                )
                break

            try:
                data = resp.json()
            except ValueError:
                print("[vinted_scraper] Raspunsul nu e JSON valid, ma opresc.")
                break

            raw_items = data.get("items", [])
            if not raw_items:
                break

            for it in raw_items:
                try:
                    items.append(
                        VintedItem(
                            id=it.get("id"),
                            title=it.get("title", "") or "",
                            price=float((it.get("price") or {}).get("amount", 0) or 0),
                            currency=(it.get("price") or {}).get("currency_code", "RON"),
                            brand=(it.get("brand_title") or None),
                            size=(it.get("size_title") or None),
                            url=it.get("url", ""),
                            photo_url=((it.get("photo") or {}).get("url")),
                        )
                    )
                except Exception:
                    continue

            self._sleep()

        return items


STOPWORDS_RO = {
    "de", "la", "cu", "si", "în", "in", "pe", "pentru", "un", "o", "din",
    "se", "ca", "sau", "este", "sunt", "nou", "noua", "noi", "buna",
    "bun", "stare", "foarte", "mai", "doar", "cel", "cea", "care",
}


def _extract_keywords(titles: List[str], top_n: int = 15) -> List[str]:
    counter = Counter()
    for title in titles:
        words = re.findall(r"[a-zA-ZăâîșțĂÂÎȘȚ]{3,}", title.lower())
        for w in words:
            if w not in STOPWORDS_RO:
                counter[w] += 1
    return [w for w, _ in counter.most_common(top_n)]


def analyze_trends(query: str, items: List[VintedItem]) -> TrendReport:
    if not items:
        return TrendReport(query=query, sample_size=0)

    prices = [it.price for it in items if it.price and it.price > 0]
    brands = Counter([it.brand for it in items if it.brand])
    titles = [it.title for it in items if it.title]

    return TrendReport(
        query=query,
        sample_size=len(items),
        top_keywords=_extract_keywords(titles),
        top_brands=[b for b, _ in brands.most_common(8)],
        avg_price=round(sum(prices) / len(prices), 2) if prices else 0.0,
        min_price=min(prices) if prices else 0.0,
        max_price=max(prices) if prices else 0.0,
        example_titles=titles[:10],
    )


def get_market_trends(query: str, per_page: int = 40, max_pages: int = 2) -> TrendReport:
    """Functie de conveniență: cauta + analizeaza intr-un singur pas."""
    client = VintedClient()
    items = client.search(query, per_page=per_page, max_pages=max_pages)
    return analyze_trends(query, items)


if __name__ == "__main__":
    # Test rapid manual (necesita conexiune la internet catre vinted.ro)
    report = get_market_trends("geaca de piele barbati")
    print(report)
