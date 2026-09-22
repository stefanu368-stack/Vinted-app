"""
image_studio.py
-----------------
Transforma o poza "de acasa" a unui articol de haine intr-o poza cu aspect
mult mai apropiat de "studio foto":
  1. corectie automata de luminozitate/contrast
  2. eliminare fundal (metoda GrabCut din OpenCV - functioneaza local, fara
     sa descarce niciun model, deci e robusta si nu are nevoie de internet)
  3. indreptare + incadrare (crop) pe articolul detectat
  4. plasare pe fundal alb/gri neutru, centrat, cu umbra usoara, la o
     rezolutie/proportie standard de tip e-commerce

LIMITARE IMPORTANTA:
Acest modul NU poate "repozitiona" haina in mod magic (ex. sa transforme o
poza cu haina pusa pe pat intr-o poza ca pe manechin, sau sa schimbe unghiul
din care a fost facuta poza). Asta ar necesita AI generativ (inpainting /
image-to-image), nu procesare clasica de imagine. Ce face acest modul:
indreapta, centreaza, incadreaza corect si pune pe fundal neutru - lucruri
care, in practica, duc la 80% din diferenta vizuala a unei poze "de studio".

Daca vrei si pasul de AI generativ (schimbare reala de fundal cu textura,
umbre realiste, re-generare de unghi), spune-mi si iti adaug un modul
separat care apeleaza un API de generare de imagini (necesita cheie API si
cost per imagine).
"""

from __future__ import annotations
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from PIL import Image


# ---------- 1. Luminozitate / contrast ----------

def auto_brightness_contrast(img_bgr: np.ndarray, clip_hist_percent: float = 1.0) -> np.ndarray:
    """Corectie automata de contrast/luminozitate folosind stretching pe
    histograma canalului de luminanta (similar cu 'auto levels')."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist_size = len(hist)

    accumulator = np.cumsum(hist)
    maximum = accumulator[-1]
    clip_hist_percent *= (maximum / 100.0)
    clip_hist_percent /= 2.0

    minimum_gray = 0
    while accumulator[minimum_gray] < clip_hist_percent:
        minimum_gray += 1

    maximum_gray = hist_size - 1
    while accumulator[maximum_gray] >= (maximum - clip_hist_percent):
        maximum_gray -= 1

    if maximum_gray <= minimum_gray:
        return img_bgr  # imagine deja plata / fara variatie, nu mai atingem

    alpha = 255.0 / (maximum_gray - minimum_gray)
    beta = -minimum_gray * alpha

    result = cv2.convertScaleAbs(img_bgr, alpha=alpha, beta=beta)

    # usoara egalizare pe canalul L din LAB pentru "pop" fara sa suprasatureze
    lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b))
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return result


# ---------- 2. Eliminare fundal ----------

def remove_background_grabcut(img_bgr: np.ndarray, margin: int = 20) -> Tuple[np.ndarray, np.ndarray]:
    """Elimina fundalul folosind GrabCut, initializat cu un rectangle care
    presupune ca articolul e in centrul pozei (functioneaza bine pentru poze
    tip 'haina fotografiata pe fundal simplu / pat / suprafata neutra').

    Returneaza (imagine_bgr_cu_fundal_transparent_ca_alpha, masca_alpha)."""
    h, w = img_bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)

    rect = (margin, margin, w - 2 * margin, h - 2 * margin)

    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(img_bgr, mask, rect, bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        # daca imaginea e prea mica sau grabcut nu poate converge, renuntam
        # la eliminarea fundalului si returnam alpha = 255 peste tot
        alpha = np.full((h, w), 255, dtype=np.uint8)
        return img_bgr, alpha

    alpha_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")

    # curatare morfologica: inlaturam zgomot mic si umplem gauri mici
    kernel = np.ones((5, 5), np.uint8)
    alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    alpha_mask = cv2.morphologyEx(alpha_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # usoara estompare a marginii ca sa nu para "decupat cu foarfeca"
    alpha_mask = cv2.GaussianBlur(alpha_mask, (5, 5), 0)

    return img_bgr, alpha_mask


# ---------- 3. Indreptare + incadrare ----------

def straighten_and_crop(img_bgr: np.ndarray, alpha_mask: np.ndarray, pad_ratio: float = 0.08):
    """Gaseste conturul principal (articolul), il indreapta daca e inclinat
    si decupeaza cu un mic padding in jurul lui."""
    contours, _ = cv2.findContours(alpha_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return img_bgr, alpha_mask

    largest = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(largest)
    (cx, cy), (rw, rh), angle = rect

    # normalizam unghiul (evitam rotatii de 90 grade nedorite pe obiecte late)
    if rw < rh:
        angle += 90

    h, w = img_bgr.shape[:2]
    rot_mat = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)

    rotated_img = cv2.warpAffine(
        img_bgr, rot_mat, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    rotated_alpha = cv2.warpAffine(
        alpha_mask, rot_mat, (w, h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )

    # recalculam bounding box pe masca rotita
    ys, xs = np.where(rotated_alpha > 30)
    if len(xs) == 0 or len(ys) == 0:
        return rotated_img, rotated_alpha

    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    pad_x = int((x1 - x0) * pad_ratio)
    pad_y = int((y1 - y0) * pad_ratio)

    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(w, x1 + pad_x)
    y1 = min(h, y1 + pad_y)

    cropped_img = rotated_img[y0:y1, x0:x1]
    cropped_alpha = rotated_alpha[y0:y1, x0:x1]

    return cropped_img, cropped_alpha


# ---------- 4. Plasare pe fundal "studio" ----------

def place_on_studio_background(
    img_bgr: np.ndarray,
    alpha_mask: np.ndarray,
    canvas_size: Tuple[int, int] = (1200, 1500),
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    add_shadow: bool = True,
) -> Image.Image:
    """Centreaza articolul (cu fundal transparent) pe un canvas nou, de
    dimensiune standard tip listare online, cu fundal uniform si o umbra
    usoara dedesubt pentru aspect de studio."""

    canvas_w, canvas_h = canvas_size
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)

    # convertim img+alpha in PIL RGBA
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    rgba = np.dstack([rgb, alpha_mask])
    item_img = Image.fromarray(rgba, mode="RGBA")

    # redimensionam articolul sa ocupe ~75% din inaltimea canvasului, pastrand proportiile
    max_h = int(canvas_h * 0.75)
    max_w = int(canvas_w * 0.85)
    scale = min(max_h / item_img.height, max_w / item_img.width)
    new_size = (int(item_img.width * scale), int(item_img.height * scale))
    item_img = item_img.resize(new_size, Image.LANCZOS)

    paste_x = (canvas_w - item_img.width) // 2
    paste_y = (canvas_h - item_img.height) // 2

    if add_shadow:
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shadow_alpha = item_img.split()[-1].point(lambda p: min(p, 60))
        shadow_layer = Image.new("RGBA", item_img.size, (0, 0, 0, 0))
        shadow_layer.putalpha(shadow_alpha)
        shadow.paste(shadow_layer, (paste_x + 8, paste_y + 14), shadow_layer)
        shadow = shadow.filter_placeholder = shadow  # no-op keep readable
        canvas = canvas.convert("RGBA")
        canvas.alpha_composite(shadow)
        canvas = canvas.convert("RGB")

    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(item_img, (paste_x, paste_y))
    return canvas.convert("RGB")


# ---------- Pipeline complet ----------

def enhance_photo(input_path: str, output_path: str, bg_color=(255, 255, 255)) -> str:
    """Ruleaza pipeline-ul complet pe o singura poza si salveaza rezultatul."""
    img_bgr = cv2.imread(input_path)
    if img_bgr is None:
        raise ValueError(f"Nu am putut citi imaginea: {input_path}")

    img_bgr = auto_brightness_contrast(img_bgr)
    img_bgr, alpha_mask = remove_background_grabcut(img_bgr)
    img_bgr, alpha_mask = straighten_and_crop(img_bgr, alpha_mask)
    final_img = place_on_studio_background(img_bgr, alpha_mask, bg_color=bg_color)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final_img.save(output_path, quality=95)
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Utilizare: python image_studio.py input.jpg output.jpg")
    else:
        out = enhance_photo(sys.argv[1], sys.argv[2])
        print(f"Salvat: {out}")
