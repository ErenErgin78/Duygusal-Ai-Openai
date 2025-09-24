# Duygusal AI Bot - Duygu Analizi Chatbotu

Bu proje, yapay zeka kullanarak kullanıcı mesajlarındaki duyguları analiz eden ve iki aşamalı yanıt veren bir chatbot'tur. Bot, mesajınızdaki duyguyu tespit eder, ona uygun bir cevap verir, sonra ikinci bir duygu ve cevap daha sunar. Kullanıcı "Sonraki" butonu ile ikinci aşamaya geçebilir.

## Özellikler

- 🤖 **Akıllı Duygu Analizi**: Mesajınızdaki duyguyu tespit eder ve size uygun yanıt verir
- 🎭 **İki Aşamalı Yanıt**: İlk duygu/cevap → ikinci duygu/cevap (uyumlu veya aynı duygu)
- 😊 **Kullanıcı Duygu Takibi**: Sizin mesajınızdaki duygunuzu da kaydeder
- 🎨 **Görsel Arayüz**: Ortadaki yüz emojisi ile duygu gösterimi (animasyonlu)
- 📊 **İstatistikler**: "Bugün en çok hangi duyguyu yaşadın?" gibi sorulara yanıt verir
- 🌙 **Karanlık Mod**: Tema değiştirme butonu ile aydınlık/karanlık geçiş
- 🌧️ **Matrix Animasyonu**: Arka planda Matrix tarzı kod yağmuru efekti
- 📱 **Mobil Uyumlu**: Telefon ve tablette de çalışır

---

## Proje Dosyaları

```
Duygusal-Ai-Openai/
  api_web_chatbot.py        # Ana uygulama (Python)
  templates/
    index.html             # Web sayfası (HTML + CSS + JavaScript)
  data/
    mood_emojis.json       # Duygu emojileri veritabanı
    chat_history.txt       # Konuşma geçmişi
    mood_counter.txt       # Duygu istatistikleri
  requirements.txt         # Gerekli Python paketleri
  .env                     # Gizli ayarlar (OpenAI API anahtarı)
  README.md               # Bu dosya
```

---

## Nasıl Çalışır?

### 1) Web Sunucusu
- Python ile çalışan web sunucusu
- Kullanıcı mesajlarını alır, OpenAI'ye gönderir, yanıt döner
- İki endpoint: ana sayfa (`/`) ve chat (`/chat`)

### 2) Yapay Zeka Motoru
- OpenAI GPT-3.5-turbo modeli kullanır
- Son 3 konuşmayı hatırlar (bağlam için)
- Duygu analizi yapar ve iki aşamalı yanıt üretir
- İstatistik sorularını anlar ve veritabanından yanıt verir

### 3) Kullanıcı Arayüzü
- **Ortadaki Yüz**: Duygu emojisi gösterir (animasyonlu)
- **Chat Kutusu**: Konuşma geçmişi
- **Giriş Alanı**: Mesaj yazma ve gönderme
- **Sonraki Butonu**: İkinci aşamaya geçiş
- **Tema Butonu**: Aydınlık/karanlık mod
- **Matrix Efekti**: Arka plan animasyonu

---

## Duygu Sistemi

Bot şu duyguları tanır ve analiz eder:

**Temel Duygular**: Mutlu, Üzgün, Öfkeli, Şaşkın, Utanmış, Endişeli, Gülümseyen, Flörtöz, Sorgulayıcı, Yorgun

---

## Emoji Veritabanı

Her duygu için özel emoji ve kaomoji (metin yüzler) koleksiyonu:

**Örnek**: Mutlu → 😊, 😄, ^_^, (◠‿◠)

Bot, her duygu için rastgele emoji seçer ve yüz alanında gösterir.

---

## Kullanım Örnekleri

### Normal Konuşma
- **Siz**: "Bugün çok mutluyum!"
- **Bot**: İlk aşama: "Mutlu: Harika! Bu güzel haberi duymak beni de mutlu ediyor."
- **Siz**: "Sonraki" butonuna basın
- **Bot**: İkinci aşama: "Gülümseyen: Bu pozitif enerjinizi koruyun!"

### İstatistik Sorguları
- **Siz**: "Bugün en çok hangi duyguyu yaşadım?"
- **Bot**: "Bugün 3 kez mutlu, 1 kez endişeli duygularınızı yaşadınız."

---

## Kurulum ve Çalıştırma

### 1. Gereksinimler
- Python 3.8+ yüklü olmalı
- OpenAI API anahtarı gerekli

### 2. Kurulum
```bash
# Gerekli paketleri yükle
pip install -r requirements.txt
```

### 3. API Anahtarı
`.env` dosyasını düzenleyin:
```
OPENAI_API_KEY=sk-your-api-key-here
```

### 4. Çalıştırma
```bash
# Sunucuyu başlat
python -m uvicorn api_web_chatbot:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Kullanım
Tarayıcınızda şu adresi açın:
```
http://localhost:8000/
```