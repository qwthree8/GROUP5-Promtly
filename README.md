
# PromptlyAI

**İş Dünyasında Etkili Yapay Zeka Kullanımı İçin: LLM Destekli Etkileşim Mühendisi**

---

## 🚀 AMACIMIZ

PromptlyAI, yapay zekâ teknolojilerini iş dünyasında etkin şekilde kullanamayan bireyler için yönlendirici, sezgisel ve öğretici bir etkileşim arayüzü sunmayı amaçlamaktadır.

Kullanıcının yazdığı her prompt, büyük dil modeli tarafından analiz edilerek hem kalite puanı hem de gelişim önerisiyle birlikte değerlendirilir. Ayrıca verilen her cevaptan sonra yeni yönlendirici örnek promptlar da otomatik olarak önerilerek etkileşimin sürekliliği ve öğrenme derinliği sağlanır.

Kullanıcıyı pasif tüketicilikten çıkarıp yapay zekâyı iş süreçlerinde etkin biçimde kullanmasını sağlayarak çağın gerisinde kalmasını önlemek; en doğru soruları sorabilen, sektörel bilgi üretimini güçlendiren etkileşimli bir yapıyla profesyonel bir profil oluşturarak yapay zekâ okuryazarlığını yükseltmektir.

Bu sayede, PromptlyAI sadece bir sohbet uygulaması değil, aynı zamanda kullanıcıların yapay zekâyla stratejik düşünmeyi öğrenebildiği bir öğrenme ve üretim asistanı işlevi görür.

---

## 🎯 Temel Özellikler

- **Sektörel Örnekler**  
  - Kullanıcı “Sektör (örn: yazılımcı)” girdiğinde 4 sık sorulan konu başlığı gösterimi  
  - Konuya tıklandığında 6 örnek prompt önerisi  

- **Prompt Değerlendirme & İyileştirme**  
  - Google Gemini ile anlık **0–100** puanlama  
  - JSON formatlı kısa geliştirme önerileri  
  - “⚡ Promptu İyileştir” ile metni daha net, kısa ve etkili hâle getirme  

- **Yönlendirici Yeni Promptlar**  
  - Model cevabına göre 6 yeni soru önerisi  
  - Diyaloğu kesintisiz ileri taşıyan etkileşim zincirleri  

- **Renk Kodlu UI**  
  - 4 konu başlığı butonu farklı renk paletleriyle  
  - Seçilen başlığa göre prompt önerisi butonlarının eş renk teması  
  - Hover animasyonları ve dinamik genişleme  

- **Sohbet Geçmişi & Kaydırma**  
  - Kullanıcı ve Bot mesajlarının scrollable chat penceresinde saklanması  
  - Sayfa yenilese dahi geçmişin korunması (session bazlı)  

---

## 📂 Proje Yapısı
.  
├── auth.py # Kullanıcı kimlik doğrulama & JWT  
├── database.py # SQLAlchemy DB bağlantıları  
├── main.py # FastAPI uygulama ve rotalar  
├── models.py # ORM veri modelleri  
├── requirements.txt # Python bağımlılıkları  
├── static/ # CSS, JS, resimler  
│ └── styles.css  
├── templates/ # Jinja2 HTML şablonları  
│ ├── base.html  
│ ├── chat.html  
│ ├── login.html  
│ └── register.html  
└── README.md


---

## 👥 Proje Ekibi

1. **Aslı Şemşimoğlu**  
   - Bilgisayar Mühendisliği, Afyon Kocatepe Üniversitesi  

2. **Muhammet Seyfi Büyük**  
   - Elektronik Teknolojisi, Afyon Kocatepe Üniversitesi  

4. **Ege Çağın Tepe**  
   - Türk Hava Kurumu Üniversitesi, Elektrik-Elektronik Mühendisliği

5. **Amine Demirbaş**  
   - Atatürk Üniversitesi, Bilgisayar Programcılığı

6. **Döne Beyza Kurt**  
   - Dicle Üniversitesi, Elektrik-Elektronik Mühendisliği

*__init__ ile db oluşur
