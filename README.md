# 💊 Nöbetçi Eczane Bulucu ve Ecza Danışmanı

Türkiye genelindeki 81 il ve tüm ilçeler için **canlı ve resmi nöbetçi eczaneleri** listeleyen, aynı zamanda reçetesiz ilaçlar ve semptomlar konusunda rehberlik eden Streamlit tabanlı yapay zeka destekli web uygulaması.

> [!TIP]
> Bu uygulama **tamamen ücretsiz servislerle** çalışır. Ücretli OpenAI API gerektirmez; **Google Gemini (Ücretsiz Tier)** ve canlı açık nöbetçi eczane veri servisi kullanır.

---

## 🌟 Özellikler

- **🚨 Kesin ve Canlı Nöbetçi Eczane Verisi:** Kapalı, nöbetçi olmayan veya eski eczaneler asla listelenmez; sadece o an aktif olan resmi nöbetçi eczaneler getirilir.
- **📍 Harita ve İletişim:** Listelenen her eczane için açık adres, tıklanabilir doğrudan telefon arama bağlantısı ve canlı Google Haritalar yol tarifi bağlantısı sağlanır.
- **🔍 Akıllı Doğal Dil Arama:** Kullanıcı *"Kadıköy'de eczane"*, *"Ankara nöbetçi"*, *"Beşiktaş açık eczane"* gibi ifadelerle arama yaptığında il ve ilçe otomatik tespit edilir.
- **⚡ Hızlı Arama Paneli:** Sol kenar çubuğundan 81 il seçilerek tek tıkla nöbetçi eczaneler görüntülenebilir.
- **📚 Reçetesiz İlaç ve Semptom Rehberi:** Google Gemini ve FAISS vektör veritabanı ile reçetesiz ilaç kılavuzundan semptomlara yönelik güvenli bilgilendirme.

---

## 🚀 Kurulum ve Çalıştırma

1. **Depoyu klonlayın:**
```bash
git clone https://github.com/BoraKol/nobetci-eczane-bulucu.git
cd nobetci-eczane-bulucu
```

2. **Gerekli bağımlılıkları yükleyin:**
```bash
pip install -r requirements.txt
```

3. **.env dosyasını oluşturun (veya Streamlit Cloud Secrets alanına ekleyin):**
```env
GEMINI_API_KEY=your_free_gemini_api_key
```
*(Google AI Studio üzerinden ücretsiz bir API anahtarı alabilirsiniz)*

4. **Uygulamayı başlatın:**
```bash
streamlit run streamlit_app.py
```
