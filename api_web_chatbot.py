import os
import json
import random
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path


BASE_SYSTEM_PROMPT = """
Sen bir duygu sınıflandırma ve yanıt üretme modelisin.
Görevin şunlardır:

1. Kullanıcının mesajındaki duyguyu tahmin et.
2. O duyguya uygun bir ilk cevap yaz.
3. Ardından ilk duygu ile uyumlu bir ikinci duygu seç; gerekirse aynı duyguyu tekrar seçebilirsin.
4. Seçilen ikinci duyguya uygun bir ikinci cevap yaz (ilk yanıtla tutarlı olmalıdır).
5. Çıktıyı Türkçe ver ve her iki yanıt da sadece 1 cümle olmalıdır.
6. Çıktıyı her zaman aşağıdaki JSON formatında ver:

{
  "ilk_ruh_hali": "...",
  "ilk_cevap": "...",
  "ikinci_ruh_hali": "...",
  "ikinci_cevap": "..."
}

Seçilebilecek ruh halleri:
Mutlu, Üzgün, Öfkeli, Şaşkın, Utanmış, Endişeli, Gülümseyen, Flörtöz, Sorgulayıcı, Sorgulayıcı, Yorgun

EK KURALLAR (İstatistik Sorguları):
- Kullanıcı istatistik veya özet isterse (ör. "bugün en çok hangi duygu", "kaç kez öfkeli", "duygu istatistikleri"), sınıflandırma JSON'u üretmek yerine şu fonksiyonu çağır:
  - get_emotion_stats
  - period argümanı: Kullanıcı mesajında "bugün" geçiyorsa "today"; aksi halde "all" kullan.
- Fonksiyonun dönüşünden sonra sadece 1 cümlelik, Türkçe, kısa bir özet yaz ve JSON döndürme.
"""


load_dotenv()

app = FastAPI(title="Duygu Sınıflandırma ve Yanıt API", version="1.0.0")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Duygu → emoji veri kaynağını yükle (uygulama başında bir kez)
MOOD_EMOJIS: Dict[str, list[str]] = {}
# Kalıcı depolama dosyaları
DATA_DIR = Path(__file__).parent / "data"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.txt"
MOOD_COUNTER_FILE = DATA_DIR / "mood_counter.txt"
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data_path = DATA_DIR / "mood_emojis.json"
    if data_path.exists():
        MOOD_EMOJIS = json.loads(data_path.read_text(encoding="utf-8"))
    # Dosyaları oluştur
    if not CHAT_HISTORY_FILE.exists():
        CHAT_HISTORY_FILE.write_text("", encoding="utf-8")
    if not MOOD_COUNTER_FILE.exists():
        MOOD_COUNTER_FILE.write_text("{}", encoding="utf-8")
except Exception:
    MOOD_EMOJIS = {}


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Kullanıcı metni")


class AnalyzeResponse(BaseModel):
    ilk_ruh_hali: str
    ilk_cevap: str
    ikinci_ruh_hali: str
    ikinci_cevap: str


# 09_web_chatbot.py mimarisine benzer: durum tutan chatbot sınıfı
class EmotionChatbot:
    def __init__(self) -> None:
        self.messages: list[Dict[str, Any]] = []
        self.stats: Dict[str, Any] = {
            "requests": 0,
            "last_request_at": None,
        }
        self.allowed_moods = [
            "Mutlu", "Üzgün", "Öfkeli", "Şaşkın", "Utangaç",
            "Endişeli", "Yorgun", "Gururlu", "Çaresiz", "Flörtöz"
        ]
        self.emotion_counts: Dict[str, int] = {m: 0 for m in self.allowed_moods}
        # Kalıcı sayaçları yükle
        persisted = self._load_mood_counts()
        if persisted:
            # Sadece bilinen anahtarları al
            for k, v in persisted.items():
                if k in self.emotion_counts and isinstance(v, int):
                    self.emotion_counts[k] = v

    def _load_mood_counts(self) -> Dict[str, int]:
        try:
            raw = MOOD_COUNTER_FILE.read_text(encoding="utf-8").strip() or "{}"
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): int(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def _save_mood_counts(self) -> None:
        try:
            MOOD_COUNTER_FILE.write_text(
                json.dumps(self.emotion_counts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _append_chat_history(self, user_message: str, response_text: str) -> None:
        try:
            line = json.dumps({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "user": user_message,
                "response": response_text
            }, ensure_ascii=False)
            with CHAT_HISTORY_FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def get_functions(self) -> list[Dict[str, Any]]:
        return [
            {
                "name": "get_emotion_stats",
                "description": "Duygu sayım özetini döndürür (tümü veya bugün)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "period": {"type": "string", "enum": ["all", "today"], "description": "Özet periyodu"}
                    },
                    "required": []
                }
            }
        ]

    def get_emotion_stats(self, period: str | None = None) -> Dict[str, Any]:
        counts: Dict[str, int] = {m: 0 for m in self.allowed_moods}
        if period == "today":
            # chat_history.txt'yi gezip bugün tarihli JSON satırlardan sayım yap
            today_str = datetime.now().strftime("%Y-%m-%d")
            try:
                if CHAT_HISTORY_FILE.exists():
                    for line in CHAT_HISTORY_FILE.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        obj = json.loads(line)
                        ts = str(obj.get("timestamp", ""))
                        if not ts.startswith(today_str):
                            continue
                        # response alanı JSON string olabilir
                        resp = str(obj.get("response", ""))
                        # İlk JSON objesini çıkarmayı deneyelim
                        try:
                            data = json.loads(resp)
                        except Exception:
                            data = None
                        if isinstance(data, dict):
                            m1 = str(data.get("ilk_ruh_hali", "")).strip()
                            m2 = str(data.get("ikinci_ruh_hali", "")).strip()
                            if m1 in counts:
                                counts[m1] += 1
                            if m2 in counts:
                                counts[m2] += 1
            except Exception:
                pass
        else:
            # Varsayılan: tüm zamanlar - mevcut memory sayacını kullan
            counts = dict(self.emotion_counts)

        summary_parts = [f"{cnt} kez {m.lower()}" for m, cnt in counts.items() if cnt > 0]
        summary = ", ".join(summary_parts) if summary_parts else "Henüz duygu kaydı yok"
        return {"counts": counts, "summary": summary, "period": period or "all"}

    def chat(self, user_message: str) -> Dict[str, Any]:
        self.stats["requests"] += 1
        self.stats["last_request_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Geçmişten son 3 mesajı (user/assistant) dahil et, üstüne yeni kullanıcı mesajını ekle
        # En başa her zaman sabit sistem promptu koy
        history_tail = self.messages[-6:] if len(self.messages) > 6 else self.messages[:]
        messages_payload: list[Dict[str, Any]] = [{"role": "system", "content": BASE_SYSTEM_PROMPT.strip()}]
        messages_payload.extend(history_tail)
        messages_payload.append({"role": "user", "content": user_message})

        # Debug için OpenAI'ye giden tam metni hazırla
        def _messages_to_debug(ms: list[Dict[str, Any]]) -> str:
            parts: list[str] = []
            for m in ms:
                role = m.get("role", "")
                if "content" in m and m["content"] is not None:
                    parts.append(f"{role}: {m['content']}")
                elif "function_call" in m and m["function_call"] is not None:
                    parts.append(f"{role}: [function_call] {m['function_call']}")
                else:
                    parts.append(f"{role}: ")
            return "\n".join(parts)

        request_debug = _messages_to_debug(messages_payload)

        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages_payload,
            functions=self.get_functions(),
            function_call="auto",
            temperature=0.2,
        )

        msg = completion.choices[0].message

        # Eğer AI bir fonksiyon çağırdıysa (örn. özet istemi)
        if getattr(msg, "function_call", None):
            function_name = msg.function_call.name
            if function_name == "get_emotion_stats":
                period_arg = None
                try:
                    if hasattr(msg.function_call, "arguments") and msg.function_call.arguments:
                        args_obj = json.loads(msg.function_call.arguments)
                        period_arg = args_obj.get("period")
                except Exception:
                    period_arg = None
                result = self.get_emotion_stats(period=period_arg)

                # Konuşmaya fonksiyon çağrısını ve sonucunu ekle
                self.messages.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": msg.function_call
                })
                self.messages.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(result, ensure_ascii=False)
                })

                # Final yanıt metni
                messages_payload.append({"role": "assistant", "content": None, "function_call": msg.function_call})
                messages_payload.append({"role": "function", "name": function_name, "content": json.dumps(result, ensure_ascii=False)})
                final = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages_payload,
                    temperature=0.2,
                )
                text = final.choices[0].message.content or ""
                # Geçmişe son konuşmayı kaydet: kullanıcı + asistan cevabı
                self.messages.append({"role": "user", "content": user_message})
                self.messages.append({"role": "assistant", "content": text})
                # Ham chat'i kaydet
                self._append_chat_history(user_message, text)
                return {"response": text, "request_debug": request_debug}

        # Aksi halde modelden JSON bekliyoruz (duygu sınıflandırma)
        content = msg.content or ""

        def extract_json_object(text: str) -> Dict[str, Any] | None:
            # code fence temizle
            t = text.replace("```json", "").replace("```", "").strip()
            # İlk dengeli JSON objesini çıkar (kaçışlı stringleri hesaba kat)
            start = t.find('{')
            if start == -1:
                return None
            depth = 0
            in_string = False
            escape = False
            end_index = -1
            for i in range(start, len(t)):
                ch = t[i]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                else:
                    if ch == '"':
                        in_string = True
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end_index = i
                            break
            if end_index == -1:
                return None
            candidate = t[start:end_index + 1]
            try:
                return json.loads(candidate)
            except Exception:
                return None

        data = extract_json_object(content)
        if not data:
            # Ham chat'i kaydet
            self._append_chat_history(user_message, content)
            # Geçmişe ekle
            self.messages.append({"role": "user", "content": user_message})
            self.messages.append({"role": "assistant", "content": content})
            return {"response": content, "request_debug": request_debug}

        required_keys = {"ilk_ruh_hali", "ilk_cevap", "ikinci_ruh_hali", "ikinci_cevap"}
        missing = [k for k in required_keys if k not in data]
        if missing:
            # Ham chat'i kaydet
            self._append_chat_history(user_message, content)
            return {"response": content}

        # Duygu sayaçlarını güncelle
        def inc(mood: str) -> None:
            key = (mood or "").strip()
            if key in self.emotion_counts:
                self.emotion_counts[key] += 1

        first_mood_raw = str(data.get("ilk_ruh_hali", ""))
        second_mood_raw = str(data.get("ikinci_ruh_hali", ""))

        inc(first_mood_raw)
        inc(second_mood_raw)
        # Sayaçları kalıcı kaydet
        self._save_mood_counts()

        # Emoji seçim: mood_emojis.json'dan duyguya göre rastgele
        def normalize_mood(name: str) -> str:
            n = name.strip().lower()
            mapping = {
                "utangaç": "Utanmış",
                "utanmış": "Utanmış",
                "gülümseyen": "Gülümseyen",
                "mutlu": "Mutlu",
                "üzgün": "Üzgün",
                "öfkeli": "Öfkeli",
                "şaşkın": "Şaşkın",
                "endişeli": "Endişeli",
                "flörtöz": "Flörtöz",
                "sorgulayıcı": "Sorgulayıcı",
                "yorgun": "Yorgun",
            }
            return mapping.get(n, name)

        def pick_emoji(mood: str) -> Optional[str]:
            key = normalize_mood(mood)
            options = MOOD_EMOJIS.get(key)
            if options:
                try:
                    return random.choice(options)
                except Exception:
                    return None
            return None

        first_emoji = pick_emoji(first_mood_raw)
        second_emoji = pick_emoji(second_mood_raw)

        response_text = json.dumps(data, ensure_ascii=False)
        # Ham chat'i kaydet
        self._append_chat_history(user_message, response_text)
        # Geçmişe ekle
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": response_text})

        return {
            "response": response_text,
            "first_emoji": first_emoji,
            "second_emoji": second_emoji,
            "request_debug": request_debug,
        }


# Global chatbot instance (09'daki mimari gibi)
chatbot_instance: EmotionChatbot | None = None


from pathlib import Path


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    template_path = Path(__file__).parent / "templates" / "index.html"
    try:
        html = template_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HTML yüklenemedi: {e}")
    return HTMLResponse(content=html)


@app.post("/chat")
def chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    global chatbot_instance
    if chatbot_instance is None:
        chatbot_instance = EmotionChatbot()

    user_message = str(payload.get("message", "")).strip()
    if not user_message:
        return {"error": "Mesaj boş olamaz"}

    try:
        result = chatbot_instance.chat(user_message)
        stats = {
            "requests": chatbot_instance.stats["requests"],
            "last_request_at": chatbot_instance.stats["last_request_at"],
        }
        # result: { response: str, first_emoji?: str, second_emoji?: str, request_debug?: str }
        out = {"response": result.get("response", ""), "stats": stats}
        if "first_emoji" in result:
            out["first_emoji"] = result["first_emoji"]
        if "second_emoji" in result:
            out["second_emoji"] = result["second_emoji"]
        if "request_debug" in result:
            out["request_debug"] = result["request_debug"]
        return out
    except HTTPException as e:
        return {"error": e.detail}
    except Exception as e:
        return {"error": str(e)}


# Çalıştırma:
# uvicorn api_web_chatbot:app --host 0.0.0.0 --port 8000 --reload
