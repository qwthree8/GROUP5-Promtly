# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from auth import authenticate_user, create_access_token, register_user, decode_token, get_chat_history, save_chat
from database import SessionLocal
from datetime import datetime
import google.generativeai as genai
import os, re, json
from models import ChatHistory, User
from dotenv import load_dotenv

# ─────────────────────────────────────── Configuration
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash-latest")

# ─────────────────────────────────────── Helpers
def _ask(prompt: str) -> str:
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        return f"[HATA]: {e}"

def prompt_onerileri(topic: str) -> list[str]:
    p = (
        f"“{topic}” mesleğini icra eden deneyimli bir profesyonele, "
        "gerçek hayatta işe yarayacak, pratik ve doğrudan yanıtlar alabileceği "
        "**6 tane o mesleği icra eden bir kişinin yapay zekaya sorabileceği bilgi alabileceği örnek promptlar** yaz.**ancak yazdığın örnek promptlarda * karakteri parantez içi ifadeler ve tırnak**("")** işaretleri olmasın."
    )
    out = _ask(p).split("\n")
    qs = [s.strip(" -•1234567890.") for s in out if s.strip()][:6]
    if len(qs) < 6:
        qs += ["Örnek üretilemedi."] * (6 - len(qs))
    return qs

def sektor_sik_sorular(sektor: str) -> list[str]:
    p = (
        f"“{sektor}” sektöründe, yapay zekaya en sık sorulan sadece **4 başlık** yaz. "
        "Her başlık 3–5 kelime arasında, maddeleme veya numaralandırma olmadan."
    )
    out = _ask(p).split("\n")
    ks = [s.strip(" -•1234567890.") for s in out if s.strip()][:4]
    if len(ks) < 4:
        ks += ["Konu üretilmedi"] * (4 - len(ks))
    return ks

def cevaptan_yeni_oneri(cevap: str) -> list[str]:
    # Modelin cevabına dair 6 yönlendirici soru üret
    p = (
        f"Yukarıdaki cevaba dayanarak, sırf kısa sorular olarak **6 yeni** "
        "yönlendirici soru üret. Her soru 10 kelimeyi geçmesin."
    )
    out = _ask(p).split("\n")
    # Sadece "?" ile biten gerçek soru cümlelerini alıyoruz
    qs = [s.strip(" -•1234567890.") for s in out if s.strip().endswith("?")]
    # Gerekirse eksikleri tamamla
    if len(qs) < 6:
        qs += ["Devam önerisi yok?"] * (6 - len(qs))
    return qs[:6]

def improve_prompt_text(text: str) -> str:
    return _ask(f"Şuanda bir promt denetleyicisisin. İki nokta işaretinden sonraki promt kullanıcının girdisi. Bu promtu yapay zeka modellerinin en iyi şekilde anlayacağı şekilde yaz. gerekirse detaylandır,başka bir şey yapma:\n\n{text}")

def evaluate_prompt(text: str) -> tuple[int,str]:
    raw = _ask(
        "Aşağıdaki promptu 0–100 arasında puanla ve JSON olarak cevap ver:\n"
        "{score: <sayı>, suggestion: <kısa öneri>}\n\nPROMPT:\n" + text
    )
    try:
        js = re.search(r"\{.*?\}", raw, re.S).group()
        d = json.loads(js)
        return int(d.get("score",0)), d.get("suggestion","")
    except:
        return 0, "Puanlama yapılamadı."

# ─────────────────────────────────────── FastAPI setup
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.globals["now"] = datetime.utcnow

# ─────────────────────────────────────── Routes
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    if "token" in request.session:
        return RedirectResponse("/chat", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request):
    form = await request.form()
    db = SessionLocal()
    try:
        user = authenticate_user(db, form["username"], form["password"])
        if user:
            token = create_access_token({"sub": user.username, "id": user.id})
            request.session["token"] = token
            return RedirectResponse("/chat", status_code=303)
        return templates.TemplateResponse("login.html", {"request": request, "error": "❌ Giriş başarısız"})
    finally:
        db.close()

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(request: Request):
    form = await request.form()
    db = SessionLocal()
    try:
        user = register_user(db, form["username"], form["password"], form["email"], form["gender"])
        token = create_access_token({"sub": user.username, "id": user.id})
        request.session["token"] = token
        return RedirectResponse("/chat", status_code=303)
    except Exception:
        return templates.TemplateResponse("register.html", {"request": request, "error": "❌ Kayıt başarısız"})
    finally:
        db.close()

@app.post("/delete-all-chats")
async def delete_all_chats(request: Request):
    token = request.session.get("token")
    payload = decode_token(token) if token else None
    if not payload:
        return RedirectResponse("/login", status_code=303)

    user_id = payload.get("id")
    db = SessionLocal()
    db.query(ChatHistory).filter_by(user_id=user_id).delete()
    db.commit()
    db.close()

    return RedirectResponse("/chat", status_code=303)

@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    token = request.session.get("token")
    if not token or not decode_token(token):
        return RedirectResponse("/login", status_code=303)
    user = decode_token(token)["sub"]
    history = get_chat_history(user)
    # İlk açılışta kesinlikle boş listeler gönderiyoruz
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "history": history,
        "initialTopics": [],  # sektör girilene kadar gizli kalacak
        "initialQuestions": []  # henüz öneri yok
    })

@app.get("/sektor-ornekleri")
def sektor_ornekleri(sektor: str):
    return JSONResponse({
        "sorular": prompt_onerileri(sektor),
        "konular": sektor_sik_sorular(sektor)
    })

@app.get("/topic-ornekleri")
def topic_ornekleri(topic: str):
    return JSONResponse({
        "sorular": prompt_onerileri(topic)
    })

@app.post("/api/chat")
async def chat_api(request: Request):
    data = await request.json()
    msg  = data.get("message", "")
    tid  = data.get("thread_id")       # yeni alan

    resp = _ask(msg)

    token = request.session.get("token")
    thread_id = None
    if token and decode_token(token):
        username = decode_token(token)["sub"]
        # burada tid None ise yeni thread; değilse aynı thread’e devam
        thread_id = save_chat(username, msg, resp, thread_id=tid)

    yeni_oneriler = cevaptan_yeni_oneri(resp)
    puan, oneri    = evaluate_prompt(msg)

    return JSONResponse({
        "message":   msg,
        "response":  resp,
        "thread_id": thread_id,
        "yeni_oneriler": yeni_oneriler,
        "score":     puan,
        "suggestion":oneri
    })




@app.post("/prompt-iyilestir")
async def prompt_iyilestir(mesaj: str = Form(...)):
    yeni = improve_prompt_text(mesaj)
    puan, oneri = evaluate_prompt(mesaj)
    yeni_sorular = cevaptan_yeni_oneri(yeni)
    return {"yeni": yeni, "puan": puan, "oneri": oneri, "yeni_oneriler": yeni_sorular}

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.post("/delete-chat")
async def delete_chat(request: Request):
    form     = await request.form()
    message  = form.get("message")
    response = form.get("response")
    token    = request.session.get("token")
    payload  = decode_token(token) if token else None
    if not payload:
        return RedirectResponse("/login", status_code=303)

    user_id = payload.get("id")
    db = SessionLocal()
    # message+response eşleşen ilk kaydı sil
    chat = (
        db.query(ChatHistory)
          .filter_by(user_id=user_id, message=message, response=response)
          .order_by(ChatHistory.timestamp.asc())
          .first()
    )
    if chat:
        db.delete(chat)
        db.commit()
    db.close()

    return RedirectResponse("/chat", status_code=303)

@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    token = request.session.get("token")
    if not token or not decode_token(token):
        return RedirectResponse("/login", status_code=303)

    payload = decode_token(token)
    username = payload["sub"]

    db = SessionLocal()
    user = db.query(User).filter_by(username=username).first()
    # eğer user bulunamazsa güvenli bir redirect ekleyebilirsiniz

    # Sohbet geçmişini çek
    chats = (
        db.query(ChatHistory)
          .filter_by(user_id=user.id)
          .order_by(ChatHistory.timestamp.asc())
          .all()
    )

    # Ortalama prompt puanı hesapla
    puanlar = []
    for chat in chats:
        if chat.response and chat.response.strip():
            score, _ = evaluate_prompt(chat.message)
            puanlar.append(score)
    ortalama = sum(puanlar) / len(puanlar) if puanlar else 0

    return templates.TemplateResponse("profile.html", {
        "request":       request,
        "user":          user,
        "average_score": round(ortalama, 2),
        "history":       chats
    })

