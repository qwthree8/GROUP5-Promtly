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
    # Ask for exactly 6 simple questions
    p = (
        f"“{topic}” hakkında, sırf kısa sorular olarak, "
        "numaralandırmadan ve maddelemeden, tam **6 soru** üret. "
        "Her soru en fazla 15 kelime olsun."
    )
    out = _ask(p).split("\n")
    qs = [s.strip(" -•1234567890.") for s in out if s.strip()][:6]
    if len(qs) < 6:
        qs += ["Örnek üretilemedi."] * (6 - len(qs))
    return qs

def sektor_sik_sorular(sektor: str) -> list[str]:
    # Ask only for 4 short topic titles
    p = (
        f"“{sektor}” sektöründe en sık sorulan sadece **4 başlık** yaz. "
        "Başlıklar 3–5 kelime arasında olsun, maddeleme veya numaralama yok."
    )
    out = _ask(p).split("\n")
    ks = [s.strip(" -•1234567890.") for s in out if s.strip()][:4]
    if len(ks) < 4:
        ks += ["Konu üretilmedi"] * (4 - len(ks))
    return ks

def cevaptan_yeni_oneri(cevap: str) -> list[str]:
    p = (
        f"Yukarıdaki cevaba dayanarak, sırf kısa sorular olarak **5 yeni** "
        "yönlendirici soru üret. Her soru 10 kelimeyi geçmesin."
    )
    out = _ask(p).split("\n")
    qs = [s.strip(" -•1234567890.") for s in out if s.strip()][:5]
    if not qs:
        qs = ["Devam önerisi yok"]
    return qs

def improve_prompt_text(text: str) -> str:
    return _ask(f"Bu promptu daha net, kısa ve etkili hale getir:\n\n{text}")

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
    return RedirectResponse("/login")

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

@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    token = request.session.get("token")
    if not token or not decode_token(token):
        return RedirectResponse("/login", status_code=303)
    user = decode_token(token)["sub"]
    history = get_chat_history(user)
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "history": history,
        "initialTopics": sektor_sik_sorular(""),  # will show 4 placeholder topics
        "initialQuestions": []                     # no prompts yet
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
    msg = data.get("message", "")
    resp = _ask(msg)

    # 1) Sohbet geçmişine kaydet
    token = request.session.get("token")
    if token and decode_token(token):
        save_chat(decode_token(token)["sub"], msg, resp)

    # 2) Yeni yönlendirici sorular
    yeni_oneriler = cevaptan_yeni_oneri(resp)

    # 3) Prompt değerlendirme
    puan, oneri = evaluate_prompt(msg)

    return JSONResponse({
        "message": msg,
        "response": resp,
        "yeni_oneriler": yeni_oneriler,
        "score": puan,
        "suggestion": oneri
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
