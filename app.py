import streamlit as st
from PIL import Image, ImageOps
from rembg import remove
import io
from datetime import datetime

st.set_page_config(page_title="Vinted Pro Lister & Studio", layout="wide", page_icon="👕")

st.title("👕 Vinted Pro Lister & Photo Studio")
st.caption("Procesare foto de studio + generator de titlu, descriere și hashtag-uri pentru Vinted")

# --- FUNCȚII PROCESARE IMAGINE ---
def process_studio_image(uploaded_file, bg_color):
    raw_img = Image.open(uploaded_file)
    raw_img = ImageOps.exif_transpose(raw_img)  # Corectează orientarea dacă e făcută cu telefonul
    
    # Decupare AI cu rembg
    img_byte_arr = io.BytesIO()
    raw_img.save(img_byte_arr, format='PNG')
    cutout = remove(img_byte_arr.getvalue())
    cutout_img = Image.open(io.BytesIO(cutout)).convert("RGBA")
    
    # Creare fundal nou
    background = Image.new("RGBA", cutout_img.size, bg_color)
    combined = Image.alpha_composite(background, cutout_img)
    return combined.convert("RGB")

# --- LOGICĂ HASHTAG-URI SEZONIERE ȘI DE STIL ---
def get_smart_hashtags(clothing_type, style, extra_flair):
    month = datetime.now().month
    seasonal = []
    
    # Sezonalitate automată în funcție de lună
    if month in [12, 1, 2]:
        seasonal = ["#winterwear", "#cozystyle", "#layering", "#coldweather"]
    elif month in [3, 4, 5]:
        seasonal = ["#springfashion", "#springvibes", "#lightlayering", "#freshfit"]
    elif month in [6, 7, 8]:
        seasonal = ["#summerwear", "#festivalstyle", "#summerfit", "#hotweather"]
    else:
        seasonal = ["#autumnvibes", "#fallstyle", "#backtoschool", "#autumnwardrobe"]
        
    style_tags = {
        "Vintage 90s/Y2K": ["#vintage", "#y2k", "#90sfashion", "#retroaesthetic", "#thrifted"],
        "Streetwear / Casual": ["#streetwear", "#casualoutfit", "#oversized", "#urbanstyle"],
        "Sportswear / Bloke": ["#sportswear", "#blokecore", "#footballjersey", "#terracewear", "#retrofootball"],
        "Classic / Elegant": ["#classychic", "#quietluxury", "#officewear", "#minimalist"]
    }
    
    selected_tags = seasonal + style_tags.get(style, ["#streetwear", "#vintagestyle"])
    if clothing_type.lower() in ["tricou", "tricou fotbal"]:
        selected_tags.append("#kit")
    elif clothing_type.lower() in ["hanorac", "hoodie", "geaca"]:
        selected_tags.append("#outerwear")
        
    return " ".join(list(dict.fromkeys(selected_tags))[:10])

# --- INTERFAȚA CU DOUĂ COLOANE ---
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("1. Datele hainei")
    brand = st.text_input("Brand / Marcă", placeholder="ex: Nike, Adidas, Carhartt, Zara")
    item_type = st.text_input("Tip haină", placeholder="ex: Hanorac cu glugă, Geacă vânt, Tricou")
    size = st.text_input("Mărime etichetă (și fit)", placeholder="ex: L (vine lejer ca un XL)")
    condition = st.selectbox(
        "Stare produs", 
        ["Nou cu etichetă", "Foarte bună (fără semne de uzură)", "Bună (urme ușoare normale de purtare)", "Satisfăcătoare (are mici defecte menționate)"]
    )
    details = st.text_area("Măsurători & Defecte", placeholder="ex: Lățime piept: 58 cm, Lungime: 72 cm. Nu are pete sau găuri.")
    style = st.selectbox("Stil / Curent", ["Vintage 90s/Y2K", "Streetwear / Casual", "Sportswear / Bloke", "Classic / Elegant"])

    st.markdown("---")
    st.subheader("2. Poza hainei")
    uploaded_file = st.file_uploader("Încarcă poza făcută pe umeraș / pat", type=["jpg", "jpeg", "png"])
    bg_choice = st.radio("Fundal de studio dorit:", ["Alb Studio (#FFFFFF)", "Gri Deschis (#F2F2F2)", "Bej Neutru (#F7F5F0)"])
    
    color_map = {
        "Alb Studio (#FFFFFF)": (255, 255, 255, 255),
        "Gri Deschis (#F2F2F2)": (242, 242, 242, 255),
        "Bej Neutru (#F7F5F0)": (247, 245, 240, 255)
    }

with col_right:
    st.subheader("3. Rezultat final Vinted")
    
    if uploaded_file is not None:
        with st.spinner("AI-ul curăță poza și aplică fundalul de studio..."):
            processed_image = process_studio_image(uploaded_file, color_map[bg_choice])
            st.image(processed_image, caption="Poză optimizată pentru prima copertă Vinted", use_column_width=True)
            
            # Buton descărcare
            buf = io.BytesIO()
            processed_image.save(buf, format="JPEG", quality=95)
            st.download_button(
                label="Descarcă poza gata de Vinted",
                data=buf.getvalue(),
                file_name="vinted_studio_photo.jpg",
                mime="image/jpeg"
            )
    else:
        st.info("Încarcă o poză în stânga pentru a o transforma automat în poză de studio.")

    # Generare text
    if brand and item_type:
        optimized_title = f"{brand} {item_type} - Mărimea {size} | {style.split('/')[0].strip()}"
        hashtags = get_smart_hashtags(item_type, style, brand)
        
        description_template = f"""{item_type} {brand} în stare excelentă, curat și bine întreținut.

📏 Mărime: {size}
✨ Stare: {condition}
📐 Detalii & Măsurători:
{details if details else "Material calitativ, fără defecte ascunse."}

📦 Livrare rapidă prin Vinted (ambalat corespunzător).
💬 Pentru orice alte detalii sau măsurători suplimentare, răspund rapid la mesaje!

{hashtags}"""

        st.markdown("#### Titlu optimizat SEO (Click pe iconița de copiere)")
        st.code(optimized_title, language="text")
        
        st.markdown("#### Descriere completă structurată")
        st.code(description_template, language="text")
