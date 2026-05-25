import markdown

from pydantic import BaseModel
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import engine, SessionLocal
from app.models import Base, User, Article

from app.services.rag_service import search_articles_by_question
from app.services.ai_service import generate_answer_with_context

Base.metadata.create_all(bind=engine)

# Тестовые данные 
def add_test_articles():
    db = SessionLocal()
    if db.query(Article).count() == 0:
        articles = [
            Article(
                title="Основы правильного питания",
                content="Правильное питание помогает поддерживать здоровье, энергию и нормальный обмен веществ. В рационе должны быть белки, жиры, углеводы, витамины и достаточное количество воды.",
                category="Питание"
            ),
            Article(
                title="Польза регулярных тренировок",
                content="Регулярные тренировки укрепляют мышцы, улучшают работу сердца, повышают выносливость и помогают поддерживать хорошее самочувствие.",
                category="Тренировки"
            ),
            Article(
                title="Кардио для здоровья",
                content="Кардиотренировки помогают развивать выносливость, укрепляют сердечно-сосудистую систему и способствуют снижению лишнего веса.",
                category="Тренировки"
            )
        ]
        db.add_all(articles)
        db.commit()
    db.close()

def add_admin_user():
    db = SessionLocal()
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(
            username="admin",
            email="admin@example.com",
            password="admin",
            role="admin"
        ))
        db.commit()
    db.close()

add_test_articles()
add_admin_user()

# FastAPI 
app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

#  Chat models 
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []

# LOGIN
@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse(
        name="login.html",
        request=request,
        context={}
    )

@app.post("/login")
async def login_user(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username, User.password == password).first()
    db.close()

    if user:
        if user.role == "admin":
            response = RedirectResponse(url="/articles", status_code=303)
        else:
            response = RedirectResponse(url="/home", status_code=303)

        response.set_cookie("user_role", user.role)
        response.set_cookie("username", user.username)
        return response

    return templates.TemplateResponse(
        name="login.html",
        request=request,
        context={"error_message": "Неверный логин или пароль. Проверьте данные и попробуйте снова."}
    )

@app.get("/logout")
async def logout_user():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user_role")
    response.delete_cookie("username")
    return response

#  REGISTER 
@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(
        name="register.html",
        request=request,
        context={}
    )

@app.post("/register")
async def register_user(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    db = SessionLocal()

    # Проверяем существующего пользователя
    existing_user = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if existing_user:
        db.close()
        return templates.TemplateResponse(
            name="register.html",
            request=request,
            context={"error_message": "Пользователь с таким логином или email уже существует"}
        )

    # Создаем нового пользователя
    new_user = User(username=username, email=email, password=password, role="user")
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()

    return RedirectResponse(url="/", status_code=303)

#  HOME 
@app.get("/home")
async def home_page(request: Request):
    user_role = request.cookies.get("user_role")
    if user_role == "admin":
        return RedirectResponse(url="/articles", status_code=303)
    return templates.TemplateResponse(
        name="home.html",
        request=request,
        context={"user_role": user_role}
    )

# ARTICLES
@app.get("/articles")
async def articles_page(request: Request):
    db = SessionLocal()
    articles = db.query(Article).all()
    db.close()
    user_role = request.cookies.get("user_role")
    return templates.TemplateResponse(
        name="articles.html",
        request=request,
        context={"articles": articles, "user_role": user_role}
    )

@app.get("/articles/{article_id}")
async def article_detail_page(request: Request, article_id: int):
    db = SessionLocal()
    article = db.query(Article).filter(Article.id == article_id).first()
    db.close()
    if article:
        article.content = markdown.markdown(article.content)
    user_role = request.cookies.get("user_role")
    return templates.TemplateResponse(
        name="article_detail.html",
        request=request,
        context={"article": article, "user_role": user_role}
    )


#  CHAT 
@app.post("/chat")
async def chat(request: ChatRequest):
    db = SessionLocal()
    search_query = request.message

    # Ищем релевантные статьи
    articles = search_articles_by_question(db, search_query, limit=3)

    answer = ""
    found_articles = []

    if articles:
        # Сохраняем только найденные статьи для вывода источников
        found_articles = [{"id": a.id, "title": a.title, "category": a.category} for a in articles]

        # Генерация ответа с контекстом последних 6 сообщений
        answer = generate_answer_with_context(request.message, articles, request.history[-6:])
    else:
        # Если статьи не найдены, модель отвечает на основе истории, если есть
        answer = "Информация не найдена по вашему запросу."

    db.close()

    return {
        "found": bool(articles),
        "answer": answer,
        "articles": found_articles
    }

# ADMIN ARTICLES
@app.get("/admin/articles/new")
async def new_article_page(request: Request):
    user_role = request.cookies.get("user_role")
    if user_role != "admin":
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        name="admin_article_new.html",
        request=request,
        context={"user_role": user_role}
    )

@app.post("/admin/articles/new")
async def create_article(request: Request, title: str = Form(...), category: str = Form(...), content: str = Form(...), source_url: str = Form("")):
    user_role = request.cookies.get("user_role")
    if user_role != "admin":
        return RedirectResponse(url="/", status_code=303)

    db = SessionLocal()
    new_article = Article(title=title, category=category, content=content, source_url=source_url if source_url else None, embedding=None)
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    db.close()

    return RedirectResponse(url="/admin/articles/new", status_code=303)