import os
import streamlit as st
from dotenv import load_dotenv

import google.generativeai as genai
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from duty_pharmacy import (
    get_duty_pharmacies,
    format_duty_pharmacies_for_llm,
    extract_pharmacy_intent,
    TURKISH_CITIES
)

load_dotenv()

# API Anahtarı: Önce .env, sonra Streamlit Cloud secrets
gemini_key = os.getenv("GEMINI_API_KEY")
if not gemini_key:
    try:
        gemini_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        gemini_key = None

if gemini_key:
    genai.configure(api_key=gemini_key)

st.set_page_config(
    page_title="Ecza ve Nöbetçi Eczane Danışmanı",
    page_icon="💊",
    layout="wide"
)

# --- ÜCRETSİZ GEMINI EMBEDDING WRAPPER ---
class GeminiEmbeddings(Embeddings):
    def __init__(self, api_key: str, model: str = "models/gemini-embedding-001"):
        genai.configure(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Toplu embedding çağrısı
        results = []
        for text in texts:
            try:
                res = genai.embed_content(model=self.model, content=text)
                results.append(res['embedding'])
            except Exception as e:
                print(f"Embedding hatası: {e}")
                results.append([0.0] * 3072)
        return results

    def embed_query(self, text: str) -> list[float]:
        try:
            res = genai.embed_content(model=self.model, content=text)
            return res['embedding']
        except Exception as e:
            print(f"Query embedding hatası: {e}")
            return [0.0] * 3072

# --- CACHED RESOURCES ---
@st.cache_resource(show_spinner="Reçetesiz ilaç veritabanı yükleniyor...")
def load_vector_db(api_key: str):
    """PDF dosyasını yükleyip ücretsiz Gemini Embedding ile FAISS veritabanını önbelleğe alır."""
    pdf_path = "recetesiz_ilac_listesi.pdf"
    if not os.path.exists(pdf_path) or not api_key:
        return None
    try:
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = splitter.split_documents(documents)
        embeddings = GeminiEmbeddings(api_key=api_key)
        return FAISS.from_documents(docs, embeddings)
    except Exception as e:
        print(f"Vektör veritabanı oluşturma hatası: {e}")
        return None

# --- SIDEBAR: HIZLI NÖBETÇİ ECZANE PANELİ ---
with st.sidebar:
    st.header("🚨 Canlı Nöbetçi Eczane Sorgula")
    st.caption("Ücretsiz ve canlı veri: Ne olursa olsun **sadece ve sadece şu an açık olan nöbetçi eczaneler** listelenir.")
    
    selected_city = st.selectbox(
        "İl Seçin:",
        options=[""] + TURKISH_CITIES,
        index=0,
        help="Nöbetçi eczanelerini görmek istediğiniz şehri seçin."
    )
    
    district_input = st.text_input(
        "İlçe (İsteğe bağlı):",
        placeholder="Örn: Kadıköy, Çankaya, Konak"
    )
    
    search_duty_btn = st.button("🔍 Nöbetçi Eczaneleri Getir", use_container_width=True)
    
    if search_duty_btn and selected_city:
        with st.spinner(f"{selected_city} nöbetçi eczaneleri çekiliyor..."):
            duty_res = get_duty_pharmacies(selected_city, district_input, limit=10)
            if duty_res.get("success"):
                st.success(f"✅ {duty_res.get('count')} aktif nöbetçi eczane bulundu.")
                for p in duty_res.get("pharmacies", []):
                    with st.expander(f"🏥 {p['name']} ({p.get('district', '')})", expanded=True):
                        st.markdown(f"**📍 Adres:** {p['address']}")
                        clean_phone = p['phone'].replace(' ', '')
                        st.markdown(f"**📞 Tel:** [{p['phone']}](tel:{clean_phone})")
                        st.markdown(f"[🗺️ Google Haritalar'da Yol Tarifi]({p['maps_url']})")
            else:
                st.warning(duty_res.get("message", "Nöbetçi eczane bulunamadı."))
    elif search_duty_btn and not selected_city:
        st.error("Lütfen bir il seçin.")

    st.divider()
    st.info("💡 **Bilgi:** Sohbet penceresinden de 'Kadıköy'de eczane', 'Ankara nöbetçi eczaneler' veya 'İzmir'de açık eczane var mı' şeklinde doğrudan sorabilirsiniz.")

# --- MAIN PAGE HEADER ---
st.title("💊 İlaç ve Nöbetçi Eczane Danışmanı")
st.write("Şikayetinizi belirtin, reçetesiz ilaç tavsiyesi alın veya bulunduğunuz şehri yazarak **yalnızca o an açık olan güncel NÖBETÇİ eczaneleri** anında listeleyin. *(Tamamen Ücretsiz API - Google Gemini & Canlı Eczane Servisi)*")

# Vektör veritabanını yükle
vector_db = load_vector_db(gemini_key) if gemini_key else None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- SOHBET ARAYÜZÜ (2 SÜTUN) ---
col1, col2 = st.columns([1, 2])

with col1:
    user_question = st.text_input(
        "👤 Şikayetinizi veya aradığınız şehri yazın:",
        placeholder="Örn: Kadıköy'de nöbetçi eczane veya Başım ağrıyor"
    )
    send_btn = st.button("Gönder", use_container_width=True)

    if send_btn and user_question:
        user_question = user_question.strip()
        answer = ""

        # 1. ÖNCELİK: Eczane ve nöbetçi eczane araması tespiti
        # Katı Kural: Kullanıcı eczane veya açık yer sorduğunda NE OLURSA OLSUN sadece nöbetçi eczaneler listelenir.
        intent = extract_pharmacy_intent(user_question)

        if intent["is_pharmacy_query"]:
            city = intent.get("city")
            district = intent.get("district")

            if city:
                duty_data = get_duty_pharmacies(city, district, limit=8)
                answer = format_duty_pharmacies_for_llm(duty_data)
            else:
                answer = (
                    "🚨 Nöbetçi eczaneleri listeleyebilmem için lütfen hangi şehirde (ve varsa ilçede) olduğunuzu belirtin.\n\n"
                    "*(Örnek: **'İstanbul Kadıköy'de eczane'**, **'Ankara Çankaya nöbetçi eczane'**, **'İzmir nöbetçi eczaneler'**)*\n\n"
                    "⚠️ **Önemli Kural:** Ne olursa olsun sistemimiz kapalı veya nöbetçi olmayan hiçbir eczaneyi listelemez; sadece şu an açık olan resmi nöbetçi eczaneleri getirir."
                )
        else:
            # 2. Semptom / Reçetesiz İlaç Rehberi Sorgusu (Ücretsiz Google Gemini ile)
            if not gemini_key:
                answer = (
                    "⚠️ Reçetesiz ilaç danışmanlığı için `GEMINI_API_KEY` gereklidir. "
                    "Google AI Studio üzerinden ücretsiz bir API anahtarı alıp `.env` veya Streamlit Cloud Secrets alanına ekleyebilirsiniz. "
                    "\n\nNöbetçi eczane arama sistemi API anahtarı gerektirmeden çalışmaktadır! Bir il/ilçe yazarak nöbetçi eczaneleri sorgulayabilirsiniz."
                )
            else:
                try:
                    # Benzer belgeleri FAISS'ten çek
                    context = ""
                    if vector_db:
                        relevant_docs = vector_db.similarity_search(user_question, k=3)
                        context = "\n---\n".join([d.page_content for d in relevant_docs])

                    # Gemini Modeli ile yanıt üret
                    model = genai.GenerativeModel("gemini-flash-latest")
                    prompt = f"""Sen Türkçe hizmet veren uzman bir Ecza ve Sağlık Danışmanı AI asistanısın.
Aşağıda reçetesiz ilaç kılavuzundan alınan resmi bilgiler yer almaktadır:
-------------------
{context}
-------------------

Kullanıcı Sorusu/Şikayeti: {user_question}

Yönergeler:
1. Reçetesiz ilaç kılavuzundaki bilgilere dayanarak kullanıcının şikayetine uygun reçetesiz ilaç önerileri, kullanım talimatı ve uyarıları açıkla.
2. Ciddi durumlarda mutlaka hekime veya en yakın nöbetçi eczacıya başvurulması gerektiğini hatırlat.
3. Asla kendi hafızandan rastgele eczane ismi uydurma.
4. Yanıtını anlaşılır, sıcak ve profesyonel Türkçe ile yaz."""

                    response = model.generate_content(prompt)
                    answer = response.text if response and response.text else "Yanıt alınamadı."
                except Exception as e:
                    answer = f"Yanıt oluşturulurken bir hata meydana geldi: {str(e)}"

        st.session_state.chat_history.append(("👤", user_question))
        st.session_state.chat_history.append(("🤖", answer))

with col2:
    if st.session_state.chat_history:
        st.subheader("🗨️ Sohbet Geçmişi")

        if st.button("🧹 Sohbeti Temizle"):
            st.session_state.chat_history = []
            st.rerun()

        for role, content in st.session_state.chat_history:
            if role == "👤":
                st.markdown(f"**👤 Kullanıcı:** {content}")
            elif role == "🤖":
                st.markdown(f"**🤖 Asistan:**\n\n{content}")
            st.markdown("---")