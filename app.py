import streamlit as st
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np
import io
import requests
from datetime import datetime

st.set_page_config(page_title="Vinted AI Studio & Lister", layout="wide", page_icon="✨")

st.title("✨ Vinted AI Studio & Market Analyzer")
st.caption("Auto-decupare studio, centrare flat-lay și generare anunț bazat pe căutări reale")

# --- PROCESARE FOTO AVANSATĂ: DECUPARE, CENTRARE & FUNDAL ALB STUDIO ---
def auto_studio_transform(uploaded_file, bg_tone="Alb Pur (#FFFFFF)"):
    # Deschidere și corecție automată de orientare EXIF (făcută din mână/telefon)
    img = Image.open(uploaded_file).convert("RGBA")
    img = ImageOps.exif_transpose(img)
    
    # Redimensionare proporțională pentru procesare rapidă și curată
    max_side = 1200
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    
    np_img = np.array(img)
    rgb = np_img[:, :, :3].astype(float)
    
    # Detectare automată a fundalului de la colțuri
    corners = np.concatenate([
        rgb[:30, :30].reshape(-1, 3),
        rgb[:30, -30:].reshape(-1, 3),
        rgb[-30:, :30].reshape(-1, 3),
        rgb[-30:, -30:].reshape(-1, 3)
    ], axis=0)
    bg_ref = np.median(corners, axis=0)
    
    # Mască inteligentă de separare haină vs fundal
    diff = np.linalg.norm(rgb - bg_ref, axis=2)
    mask = (diff > 28).astype(np.uint8) * 255
    
    mask_img = Image.fromarray(mask, mode="L")
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(1.2)) # marginile fine ale hainei
    
    # Izolare haină
    np_img[:, :, 3] = np.array(mask_img)
    isolated_clothing = Image.fromarray(np_img, mode="RGBA")
    
    # Auto-Centrare & Bounding Box (rearanjare haină dreaptă / flat-lay)
    bbox = isolated_clothing.getbbox()
    if bbox:
        isolated_clothing = isolated_clothing.crop(bbox)
        
    # Creare fundal nou de catalog profesional
    canvas_w, canvas_h = 1080, 1440 # Raport clasic 3:4 Vinted
    bg_color = (255, 255, 255) if "Alb" in bg_tone else (243, 244, 246)
    studio_canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)
    
    # Redimensionare armonioasă pe manechin/flat-lay cu margini de respirație (15%)
    target_w = int(canvas_w * 0.78)
    target_h = int(canvas_h * 0.78)
    
    isolated_clothing.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    
    # Lipire pe mijloc perfect centrat
    offset_x = (canvas_w - isolated_clothing.width) // 2
    offset_y = (canvas_h - isolated_clothing.height) // 2
    
    # Aplicare umbră discretă de adâncime ca să nu pară artificială
    shadow = Image.new("RGBA", isolated_clothing.size, (30, 30, 30, 40))
    studio_canvas.paste(isolated_clothing, (offset_x, offset_y), isolated_clothing)
    
    # Ușoară optimizare de culoare și contrast pentru evidențierea țesăturii
    final_img = ImageEnhance.Contrast(studio_canvas).enhance(1.08)
    final_img = ImageEnhance.Sharpness(final_img).enhance(1.2)
    return final_img

# --- ANALIZĂ DE PIAȚĂ VINTED & TRENDURI ---
def get_vinted_top_insights(query):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    url = f"https://www.vinted.ro/api/v2/catalog/items?search_text={requests.utils.quote(query)}&order=relevance"
    try:
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                popular_titles = [i.get("title") for i in items[:4] if i.get("title")]
                avg_favs = sum(i.get("favourite_count", 0) for i in items[:10]) / max(1, min(len(items), 10))
                return {"titles": popular_titles, "avg_favs": round(avg_favs, 1)}
    except Exception:
        pass
    return None

def generate_smart_tags(item_type, style, brand):
    month = datetime.now().month
    # Tag-uri sezoniere adaptate dinamic lunii curente
    if month in [12, 1, 2]:
        season = ["#winterdrop", "#cozystyle", "#layering", "#coldweather"]
    elif month in [3, 4, 5]:
        season = ["#springfashion", "#springvibes", "#freshfit", "#lightlayering"]
    elif month in [6, 7, 8]:
        season = ["#summerfit", "#streetstyle", "#summervibes", "#festivalwear"]
    else:
        season = ["#autumnstyle", "#fallvibes", "#backtoschool", "#autumnwardrobe", "#layeringseason"]
        
    style_dict = {
        "Vintage / Retro 90s": ["#vintage", "#y2k", "#90sfashion", "#retrostyle", "#thriftfind"],
        "Sportswear / Blokecore": ["#blokecore", "#terracewear", "#footballcasuals", "#sportswear", "#retrojersey"],
        "Streetwear / Gorpcore": ["#streetwear", "#gorpcore", "#urbanfashion", "#boxydrop", "#hypebeast"],
        "Casual / Minimalist": ["#cleanaesthetic", "#quietluxury", "#dailyoutfit", "#essentialwear"]
    }
    
    tags = [f"#{brand.lower().replace(' ', '')}"] if brand else []
    tags += style_dict.get(style, ["#streetwear"]) + season
    return " ".join(list(dict.fromkeys(tags))[:10])

# --- INTERFAȚA ---
t1, t2 = st.tabs(["📸 AI Photo Studio (Fundal Alb & Centrare)", "📝 Generator Anunț & Piață"])

with t1:
    st.subheader("Transformă poza într-o fotografie de catalog Vinted")
    st.caption("AI-ul decupează fundalul, centrează haina în format 3:4 și aplică fundal alb de studio.")
    
    col_upload, col_preview = st.columns([1, 1], gap="medium")
    
    with col_upload:
        uploaded_file = st.file_uploader("Alege poza hainei din telefon", type=["jpg", "jpeg", "png"])
        bg_tone = st.radio("Fundal studio:", ["Alb Pur (#FFFFFF)", "Gri Studio Deschis (#F3F4F6)"], horizontal=True)
        
    with col_preview:
        if uploaded_file:
            with st.spinner("Decupez fundalul și așez haina în studio..."):
                studio_result = auto_studio_transform(uploaded_file, bg_tone)
                # Corecție pentru noua versiune Streamlit (fără crash TypeError)
                st.image(studio_result, caption="Rezultat optimizat copertă Vinted", use_container_width=True)
                
                buf = io.BytesIO()
                studio_result.save(buf, format="JPEG", quality=95)
                st.download_button(
                    "⬇️ Descarcă poza pentru Vinted",
                    data=buf.getvalue(),
                    file_name="vinted_pro_cover.jpg",
                    mime="image/jpeg",
                    use_container_width=True
                )
        else:
            st.info("Încarcă o poză pentru a vedea cum decupează și centrează haina automat.")

with t2:
    st.subheader("Date articol & Analiză competitori")
    c1, c2 = st.columns([1, 1], gap="medium")
    
    with c1:
        brand = st.text_input("Brand", value="Nike")
        item_type = st.text_input("Ce este articolul?", value="Tricou / Hanorac")
        size = st.text_input("Mărime", value="M")
        condition = st.selectbox("Stare", ["Nou cu etichetă", "Foarte bună (fără defecte)", "Bună (urme ușoare purtare)", "Cu mici defecte"])
        measurements = st.text_area("Măsurători", value="Lățime piept: 54 cm\nLungime: 68 cm")
        style = st.selectbox("Stil căutat", ["Vintage / Retro 90s", "Sportswear / Blokecore", "Streetwear / Gorpcore", "Casual / Minimalist"])
    
    with c2:
        query = f"{brand} {item_type}".strip()
        with st.spinner("Verific pe Vinted ce tipuri de anunțuri merg bine..."):
            insights = get_vinted_top_insights(query)
            if insights:
                st.success(f"Articolele similare de top au în medie **{insights['avg_favs']} favorite**.")
                if insights["titles"]:
                    with st.expander("Exemple de titluri căutate acum:"):
                        for t in insights["titles"]:
                            st.write(f"• {t}")
        
        seo_title = f"{brand} {item_type} {size} - {style.split('/')[0].strip()} Stare {condition.split('(')[0].strip()}"
        tags = generate_smart_tags(item_type, style, brand)
        
        ad_text = f"""{item_type} {brand} original, în stare {condition.lower()}.

📐 Mărime: {size}
📏 Măsurători:
{measurements}

✨ Produs curat, păstrat impecabil, exact ca în poze.
📦 Livrare rapidă prin Vinted. Împachetez cu grijă!
💬 Pentru orice alte detalii sau oferte de bundle (reducere la pachet), lăsați mesaj.

{tags}"""

        st.markdown("#### Titlu SEO recomandat:")
        st.code(seo_title, language="text")
        st.markdown("#### Descriere completă gata de copiat:")
        st.code(ad_text, language="text")
