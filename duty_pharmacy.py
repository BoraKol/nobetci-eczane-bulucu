import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Türkiye 81 İl Listesi
TURKISH_CITIES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın",
    "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı",
    "Çorum", "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir",
    "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Isparta", "Mersin", "İstanbul",
    "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli", "Konya",
    "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir",
    "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ",
    "Tokat", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak",
    "Aksaray", "Bayburt", "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan",
    "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce"
]

# Popüler ilçe -> il eşleştirmesi (kullanıcı sadece ilçe yazarsa ili otomatik bulur)
POPULAR_DISTRICT_TO_CITY = {
    # İstanbul
    "kadikoy": "İstanbul", "besiktas": "İstanbul", "uskudar": "İstanbul", "sisli": "İstanbul",
    "bakirkoy": "İstanbul", "beyoglu": "İstanbul", "fatih": "İstanbul", "maltepe": "İstanbul",
    "atasehir": "İstanbul", "kartal": "İstanbul", "pendik": "İstanbul", "sariyer": "İstanbul",
    "beylikduzu": "İstanbul", "esenyurt": "İstanbul", "umraniye": "İstanbul", "bagcilar": "İstanbul",
    "bahcelievler": "İstanbul", "zeytinburnu": "İstanbul", "gaziosmanpasa": "İstanbul",
    "sultangazi": "İstanbul", "basaksehir": "İstanbul", "sancaktepe": "İstanbul", "tuzla": "İstanbul",
    "cekmekoy": "İstanbul", "buyukcekmece": "İstanbul", "kucukcekmece": "İstanbul", "silivri": "İstanbul",
    "eyup": "İstanbul", "eyupsultan": "İstanbul", "kagithane": "İstanbul", "avcilar": "İstanbul",
    "gungoren": "İstanbul", "bayrampasa": "İstanbul", "esenler": "İstanbul", "arnavutkoy": "İstanbul",
    "beykoz": "İstanbul", "sultanbeyli": "İstanbul", "adalar": "İstanbul", "sile": "İstanbul",
    # Ankara
    "cankaya": "Ankara", "kecioren": "Ankara", "yenimahalle": "Ankara", "mamak": "Ankara",
    "etimesgut": "Ankara", "sincan": "Ankara", "altindag": "Ankara", "pursaklar": "Ankara",
    "golbasi": "Ankara", "polatli": "Ankara", "cubuk": "Ankara", "kahramankazan": "Ankara",
    "kazan": "Ankara", "beypazari": "Ankara", "elmadag": "Ankara", "akyurt": "Ankara",
    # İzmir
    "konak": "İzmir", "karsiyaka": "İzmir", "bornova": "İzmir", "buca": "İzmir",
    "cigli": "İzmir", "karabaglar": "İzmir", "bayrakli": "İzmir", "balcova": "İzmir",
    "narlidere": "İzmir", "gaziemir": "İzmir", "menemen": "İzmir", "torbali": "İzmir",
    "kemalpasa": "İzmir", "menderes": "İzmir", "tire": "İzmir", "bergama": "İzmir",
    "odemis": "İzmir", "aliaga": "İzmir", "urla": "İzmir", "cesme": "İzmir",
    "foca": "İzmir", "dikili": "İzmir", "seferihisar": "İzmir", "alsancak": "İzmir",
    # Bursa
    "osmangazi": "Bursa", "yildirim": "Bursa", "nilufer": "Bursa", "inegol": "Bursa",
    "gemlik": "Bursa", "mudanya": "Bursa", "karacabey": "Bursa", "mustafakemalpasa": "Bursa",
    # Antalya
    "muratpasa": "Antalya", "kepez": "Antalya", "konyaalti": "Antalya", "alanya": "Antalya",
    "manavgat": "Antalya", "serik": "Antalya", "kemer": "Antalya", "kas": "Antalya",
    # Kocaeli
    "izmit": "Kocaeli", "gebze": "Kocaeli", "darica": "Kocaeli", "korfez": "Kocaeli", "golcuk": "Kocaeli"
}

PHARMACY_KEYWORDS = [
    "eczane", "eczaneler", "eczaneleri", "nobetci", "nobet", "acik", "acil",
    "nerede", "bul", "ilac nereden", "nereden alabilirim", "en yakin", "nerededir"
]

TURKISH_CHAR_MAP = {
    'ı': 'i', 'I': 'i', 'İ': 'i',
    'ğ': 'g', 'Ğ': 'g',
    'ü': 'u', 'Ü': 'u',
    'ş': 's', 'Ş': 's',
    'ö': 'o', 'Ö': 'o',
    'ç': 'c', 'Ç': 'c',
}

def to_slug(text: str) -> str:
    """Metni API uyumlu slug formatına dönüştürür (örn. 'Kadıköy' -> 'kadikoy')."""
    if not text:
        return ""
    text = text.strip()
    for tr, en in TURKISH_CHAR_MAP.items():
        text = text.replace(tr, en)
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text

def extract_pharmacy_intent(user_text: str) -> Dict[str, Any]:
    """
    Kullanıcı mesajından eczane arama niyetini, şehir ve ilçe bilgisini tespit eder.
    Returns:
        {
            "is_pharmacy_query": bool,
            "city": Optional[str],
            "district": Optional[str]
        }
    """
    slug_text = to_slug(user_text)
    tokens = slug_text.split('-')
    raw_lower = user_text.lower()

    is_pharmacy = any(
        kw in slug_text or kw in raw_lower
        for kw in ["eczane", "nobetci", "nobet", "acik-eczane", "en-yakin"]
    )

    detected_city = None
    detected_district = None

    # 1. 81 il içinde ara
    for city in TURKISH_CITIES:
        city_slug = to_slug(city)
        # Kelime bazlı veya tireli kontrol (örn: "istanbulda", "istanbul", "ankara")
        if re.search(r'\b' + re.escape(city_slug) + r'(da|de|ta|te|ya|ye|nin|in|e|a)?\b', slug_text):
            detected_city = city
            break

    # 2. Popüler ilçeler içinde ara
    for dist_slug, city_of_dist in POPULAR_DISTRICT_TO_CITY.items():
        if re.search(r'\b' + re.escape(dist_slug) + r'(da|de|ta|te|ya|ye|nin|in|e|a)?\b', slug_text):
            detected_district = dist_slug.title()
            if not detected_city:
                detected_city = city_of_dist
            break

    # Eğer ilçe tespit edildi ama şehir yoksa eşleştir
    if detected_district and not detected_city:
        detected_city = POPULAR_DISTRICT_TO_CITY.get(to_slug(detected_district))

    # Eğer şehir bulundu ama ilçe bulunamadıysa, şehir dışındaki özel kelimelerden ilçe yakalamayı dene
    if detected_city and not detected_district:
        # Metindeki tokens arasında popüler ilçe kontrolü
        for tok in tokens:
            if tok in POPULAR_DISTRICT_TO_CITY and POPULAR_DISTRICT_TO_CITY[tok].lower() == to_slug(detected_city):
                detected_district = tok.title()
                break

    return {
        "is_pharmacy_query": is_pharmacy,
        "city": detected_city,
        "district": detected_district
    }


def _fetch_api(params: Dict[str, Any]) -> Dict[str, Any]:
    """eczaneadresi.com public API çağrısı yapar."""
    url = f"https://eczaneadresi.com/api/public/widget/duty?{urllib.parse.urlencode(params)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                raw_data = response.read().decode('utf-8')
                return json.loads(raw_data)
    except Exception as e:
        return {"error": f"Bağlantı hatası: {str(e)}"}
    return {"error": "Veri alınamadı."}

def fetch_duty_pharmacies_from_collectapi(
    city: str, district: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Eğer .env dosyasında COLLECTAPI_KEY varsa alternatif kaynak olarak dener."""
    api_key = os.getenv("COLLECTAPI_KEY")
    if not api_key:
        return None

    params = {"il": city}
    if district:
        params["ilce"] = district

    url = f"https://api.collectapi.com/health/dutyPharmacy?{urllib.parse.urlencode(params)}"
    headers = {
        "authorization": f"apikey {api_key}",
        "content-type": "application/json"
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                raw_data = response.read().decode('utf-8')
                return json.loads(raw_data)
    except Exception:
        return None
    return None

def get_duty_pharmacies(city: str, district: Optional[str] = None, limit: int = 8) -> Dict[str, Any]:
    """
    Verilen şehir (ve varsa ilçe) için GÜNCEL NÖBETÇİ ECZANELERİ getirir.
    Sadece ve sadece nöbetçi olan eczaneler döndürülür.
    Kapalı veya nöbetçi olmayan eczaneler ASLA yer almaz.
    """
    if not city or not city.strip():
        return {
            "success": False,
            "message": "Nöbetçi eczaneleri sorgulayabilmek için lütfen bir şehir adı belirtin (örn: İstanbul, Ankara, İzmir)."
        }

    clean_city = city.strip()
    clean_district = district.strip() if district and district.strip() else None

    # 1. CollectAPI anahtarı tanımlıysa önce oradan almayı dene
    collect_data = fetch_duty_pharmacies_from_collectapi(clean_city, clean_district)
    if collect_data and collect_data.get("success") and collect_data.get("result"):
        pharmacies = []
        for item in collect_data["result"][:limit]:
            pharmacies.append({
                "name": item.get("name", "Bilinmeyen Eczane"),
                "city": clean_city.title(),
                "district": item.get("dist", clean_district or "").title(),
                "address": item.get("address", "Adres bilgisi yok"),
                "phone": item.get("phone", "Telefon bilgisi yok"),
                "maps_url": f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(item.get('name', '') + ' Eczanesi ' + clean_city)}",
                "is_duty": True
            })
        return {
            "success": True,
            "city": clean_city.title(),
            "district": clean_district.title() if clean_district else None,
            "count": len(pharmacies),
            "pharmacies": pharmacies,
            "note": "Bu liste sadece ve sadece şu an açık olan GÜNCEL NÖBETÇİ eczaneleri içermektedir."
        }

    # 2. eczaneadresi.com public widget API çağrısı
    city_slug = to_slug(clean_city)
    district_slug = to_slug(clean_district) if clean_district else None

    data = None
    # İlçe belirtilmişse önce ilçe bazında ara
    if district_slug:
        data = _fetch_api({
            "scope": "district",
            "city": city_slug,
            "district": district_slug,
            "limit": min(limit, 50)
        })
        # Eğer district slug ile sonuç 0 geldiyse, şehir içinde arama (q=district) parametresi ile dene
        if not data.get("ok") or not data.get("pharmacies"):
            data = _fetch_api({
                "scope": "city",
                "city": city_slug,
                "q": district_slug,
                "limit": min(limit, 50)
            })

    # İlçe belirtilmediyse veya ilçe araması sonuç vermediyse il genelinde nöbetçileri çek
    if not data or not data.get("ok") or not data.get("pharmacies"):
        data = _fetch_api({
            "scope": "city",
            "city": city_slug,
            "limit": min(limit, 50)
        })

    if data.get("ok") and "pharmacies" in data:
        raw_list = data.get("pharmacies", [])
        if not raw_list:
            location_str = f"{clean_city.title()}" + (f" - {clean_district.title()}" if clean_district else "")
            return {
                "success": False,
                "city": clean_city.title(),
                "district": clean_district.title() if clean_district else None,
                "message": f"{location_str} için şu an sistemde kayıtlı nöbetçi eczane bulunamadı. Lütfen il/ilçe adını kontrol edin."
            }

        pharmacies = []
        for p in raw_list[:limit]:
            name = p.get("name", "")
            if not name.lower().endswith("eczanesi") and not name.lower().endswith("eczane"):
                name = f"{name} Eczanesi"

            lat = p.get("lat")
            lng = p.get("lng")
            if lat and lng:
                maps_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
            else:
                maps_url = p.get("maps") or f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name + ' ' + clean_city)}"

            pharmacies.append({
                "name": name,
                "city": p.get("city", clean_city.title()),
                "district": p.get("district", clean_district or "").title(),
                "address": p.get("address", "Adres bilgisi yok"),
                "phone": p.get("phone", "Telefon bilgisi yok"),
                "maps_url": maps_url,
                "is_duty": True
            })

        return {
            "success": True,
            "city": clean_city.title(),
            "district": clean_district.title() if clean_district else None,
            "count": len(pharmacies),
            "date": data.get("tarih"),
            "pharmacies": pharmacies,
            "note": "Bu liste yalnızca o an açık olan RESMİ NÖBETÇİ eczanelerden oluşmaktadır. Normal veya kapalı eczaneler dahil edilmemiştir."
        }

    return {
        "success": False,
        "message": f"{clean_city.title()} için nöbetçi eczane bilgisi alınamadı. Hata: {data.get('error', 'Bilinmeyen hata')}"
    }

def format_duty_pharmacies_for_llm(result: Dict[str, Any]) -> str:
    """
    LLM veya kullanıcı arayüzü için okunabilir Türkçe metin çıktısı üretir.
    """
    if not result.get("success"):
        return result.get("message", "Nöbetçi eczane bulunamadı.")

    city = result.get("city", "")
    district = result.get("district")
    header = f"🚨 **{city}" + (f" / {district}" if district else "") + " Güncel Nöbetçi Eczaneleri:**\n\n"
    header += "*Not: Bu liste sadece ve sadece şu an aktif olan NÖBETÇİ eczaneleri içerir. Kapalı hiçbir eczane bulunmamaktadır.*\n\n"

    items = []
    for i, p in enumerate(result.get("pharmacies", []), 1):
        item_text = (
            f"**{i}. 🏥 {p['name']}** ({p.get('district', '')})\n"
            f"- 📍 **Adres:** {p['address']}\n"
            f"- 📞 **Telefon:** [{p['phone']}](tel:{p['phone'].replace(' ', '')})\n"
            f"- 🗺️ **Harita / Yol Tarifi:** [Haritada Gör]({p['maps_url']})\n"
        )
        items.append(item_text)

    return header + "\n".join(items)
