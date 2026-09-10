import os
import streamlit as st
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

try:
    from langchain_core.messages import AIMessage, HumanMessage
except ImportError:
    from langchain.schema import AIMessage, HumanMessage

from duty_pharmacy import (
    get_duty_pharmacies,
    format_duty_pharmacies_for_llm,
    extract_pharmacy_intent,
    TURKISH_CITIES
)

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Streamlit Cloud secrets kontrolü
if not api_key:
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        api_key = None

if api_key:
    os.environ["OPENAI_API_KEY"] = api_key

st.set_page_config(
    page_title="Ecza ve Nöbetçi Eczane Danışmanı",
    page_icon="💊",
    layout="wide"
)

# --- CACHED RESOURCES ---
@st.cache_resource(show_spinner="Reçetesiz ilaç veritabanı yükleniyor...")
def load_vector_db():
    """PDF dosyasını sadece 1 defa yükleyip vektör veritabanını önbelleğe alır."""
    pdf_path = "recetesiz_ilac_listesi.pdf"
    if not os.path.exists(pdf_path) or not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        docs = splitter.split_documents(documents)
        embedding = OpenAIEmbeddings(model="text-embedding-3-large")
        return FAISS.from_documents(docs, embedding)
    except Exception as e:
        # OpenAI quota aşımı veya bağlantı hatası durumunda uygulamanın çökmesini engeller
        print(f"Vektör veritabanı yükleme hatası: {e}")
        return None

# --- SIDEBAR: HIZLI NÖBETÇİ ECZANE PANELİ ---
with st.sidebar:
    st.header("🚨 Canlı Nöbetçi Eczane Sorgula")
    st.caption("Ne olursa olsun **sadece ve sadece şu an açık olan nöbetçi eczaneler** listelenir. Kapalı hiçbir eczane gösterilmez.")
    
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
st.write("Şikayetinizi belirtin, reçetesiz ilaç tavsiyesi alın veya bulunduğunuz şehri yazarak **yalnızca o an açık olan güncel NÖBETÇİ eczaneleri** anında listeleyin.")

# Vector DB & QA Chain setup
vector_db = load_vector_db()

if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )

if "qa_chain" not in st.session_state and vector_db is not None:
    try:
        llm = ChatOpenAI(
            model_name="gpt-4o-mini",
            temperature=0.1
        )
        st.session_state.qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vector_db.as_retriever(search_kwargs={"k": 3}),
            memory=st.session_state.memory
        )
    except Exception as e:
        st.session_state.qa_chain = None
        print(f"QA Chain başlatma hatası: {e}")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- SOHBET ARAYÜZÜ (2 SÜTUN) ---
col1, col2 = st.columns([1, 2])

with col1:
    user_question = st.text_input("👤 Şikayetinizi veya aradığınız şehri yazın:", placeholder="Örn: Kadıköy'de nöbetçi eczane veya Başım ağrıyor")
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
            # 2. Semptom / Reçetesiz İlaç Rehberi Sorgusu
            if "qa_chain" in st.session_state and st.session_state.qa_chain is not None:
                try:
                    response = st.session_state.qa_chain.invoke(user_question)
                    answer = response.get("answer", "Yanıt alınamadı.")
                except Exception as e:
                    err_msg = str(e)
                    if "insufficient_quota" in err_msg or "429" in err_msg:
                        answer = (
                            "⚠️ **OpenAI API Kotası Uyarısı:** OpenAI API hesabınızın kullanım kotası dolmuş görünüyor. "
                            "Ancak nöbetçi eczane sorgulama sistemimiz canlı ve kesintisiz çalışmaktadır! "
                            "İl veya ilçe adını yazarak (örn: *İstanbul Kadıköy*, *Ankara*) açık nöbetçi eczaneleri sorgulayabilirsiniz."
                        )
                    else:
                        answer = f"Yanıt oluşturulurken bir hata meydana geldi: {err_msg}"
            else:
                answer = (
                    "Reçetesiz ilaç veritabanı şu an çevrimdışı. "
                    "Ancak nöbetçi eczane arama sistemimiz aktiftir. Nöbetçi eczane öğrenmek istediğiniz ili yazabilirsiniz."
                )

        st.session_state.chat_history.append(("👤", user_question))
        st.session_state.chat_history.append(("🤖", answer))

with col2:
    if st.session_state.chat_history:
        st.subheader("🗨️ Sohbet Geçmişi")

        if st.button("🧹 Sohbeti Temizle"):
            st.session_state.chat_history = []
            if "memory" in st.session_state and st.session_state.memory is not None:
                st.session_state.memory.clear()
            st.rerun()

        for role, content in st.session_state.chat_history:
            if role == "👤":
                st.markdown(f"**👤 Kullanıcı:** {content}")
            elif role == "🤖":
                st.markdown(f"**🤖 Asistan:**\n\n{content}")
            st.markdown("---")

# NOT: Sadece reçetesiz ilaç/semptom ve doğrulanmış nöbetçi eczane bilgileri sunulur.