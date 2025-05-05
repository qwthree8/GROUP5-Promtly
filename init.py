# init_db.py
from database import Base, engine
import models  # modellerin burada import edildiğinden emin ol

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Veritabanı tabloları oluşturuldu.")

if __name__ == "__main__":
    init_db()