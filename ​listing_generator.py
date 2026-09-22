"""
listing_generator.py
---------------------
Genereaza titlu si descriere pentru un anunt Vinted, pe baza:
  - informatiilor pe care le da utilizatorul despre articolul propriu
  - tendintelor extrase de pe piata (vinted_scraper.TrendReport)

Nu foloseste AI generativ extern by default (functioneaza offline, pe baza de
template-uri + cuvinte cheie), ca sa nu fie nevoie de un API key. Daca vrei,
poti conecta ulterior un LLM (ex. Claude API) inlocuind functia
`build_description` cu un apel catre API, folosind exact aceleasi date de
intrare (item_info + trends).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List

from vinted_scraper import TrendReport


@dataclass
class ItemInfo:
    category: str            # ex: "geaca de piele"
    brand: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    condition: str = "foarte buna"   # noua cu eticheta / ca noua / foarte buna / buna
    material: Optional[str] = None
    gender: Optional[str] = None     # barbati / femei / unisex / copii
    extra_notes: Optional[str] = None
    price_hint: Optional[float] = None


def build_title(item: ItemInfo, trends: Optional[TrendReport] = None) -> str:
    """Construieste un titlu in stilul celor populare pe Vinted:
    Brand + Categorie + Culoare + Marime (ordinea care apare cel mai des la
    anunturile cu succes)."""
    parts: List[str] = []

    if item.brand:
        parts.append(item.brand)

    parts.append(item.category.capitalize())

    if item.color:
        parts.append(item.color.capitalize())

    if item.gender:
        parts.append(item.gender)

    if item.size:
        parts.append(f"mărime {item.size}")

    title = " ".join(parts)

    # Adauga un cuvant cheie popular din piata, daca nu e deja in titlu si daca
    # incape (Vinted limiteaza titlul, de regula ~70-80 caractere)
    if trends and trends.top_keywords:
        for kw in trends.top_keywords:
            if kw.lower() not in title.lower() and len(title) + len(kw) + 1 <= 75:
                title = f"{title} {kw}"
                break

    return title.strip()


def build_description(item: ItemInfo, trends: Optional[TrendReport] = None) -> str:
    """Construieste o descriere structurata, in stilul anunturilor cu
    conversie buna: stare, material, detalii, masuri, cuvinte cheie, hashtag-uri."""

    lines: List[str] = []

    intro_bits = []
    if item.brand:
        intro_bits.append(item.brand)
    intro_bits.append(item.category)
    if item.color:
        intro_bits.append(f"culoare {item.color}")
    lines.append(" ".join(intro_bits).strip().capitalize() + ".")

    lines.append(f"Stare: {item.condition}.")

    if item.material:
        lines.append(f"Material: {item.material}.")

    if item.size:
        lines.append(f"Mărime: {item.size} (recomand verificarea măsurilor la solicitare).")

    if item.extra_notes:
        lines.append(item.extra_notes.strip())

    if trends and trends.avg_price:
        lines.append(
            f"Pentru referință, articole similare pe piață se vând în medie cu "
            f"{trends.avg_price:.0f} RON (interval {trends.min_price:.0f}-{trends.max_price:.0f} RON)."
        )

    lines.append("Trimit rapid, împachetat cu grijă. Întrebări - scrieți-mi cu drag!")

    if trends and trends.top_keywords:
        hashtags = " ".join(f"#{kw}" for kw in trends.top_keywords[:6])
        lines.append(hashtags)

    return "\n".join(lines)


def suggest_price(item: ItemInfo, trends: Optional[TrendReport]) -> Optional[float]:
    """Sugestie simpla de pret pe baza mediei de piata, ajustata usor pe baza
    starii articolului."""
    if not trends or not trends.avg_price:
        return item.price_hint

    condition_multiplier = {
        "noua cu eticheta": 1.15,
        "ca noua": 1.05,
        "foarte buna": 1.0,
        "buna": 0.85,
        "satisfacatoare": 0.65,
    }
    mult = condition_multiplier.get(item.condition.lower(), 1.0)
    return round(trends.avg_price * mult, 2)


def generate_listing(item: ItemInfo, trends: Optional[TrendReport] = None) -> dict:
    return {
        "title": build_title(item, trends),
        "description": build_description(item, trends),
        "suggested_price": suggest_price(item, trends),
    }


if __name__ == "__main__":
    demo_item = ItemInfo(
        category="geaca de piele",
        brand="Zara",
        color="negru",
        size="M",
        condition="foarte buna",
        material="piele ecologica",
        gender="barbati",
    )
    print(generate_listing(demo_item))
