## Duygu Sınıflandırma Web Chatbot (FastAPI)

Bu proje, FastAPI tabanlı bir web servisi ve basit bir HTML arayüzü ile kullanıcı mesajlarından duygu sınıflandırması yapan ve iki aşamalı yanıt üreten bir chatbot içerir. Model, ilk duyguyu ve ona uygun cevabı üretir; ardından ilk duygu ile uyumlu (gerekirse aynı) ikinci bir duygu ve ona uygun ikinci cevabı üretir. Arayüz, ilk adımı gösterir; kullanıcı ok tuşu ile ikinci adıma geçer.

### Özellikler
- OpenAI sohbet tamamlamaları ile sistem prompt’lu duygu sınıflandırma
- İki adımda gösterim: ilk duygu/cevap → ikinci duygu/cevap
- AI yanıtından emoji çıkarımı ve ortadaki eliptik yüz üzerinde gösterim (animasyonlu)
- JSON olmayan/çıtalı (code fence) çıktılara karşı sağlam JSON ayıklama (hem backend hem frontend)
- Duygu sayaçları: “3 kez öfkeli, 4 kez mutlu” gibi özet fonksiyonu (AI function calling ile tetiklenebilir) ve TXT’ye kalıcı yazma
- Ek gösterim: sayfa sonunda ham AI yanıtının metin olarak gösterimi
- Duyguya göre rastgele emoji seçimi: `mood_emojis.json`’dan iki duygu için iki emoji seçilir ve UI’da adım adım gösterilir

---

## Dosya Yapısı

```
hafta_2/
  api_web_chatbot.py        # FastAPI uygulaması ve chatbot sınıfı
  templates/
    index.html             # Web arayüzü (HTML + inline CSS/JS)
  data/
    mood_emojis.json       # Duygu → emoji/kaomoji veri kaynağı
    chat_history.txt       # Her istek için tek satır JSON (timestamp, user, response)
    mood_counter.txt       # Duygu sayaçları (JSON) - kalıcı depolama
  README_emotion_chatbot.md# Bu doküman
```

Diğer örnek dosyalar (`06_function_calling.py`, `07_chatbot_with_functions.py`, `09_web_chatbot.py` vb.) hocanın örneklerini içerir; bu proje onlara mimari olarak benzer, ancak FastAPI ve özel arayüz davranışları ile ayrışır.

---

## Mimari

### 1) API Katmanı (`api_web_chatbot.py`)
- FastAPI uygulaması `app` ve global `chatbot_instance` oluşturulur (durum tutarlılığı için tekil örnek).
- Endpoint’ler:
  - GET `/` → `templates/index.html` döner (statik HTML arayüz)
  - POST `/chat` → `{ message: string }` alır, modeli çağırır, şu formatta yanıt döner:
    ```json
    {
      "response": "<modelin döndürdüğü metin veya JSON string>",
      "stats": { "requests": number, "last_request_at": string }
    }
    ```

### 2) Chatbot Sınıfı (`EmotionChatbot`)
- Alanlar:
  - `messages`: OpenAI mesaj geçmişi (system + user + assistant + function)
  - `stats`: istek sayacı ve son istek zamanı
  - `allowed_moods`: desteklenen duygu isimleri (UI/raporlama için)
  - `emotion_counts`: duygu sayaçları (Mutlu, Üzgün, Öfkeli, Şaşkın, …)
- Metotlar:
  - `get_functions()`: AI function calling için fonksiyon şemaları (şu an `get_emotion_stats`)
  - `get_emotion_stats()`: sayaçlardan özet üretir ("3 kez mutlu, 1 kez üzgün" gibi)
  - `chat(user_message: str) -> str`: 
    - Sistem promptu ve kullanıcı mesajı ile `gpt-3.5-turbo` çağrısı
    - `function_call="auto"` ile AI fonksiyon seçerse `get_emotion_stats` çalıştırılır
    - Aksi halde model yanıtından JSON ayıklanır; varsa ilk/ikinci duygu sayaçları artar, `mood_counter.txt` güncellenir
    - `mood_emojis.json`’dan iki duygu için iki emoji rastgele seçilir ve `first_emoji`/`second_emoji` ile birlikte dönülür
    - Yanıt, JSON string veya düz metin olarak `response` alanında dönülür
    - JSON ayıklama: code fence temizleme + ilk `{` ile son `}` aralığını parse etme (backend) ve yedek olarak frontend’de aynı mantık
  - Kalıcılık yardımcıları:
    - `_load_mood_counts()`: `data/mood_counter.txt`’yi yükleyip sayacı başlatır
    - `_save_mood_counts()`: güncel sayaçları JSON olarak dosyaya yazar
    - `_append_chat_history(user, response)`: her isteği `data/chat_history.txt`’ye tek satır JSON olarak ekler

### 3) Arayüz (`templates/index.html`)
- Eliptik yüz (ortada) ve içinde emoji; emoji değişiminde küçük scale/opacity animasyonu
- Mesaj kutusu, Gönder butonu ve “▶ Sonraki” kontrolü
- Akış:
  1. Kullanıcı mesaj gönderir → input devre dışı (bekleme)
  2. Model yanıtı geldiğinde sayfa altında ham yanıt gösterilir (debug/şeffaflık)
  3. JSON ise iki adım çıkarılır: ilk duygu/cevap hemen gösterilir, duyguya göre gelen `first_emoji` yüz alanında gösterilir; “▶ Sonraki” ile ikinci adım gösterilir ve `second_emoji` kullanılır (bu sırada input kapalı kalır)
  4. İkinci adım gösterildikten sonra input tekrar açılır
- JSON tespit edilemezse düz metin mesaj ve emoji gösterilir
- Kaomoji taşmasını engellemek için yüz alanı otomatik olarak sığdırılır; büyük `(O_O)` gibi ifadeler ölçeklenir.

---

## Sistem Prompt

Sistem promptu, modele ilk ve ikinci duygu/cevabı belirli JSON şemasında üretmesini söyler (Türkçe ve tek cümle kısıtları dahil). İkinci duygu, ilk duygu ile uyumlu olmalı; gerekirse tamamen aynı duygu da seçilebilir. Prompt, backend içinde dinamik olarak `{text}` ile kullanıcının mesajını yerleştirerek iletilir.

Beklenen JSON şeması:
```json
{
  "kullanici_ruh_hali": "...",
  "ilk_ruh_hali": "...",
  "ilk_cevap": "...",
  "ikinci_ruh_hali": "...",
  "ikinci_cevap": "..."
}
```

---

## Veri Kaynağı: `data/mood_emojis.json`

Seçili duyguya uygun yüz odaklı (kol içermeyen) emoji/kaomoji listeleri içerir. Başlıca başlıklar: `Mutlu`, `Üzgün`, `Öfkeli`, `Şaşkın`, `Utanmış`, `Endişeli`, `Gülümseyen`, `Flörtöz`, `Sorgulayıcı`, `Yorgun`.

Arayüz şu an bot cevabından ilk emojiyi çıkarıp yüz üzerinde gösterir. İstenirse bu dosyadan duyguya göre rastgele emoji seçilerek yüz güncellenebilir.

Sunucu tarafı güncel davranış: AI’nin döndürdüğü iki duyguya karşılık bu dosyadan rastgele iki emoji seçilir ve `first_emoji`, `second_emoji` olarak frontend’e gönderilir. Frontend ilk adımda `first_emoji`, ikinci adımda `second_emoji` kullanır; yoksa metinden emoji çıkarımı fallback’tir.

---

## API Detayları

### POST /chat
- İstek:
  ```json
  { "message": "Bugün biraz gerginim ama umutluyum." }
  ```
- Yanıt (örnek, JSON üretildiyse):
  ```json
  {
    "response": "{\n  \"ilk_ruh_hali\": \"Endişeli\",\n  \"ilk_cevap\": \"...\",\n  \"ikinci_ruh_hali\": \"Mutlu\",\n  \"ikinci_cevap\": \"...\"\n}",
    "first_emoji": "😟",
    "second_emoji": "😊",
    "stats": { "requests": 3, "last_request_at": "2025-09-24 12:34:56" }
  }
  ```
- Yanıt (JSON değilse):
  ```json
  { "response": "...düz metin...", "stats": { ... } }
  ```

---

## Çalıştırma

1) Kurulum (sanal ortam açıkken):
```
pip install -r requirements.txt
```

2) Ortam değişkeni:
```
OPENAI_API_KEY=your_openai_api_key_here
```

3) Sunucu:
```
uvicorn api_web_chatbot:app --host 0.0.0.0 --port 8000 --reload
```

4) Tarayıcı:
```
http://localhost:8000/
```

---

## Hata Yönetimi ve Sağlamlık
- Backend ve frontend, code fence/ek metin içeren model çıktılarında JSON bloğunu güvenle ayıklamaya çalışır.
- JSON anahtarları eksikse düz metin akışına düşer.
- Ağ/parse hatalarında UI input tekrar aktif edilir ve kullanıcı bilgilendirilir.
- TXT kalıcılıkta yazma hataları sessizce yutulur (kullanıcı akışı kesilmez); detaylı loglama ihtiyaca göre eklenebilir.

---

## Sık Karşılaşılan Sorular

### Model fonksiyonları kendisi mi seçiyor?
Evet. `function_call="auto"` ile AI gerekli gördüğünde `get_emotion_stats` fonksiyonunu çağırır; biz sadece sonucu işleyip final metin döndürürüz.

### Neden yanıt metni bazı zamanlar alt bölümde JSON gibi görünüyor?
Model her zaman saf JSON döndürmeyebilir. Arayüz, bu metinden JSON’u ayıklayıp iki aşamalı gösterim yapmayı dener; yine de ham yanıt altta referans için gösterilir.

---

## Geliştirme Fikirleri
- Duygu sayaçlarının kullanıcı oturumlarına göre ayrılması (ID bazlı)
- `chat_history.txt` için döküm/filtreleme aracı (tarih, kullanıcı metni, duygu)
- Duygu sayaçlarının kalıcı depolanması (ör. SQLite)
- Streaming yanıt (parça parça gösterim)
- Çok dillilik ve daha fazla duygu kategorisi


