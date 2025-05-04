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

# ---------- Yapılandırma ----------
load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash-latest")

# ---------- Fonksiyonlar ----------
def _ask(prompt):
    try:
        return model.generate_content(prompt).text.strip()
    except Exception as e:
        return f"[HATA]: {e}"

def improve_prompt_text(text: str):
    return _ask(f"Bu promptu daha net ve etkili hale getir:\n{text}")

def evaluate_prompt(text: str):
    p = "Aşağıdaki promptu 0-100 arası puanla değerlendir ve JSON ver: {score: , suggestion: }\n" + text
    raw = _ask(p)
    try:
        js = re.search(r"\{.*?\}", raw, re.S).group()
        d = json.loads(js)
        return int(d.get("score", 0)), d.get("suggestion", "")
    except:
        return 0, "Puanlama yapılamadı."

def cevaptan_yeni_oneri(cevap):
    p = f"Bu cevaptan sonra sorulabilecek 5 soru üret:\n{cevap}"
    return [s.strip("1234567890.-• ") for s in _ask(p).split("\n") if "?" in s][:5]

def get_example_outputs(sektor):
    p1 = f"{sektor} sektöründe çalışan bir kişi için yapay zekâya sorabileceği sade 5 soru."
    p2 = f"{sektor} sektöründe sık sorulan 4 konu başlığı sade şekilde listele."
    s = [s.strip("1234567890.-• ") for s in _ask(p1).split("\n") if "?" in s][:5]
    k = [k.strip("1234567890.-• ") for k in _ask(p2).split("\n") if k.strip()][:4]
    return s, k

# ---------- FastAPI ayarları ----------
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="super-secret-key")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
templates.env.globals["now"] = datetime.utcnow

# ---------- Rotalar ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    db = SessionLocal()
    try:
        user = authenticate_user(db, username, password)
        if user:
            token = create_access_token({"sub": user.username, "id": user.id})
            request.session["token"] = token
            print("✅ Giriş başarılı! Token:", token[:30], "...")
            return RedirectResponse("/chat", status_code=303)
        print("❌ Giriş başarısız!")
        return templates.TemplateResponse("login.html", {"request": request, "error": "❌ Giriş başarısız"})
    finally:
        db.close()

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    email = form.get("email")
    gender = form.get("gender")

    db = SessionLocal()
    try:
        user = register_user(db, username, password, email, gender)
        token = create_access_token({"sub": user.username, "id": user.id})
        request.session["token"] = token
        print("🆕 Kayıt başarılı:", username)
        return RedirectResponse("/chat", status_code=303)
    except Exception as e:
        msg = "❌ Kayıt başarısız"
        if "UNIQUE constraint" in str(e):
            msg = "❌ Kullanıcı adı veya e-posta zaten var"
        print("❌ Kayıt hatası:", e)
        return templates.TemplateResponse("register.html", {"request": request, "error": msg})
    finally:
        db.close()

@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    token = request.session.get("token")
    print("📦 Session token:", token)

    if not token:
        print("🚫 Token yok, login'e yönlendiriliyor.")
        return RedirectResponse("/login", status_code=303)

    payload = decode_token(token)
    print("🧩 Token payload:", payload)

    if not payload:
        print("🚫 Token geçersiz veya süresi dolmuş.")
        return RedirectResponse("/login", status_code=303)

    username = payload.get("sub")
    print("👤 Kullanıcı adı:", username)

    history = get_chat_history(username)
    print(f"💬 {len(history)} adet geçmiş mesaj bulundu.")

    return templates.TemplateResponse("chat.html", {"request": request, "username": username, "history": history})

@app.post("/chat")
async def chat_post(request: Request):
    form = await request.form()
    token = request.session.get("token")
    payload = decode_token(token) if token else None
    username = payload.get("sub") if payload else None

    message = form.get("message")
    cevap = _ask(message)
    if username:
        save_chat(username, message, cevap)
    return RedirectResponse("/chat", status_code=303)

@app.get("/sektor-ornekleri")
def sektor_ornekleri(sektor: str):
    sorular, konular = get_example_outputs(sektor)
    return {"sorular": sorular, "konular": konular}

@app.get("/logout")
def logout(request: Request):
    request.session.clear()  # Token dahil tüm session verilerini temizle
    return RedirectResponse("/login", status_code=303)

@app.post("/prompt-iyilestir")
async def prompt_iyilestir(mesaj: str = Form(...)):
    yeni = improve_prompt_text(mesaj)
    puan, oneri = evaluate_prompt(mesaj)
    yeni_sorular = cevaptan_yeni_oneri(yeni)
    return {"yeni": yeni, "puan": puan, "oneri": oneri, "yeni_oneriler": yeni_sorular}
