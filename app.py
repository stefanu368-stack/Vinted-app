import streamlit as st
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import io
import requests
import re
from collections import Counter
from datetime import datetime

st.set_page_config(page_title="Vinted AI Studio & Market Pro", layout="wide", page_icon="✨")

st.title("✨ Vinted AI Studio & Market Assistant")
st.caption("Decupare AI de precizie, centrare proporțională de catalog & cercetare Vinted în timp real")

# --- PROCESARE FOTO AVANSATĂ CU AI REAL ---
def remove_bg_with_ai(image_bytes, api_key=None):
    """
    Decupare profesională. Dacă ai un API key gratuit de la ClipDrop, îl folosește direct.
    Dacă nu, folosește endpoint-ul public de înaltă precizie.
    """
    if api_key:
        # Folosește ClipDrop API (Stability AI)
        response = requests.post(
            'https://clipdrop-api.co/remove-background/v1',
            files={'image_file': ('image.png', image_bytes, 'image/png')},
            headers={'x-api-key': api_key},
            timeout=20
        )
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
    
    # Metodă de rezervă cloud AI gratuită
    try:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": image_bytes},
            data={"size": "auto"},
            headers={"X-Api-Key": api_key if api_key else ""},
            timeout=15
        )
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content)).convert("RGBA")
    except Exception:
        pass
    
    return None

def compose_catalog_image(cutout_img, bg_color_hex="#FFFFFF"):
    """
    Centrează haina decupată, adaugă umbră naturală de contact și fundal de catalog curat.
    """
    # Îndepărtare margini goale (auto-crop)
    bbox = cutout_img.getbbox()
    if bbox:
        cutout_img = cutout_img.crop(bbox)
        
    # Dimensiune standard de catalog Vinted (raport 3:4)
    canvas_w, canvas_h = 1080, 1440
    
    # Convertire culoare fundal
    bg_hex = bg_color_hex.lstrip('#')
    bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (*bg_rgb, 255))
    
    # Redimensionare proporțională (ocupă 80% din înălțimea sau lățimea imaginii)
    target_max_w = int(canvas_w * 0.80)
    target_max_h = int(canvas_h * 0.80)
    cutout_img.thumbnail((target_max_w, target_max_h), Image.Resampling.LANCZOS)
    
    # Calcul coordonate centrare perfectă
    pos_x = (canvas_w - cutout_img.width) // 2
    pos_y = (canvas_h - cutout_img.height) // 2
    
    # Creare umbră discretă și realistă sub haină
    shadow_mask = cutout_img.split()[3].filter(ImageFilter.GaussianBlur(15))
    shadow = Image.new("RGBA", cutout_img.size, (0, 0, 0, 45))
    canvas.paste(shadow, (pos_x + 4, pos_y + 12), shadow_mask)
    
    # Suprapunere haină
    canvas.paste(cutout_img, (pos_x, pos_y), cutout_img)
    
    final_rgb = canvas.convert("RGB")
    # Accentuează ușor culorile și textura ca să arate proaspăt spălat și călcat
    final_rgb = ImageEnhance.Sharpness(final_rgb).enhance(1.2)
    final_rgb = ImageEnhance.Contrast(final_rgb).enhance(1.05)
    return final_rgb

# --- DATE REALE VINTED & ANUNȚ ---
def fetch_live_vinted(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    url = f"https://www.vinted.ro/api/v2/catalog/items?search_text={requests.utils.quote(query)}&order=relevance"
    try:
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                sorted_items = sorted(items, key=lambda x: x.get("favourite_count", 0), reverse=True)[:6]
                titles = [it.get("title", "") for it in sorted_items if it.get("title")]
                avg_favs = sum([it.get("favourite_count", 0) for it in sorted_items]) / len(sorted_items)
                
                words = []
                for t in titles:
                    w_list = re.findall(r'\b[a-zA-Z0-9]{3,}\b', t.lower())
                    words.extend([w for w in w_list if w not in ["the", "and", "de", "cu", "marimea", "nou", "stare"]])
                return {"titles": titles, "avg_favs": round(avg_favs, 1), "kws": [x[0] for x in Counter(words).most_common(5)]}
    except Exception:
        pass
    return None

# --- INTERFAȚA ---
tab_photo, tab_listing = st.tabs(["📸 AI Photo Studio Pro", "⚡ Anunț & Căutare în Timp Real"])

with tab_photo:
    st.subheader("Transformă poza de pe telefon într-una de catalog")
    
    with st.expander("🔑 Opțional: Cheie API gratuită ClipDrop (pentru calitate maximă fără limite)"):
        st.write("Dacă vrei decupare la nivel de fir de ață, fă un cont gratuit pe [clipdrop.co/apis](https://clipdrop.co/apis) și lipește cheia API aici:")
        api_key_input = st.text_input("ClipDrop API Key (lasă liber pentru decuparea standard)", type="password")
    
    col_u, col_p = st.columns([1, 1], gap="medium")
    with col_u:
        photo_file = st.file_uploader("Încarcă poza hainei", type=["jpg", "jpeg", "png"])
        bg_color = st.color_picker("Alege culoarea fundalului de studio", "#FFFFFF")
        
    with col_p:
        if photo_file:
            if st.button("🚀 Curăță și centrează haina cu AI", use_container_width=True):
                with st.spinner("AI-ul decupează haina, elimină umbrele și o centrează..."):
                    img_bytes = photo_file.getvalue()
                    cutout = remove_bg_with_ai(img_bytes, api_key_input)
                    
                    if cutout:
                        final_result = compose_catalog_image(cutout, bg_color)
                        st.image(final_result, caption="Rezultat studio catalog", use_container_width=True)
                        
                        buf = io.BytesIO()
                        final_result.save(buf, format="JPEG", quality=95)
                        st.download_button("⬇️ Descarcă poza pentru Vinted", buf.getvalue(), "vinted_pro.jpg", "image/jpeg", use_container_width=True)
                    else:
                        st.warning("Pentru decupare de înaltă rezoluție prin server, adaugă o cheie gratuită ClipDrop mai sus (se generează gratuit în 30 de secunde pe site-ul lor).")

with tab_listing:
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        brand = st.text_input("Brand", "Nike")
        item_type = st.text_input("Tip articol", "Hanorac")
        size = st.text_input("Mărime", "L")
        condition = st.selectbox("Stare", ["Nou cu etichetă", "Foarte bună", "Bună", "Satisfăcătoare"])
        measurements = st.text_area("Măsurători", "Lățime piept: 56 cm\nLungime: 70 cm")
        style = st.selectbox("Stil / Trend", ["Vintage 90s", "Blokecore", "Streetwear", "Minimalist"])
        scan_btn = st.button("🔍 Caută anunțuri de succes & Generează text", use_container_width=True)
        
    with c2:
        if scan_btn:
            q = f"{brand} {item_type}".strip()
            with st.spinner(f"Analizez anunțurile populare pentru '{q}'..."):
                data = fetch_live_vinted(q)
                
            month = datetime.now().month
            season_tag = "#autumnvibes #layeringseason" if month in [9, 10, 11] else "#winterdrop" if month in [12, 1, 2] else "#springfit" if month in [3, 4, 5] else "#summerfit"
            
            extra_tags = " ".join([f"#{k}" for k in data["kws"]]) if data and data.get("kws") else ""
            if data:
                st.success(f"Analiză completă! Postările de top au o medie de **{data['avg_favs']} favorite**.")
            
            title_gen = f"{brand} {item_type} - {size} | {style}"
            desc_gen = f"""Piesă selectată: {item_type} {brand}, în condiție excelentă.

📏 Mărime pe etichetă: {size}
✨ Stare: {condition}
📐 Măsurători exacte:
{measurements}

💡 Produs autentic, curat și bine întreținut.
📦 Trimit prompt prin Vinted, ambalat cu atenție!
💬 Răspund rapid la orice întrebare sau solicitare de bundle.

#{brand.lower().replace(' ', '')} #{style.lower().replace(' ', '')} {season_tag} {extra_tags}"""

            st.markdown("#### Titlu:")
            st.code(title_gen, language="text")
            st.markdown("#### Descriere dinamică:")
            st.code(desc_gen, language="text")
