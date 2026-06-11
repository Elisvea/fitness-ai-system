import re
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


def add_admin_user():
    db = SessionLocal()

    if not db.query(User).filter(User.username == "admin").first():
        db.add(
            User(
                username="admin",
                email="admin@example.com",
                password="admin",
                role="admin"
            )
        )
        db.commit()

    db.close()


add_admin_user()


app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


@app.get("/")
async def login_page(request: Request):
    return templates.TemplateResponse(
        name="login.html",
        request=request,
        context={}
    )


@app.post("/login")
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    db = SessionLocal()

    user = (
        db.query(User)
        .filter(
            User.username == username,
            User.password == password
        )
        .first()
    )

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
        context={
            "error_message": "Неверный логин или пароль. Проверьте данные и попробуйте снова."
        }
    )


@app.get("/logout")
async def logout_user():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user_role")
    response.delete_cookie("username")
    return response


@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(
        name="register.html",
        request=request,
        context={}
    )


@app.post("/register")
async def register_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    db = SessionLocal()

    existing_user = (
        db.query(User)
        .filter(
            (User.username == username) | (User.email == email)
        )
        .first()
    )

    if existing_user:
        db.close()

        return templates.TemplateResponse(
            name="register.html",
            request=request,
            context={
                "error_message": "Пользователь с таким логином или email уже существует"
            }
        )

    new_user = User(
        username=username,
        email=email,
        password=password,
        role="user"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()

    return RedirectResponse(url="/", status_code=303)


@app.get("/home")
async def home_page(request: Request):
    user_role = request.cookies.get("user_role")

    if user_role == "admin":
        return RedirectResponse(url="/articles", status_code=303)

    username = request.cookies.get("username")

    db = SessionLocal()

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    db.close()

    return templates.TemplateResponse(
        name="home.html",
        request=request,
        context={
            "user_role": user_role,
            "user": user
        }
    )


def calculate_bmi(height: int, weight: int):
    height_m = height / 100
    bmi = weight / (height_m * height_m)
    return round(bmi, 1)


def get_bmi_category(bmi: float):
    if bmi < 18.5:
        return "Недостаточный вес"
    elif bmi < 25:
        return "Нормальный вес"
    elif bmi < 30:
        return "Избыточный вес"
    else:
        return "Ожирение"


def get_available_goals(bmi_category: str):
    goals_by_category = {
        "Недостаточный вес": ["Набор массы", "Поддержание формы"],
        "Нормальный вес": ["Снижение веса", "Набор массы", "Поддержание формы"],
        "Избыточный вес": ["Снижение веса", "Поддержание формы"],
        "Ожирение": ["Снижение веса"]
    }

    return goals_by_category.get(bmi_category, [])


@app.post("/profile/update")
async def update_profile(
    request: Request,
    height: int = Form(...),
    weight: int = Form(...),
    goal: str = Form(...),
    health_restrictions: list[str] = Form([])
):
    username = request.cookies.get("username")

    db = SessionLocal()

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if user:
        bmi = calculate_bmi(height, weight)
        bmi_category = get_bmi_category(bmi)

        available_goals = get_available_goals(bmi_category)

        if goal not in available_goals:
            goal = None

        user.height = height
        user.weight = weight
        user.bmi = str(bmi)
        user.bmi_category = bmi_category
        user.goal = goal

        if health_restrictions:
            user.health_restrictions = ", ".join(health_restrictions)
        else:
            user.health_restrictions = None

        db.commit()

    db.close()

    return RedirectResponse(url="/home", status_code=303)


@app.get("/articles")
async def articles_page(request: Request):
    db = SessionLocal()
    articles = db.query(Article).all()
    db.close()

    user_role = request.cookies.get("user_role")

    return templates.TemplateResponse(
        name="articles.html",
        request=request,
        context={
            "articles": articles,
            "user_role": user_role
        }
    )


@app.get("/articles/{article_id}")
async def article_detail_page(request: Request, article_id: int):
    db = SessionLocal()

    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    db.close()

    if article:
        article.content = markdown.markdown(article.content)

    user_role = request.cookies.get("user_role")

    return templates.TemplateResponse(
        name="article_detail.html",
        request=request,
        context={
            "article": article,
            "user_role": user_role
        }
    )


def find_article_by_bmi_category(db, bmi_category: str):
    category_keywords = {
        "Недостаточный вес": "недостаточ",
        "Нормальный вес": "нормальн",
        "Избыточный вес": "избыточн",
        "Ожирение": "ожирен"
    }

    keyword = category_keywords.get(bmi_category)

    if not keyword:
        return []

    articles = []

    all_articles = db.query(Article).all()

    for article in all_articles:
        title = article.title.lower()

        if keyword in title:
            articles.append(article)

    return articles


def filter_article_by_goal(
    article: Article,
    goal: str
):
    if not goal:
        return article

    sections = {
        "Снижение веса":
            "2.1. Если цель — Снижение веса",

        "Набор массы":
            "2.2. Если цель — Набор массы",

        "Поддержание формы":
            "2.3. Если цель — Поддержание формы"
    }

    start_marker = sections.get(goal)

    if not start_marker:
        return article

    text = article.content

    start = text.find(start_marker)

    if start == -1:
        return article

    markers = list(sections.values())

    ends = []

    for marker in markers:
        if marker == start_marker:
            continue

        pos = text.find(
            marker,
            start + len(start_marker)
        )

        if pos != -1:
            ends.append(pos)

    end = min(ends) if ends else len(text)

    article.content = text[start:end]

    return article

def get_selected_restriction_markers(user_restrictions: str):
    if not user_restrictions:
        return []

    selected_restrictions = [
        restriction.strip()
        for restriction in user_restrictions.split(",")
    ]

    restriction_markers = {
    "Проблемы с коленями": "При проблемах с коленями:",
    "Боли в спине": "При болях в спине:",
    "Сердечно-сосудистые ограничения": "При сердечно-сосудистых заболеваниях:",
    "Сердечно-сосудистые заболевания": "При сердечно-сосудистых заболеваниях:"
}


    return [
        restriction_markers[restriction]
        for restriction in selected_restrictions
        if restriction in restriction_markers
    ]


def extract_text_between_markers(text: str, start_marker: str, end_markers: list[str]):
    start = text.find(start_marker)

    if start == -1:
        return ""

    end_positions = []

    for marker in end_markers:
        position = text.find(
            marker,
            start + len(start_marker)
        )

        if position != -1:
            end_positions.append(position)

    end = min(end_positions) if end_positions else len(text)

    return text[start:end].strip()


def build_restrictions_block(article_content: str, user_restrictions: str):
    selected_markers = get_selected_restriction_markers(user_restrictions)

    if not selected_markers:
        return ""

    correction_block = extract_text_between_markers(
        article_content,
        "2.1.2. Корректировка рекомендаций при наличии ограничений",
        [
            "2.1.3. Что желательно ограничить",
            "2.1.4. Рекомендации по питанию",
            "2.1.5. Вывод"
        ]
    )

    if not correction_block:
        return ""

    load_names = [
        "Ходьба и лёгкий бег",
        "Кардио-тренировки",
        "Умеренные силовые тренировки",
        "Силовые тренировки",
        "Упражнения с собственным весом",
        "Ходьба",
        "Плавание"
    ]

    result = [
        "Корректировка рекомендаций при наличии ограничений:"
    ]

    for load_name in load_names:
        load_start = correction_block.find(load_name)

        if load_start == -1:
            continue

        next_load_positions = []

        for next_load_name in load_names:
            if next_load_name == load_name:
                continue

            position = correction_block.find(
                next_load_name,
                load_start + len(load_name)
            )

            if position != -1:
                next_load_positions.append(position)

        load_end = (
            min(next_load_positions)
            if next_load_positions
            else len(correction_block)
        )

        load_block = correction_block[load_start:load_end]

        selected_parts = []

        for marker in selected_markers:
            restriction_text = extract_text_between_markers(
                load_block,
                marker,
                [
                    "При проблемах с коленями:",
                    "При болях в спине:",
                    "При сердечно-сосудистых заболеваниях:",
                    "Если выбрано несколько ограничений одновременно"
                ]
            )

            if restriction_text:
                selected_parts.append(restriction_text)

        if selected_parts:
            result.append("")
            result.append(load_name)
            result.extend(selected_parts)

    return "\n".join(result)

def extract_section(text: str, start_marker: str, end_markers: list[str]):
    start = text.find(start_marker)

    if start == -1:
        return ""

    end_positions = []

    for marker in end_markers:
        position = text.find(marker, start + len(start_marker))

        if position != -1:
            end_positions.append(position)

    end = min(end_positions) if end_positions else len(text)

    return text[start:end].strip()


def clean_markdown(text: str):
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append("")
            continue

        if re.fullmatch(r"\d+\.\d+\.\d+\.?", stripped):
            continue

        if stripped == "Основные рекомендуемые виды нагрузок":
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    text = text.replace("####", "")
    text = text.replace("###", "")
    text = text.replace("##", "")
    text = text.replace("#", "")

    text = text.replace("**", "")

    text = text.replace("* ", "• ")
    text = text.replace("- ", "• ")

    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def clean_line(line: str):
    return clean_markdown(line).strip()


def remove_first_line(text: str):
    lines = text.splitlines()

    cleaned = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if re.fullmatch(r"\d+\.\d+\.\d+\.", line):
            continue

        cleaned.append(line)

    if cleaned:
        cleaned = cleaned[1:]

    return clean_markdown("\n".join(cleaned))


def get_user_restriction_markers(user_restrictions: str):
    if not user_restrictions:
        return []

    selected = [
        item.strip()
        for item in user_restrictions.split(",")
    ]

    markers = {
        "Проблемы с коленями": "При проблемах с коленями:",
        "Боли в спине": "При болях в спине:",
        "Сердечно-сосудистые заболевания": "При сердечно-сосудистых заболеваниях:"
    }

    return [
        markers[item]
        for item in selected
        if item in markers
    ]


def filter_correction_block(block: str, user_restrictions: str):
    selected_markers = get_user_restriction_markers(user_restrictions)

    if not selected_markers:
        return ""

    all_markers = [
        "При проблемах с коленями:",
        "При болях в спине:",
        "При сердечно-сосудистых заболеваниях:"
    ]

    load_names = [
        "Ходьба и лёгкий бег",
        "Кардио-тренировки",
        "Умеренные силовые тренировки",
        "Силовые тренировки",
        "Упражнения с собственным весом",
        "Ходьба",
        "Плавание"
    ]

    lines = block.splitlines()

    load_indexes = []

    for index, line in enumerate(lines):
        if line.strip() in load_names:
            load_indexes.append(index)

    result = []

    for i, load_index in enumerate(load_indexes):
        load_name = clean_line(lines[load_index])

        next_load_index = (
            load_indexes[i + 1]
            if i + 1 < len(load_indexes)
            else len(lines)
        )

        load_lines = lines[load_index:next_load_index]

        selected_parts = []

        for marker in selected_markers:
            marker_index = None

            for index, line in enumerate(load_lines):
                if clean_line(line) == marker:
                    marker_index = index
                    break

            if marker_index is None:
                continue

            end_index = len(load_lines)

            for index in range(marker_index + 1, len(load_lines)):
                current_line = clean_line(load_lines[index])

                if current_line in all_markers:
                    end_index = index
                    break

                if current_line.startswith("Если выбрано несколько ограничений"):
                    end_index = index
                    break

            selected_parts.extend(load_lines[marker_index:end_index])

        if selected_parts:
            result.append(load_name)
            result.extend(selected_parts)
            result.append("")

    return clean_markdown("\n".join(result))


def filter_limitations_block(block: str, user_restrictions: str):
    selected_markers = get_user_restriction_markers(user_restrictions)

    additional_markers = {
        "При проблемах с коленями:": "Дополнительно при проблемах с коленями:",
        "При болях в спине:": "Дополнительно при болях в спине:",
        "При сердечно-сосудистых заболеваниях:": "Дополнительно при сердечно-сосудистых заболеваниях:"
    }

    selected_additional = [
        additional_markers[marker]
        for marker in selected_markers
        if marker in additional_markers
    ]

    lines = block.splitlines()
    result = []

    for_all_started = False

    for line in lines:
        stripped = clean_line(line)

        if stripped.startswith("Что желательно ограничить"):
            continue

        if stripped == "Для всех пользователей:":
            for_all_started = True
            result.append(stripped)
            continue

        if stripped.startswith("Дополнительно"):
            break

        if for_all_started:
            result.append(line)

    for marker in selected_additional:
        marker_index = None

        for index, line in enumerate(lines):
            if clean_line(line) == marker:
                marker_index = index
                break

        if marker_index is None:
            continue

        result.append("")

        end_index = len(lines)

        for index in range(marker_index + 1, len(lines)):
            if lines[index].strip().startswith("Дополнительно"):
                end_index = index
                break

        result.extend(lines[marker_index:end_index])

    return clean_markdown("\n".join(result))


def build_personal_recommendation(article_content: str, user_restrictions: str, response_mode: str):
    selected_restrictions = []

    if user_restrictions:
        selected_restrictions = [
            item.strip()
            for item in user_restrictions.split(",")
        ]

    correction_markers = {
        "Проблемы с коленями": "Корректировка при проблемах с коленями:",
        "Боли в спине": "Корректировка при болях в спине:",
        "Сердечно-сосудистые заболевания": "Корректировка при сердечно-сосудистых заболеваниях:"
    }

    additional_markers = {
        "Проблемы с коленями": "Дополнительно при проблемах с коленями:",
        "Боли в спине": "Дополнительно при болях в спине:",
        "Сердечно-сосудистые заболевания": "Дополнительно при сердечно-сосудистых заболеваниях:"
    }

    selected_correction_markers = [
        correction_markers[item]
        for item in selected_restrictions
        if item in correction_markers
    ]

    selected_additional_markers = [
        additional_markers[item]
        for item in selected_restrictions
        if item in additional_markers
    ]

    all_correction_markers = list(correction_markers.values())
    all_additional_markers = list(additional_markers.values())

    loads_block = extract_section(
        article_content,
        "Основные рекомендуемые виды нагрузок",
        ["Что желательно ограничить"]
    )

    limitations_block = extract_section(
        article_content,
        "Что желательно ограничить",
        ["Рекомендации по питанию"]
    )

    nutrition_block = extract_section(
        article_content,
        "Рекомендации по питанию",
        ["Вывод"]
    )

    answer_parts = []

    if loads_block and response_mode in ["exercise", "full"]:
        lines = loads_block.splitlines()
        filtered_lines = []
        skip_restriction_block = False

        for line in lines:
            clean = clean_line(line)

            if not clean:
                continue

            if clean in all_correction_markers:
                if clean in selected_correction_markers:
                    skip_restriction_block = False
                    filtered_lines.append(clean)
                else:
                    skip_restriction_block = True
                continue

            if clean.startswith("Нагрузка:"):
                skip_restriction_block = False
                filtered_lines.append(clean)
                continue

            if not skip_restriction_block:
                filtered_lines.append(line)

        answer_parts.append(
            "Подходящие виды нагрузок и упражнения:\n\n" +
            clean_markdown("\n".join(filtered_lines))
        )

    if limitations_block and response_mode in ["exercise", "full"]:
        lines = limitations_block.splitlines()
        filtered_lines = []
        include_block = False

        for line in lines:
            clean = clean_line(line)

            if not clean:
                continue

            if clean.startswith("Что желательно ограничить"):
                continue

            if clean == "Для всех пользователей:":
                include_block = True
                filtered_lines.append(clean)
                continue

            if clean in all_additional_markers:
                if clean in selected_additional_markers:
                    include_block = True
                    filtered_lines.append(clean)
                else:
                    include_block = False
                continue

            if include_block:
                filtered_lines.append(line)

        if filtered_lines:
            answer_parts.append(
                "Что желательно ограничить:\n\n" +
                clean_markdown("\n".join(filtered_lines))
            )

    if nutrition_block and response_mode in ["nutrition", "full"]:
        answer_parts.append(
            "Рекомендации по питанию:\n\n" +
            remove_first_line(nutrition_block)
        )

    answer_parts.append(
        "Представленные рекомендации носят информационный характер и помогают выбрать "
        "подходящие виды физической активности и общие принципы питания с учётом категории ИМТ, "
        "цели и выбранных ограничений здоровья. При наличии выраженного дискомфорта или хронических "
        "заболеваний рекомендуется обратиться к специалисту."
    )

    final_answer = "\n\n".join(answer_parts)
    return clean_markdown(final_answer)


def define_response_mode(message: str):
    message_lower = message.lower()

    exercise_words = [
        "упраж", "трениров", "нагруз", "нагруж",
        "заним", "занят", "кардио", "силов",
        "ходьб", "бег", "плаван", "велотренаж",
        "эллипс", "гимнаст"
    ]

    nutrition_words = [
        "питани", "питат", "рацион", "еда",
        "есть", "калор", "белок", "углевод",
        "жир", "вода", "продукт", "употреб"
    ]

    full_words = [
        "что делать", "что надо", "что необходимо",
        "рекомендац", "поддерживать форму",
        "поддержания формы", "здоровый образ жизни",
        "образ жизни"
    ]

    has_exercise = any(word in message_lower for word in exercise_words)
    has_nutrition = any(word in message_lower for word in nutrition_words)
    has_full = any(word in message_lower for word in full_words)

    if has_exercise and has_nutrition:
        return "full"

    if has_exercise:
        return "exercise"

    if has_nutrition:
        return "nutrition"

    if has_full:
        return "full"

    return "unknown"


def get_requested_goal(message: str):
    message_lower = message.lower()

    if any(word in message_lower for word in ["похуд", "снизить вес", "снижение веса"]):
        return "Снижение веса"

    if any(word in message_lower for word in ["набрать массу", "набор массы", "набрать вес"]):
        return "Набор массы"

    if any(word in message_lower for word in ["поддерживать форму", "поддержание формы", "поддержания формы"]):
        return "Поддержание формы"

    return None


@app.post("/chat")
async def chat(request: Request, chat_request: ChatRequest):
    db = SessionLocal()

    username = request.cookies.get("username")

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )
    
    if not user or not user.bmi_category or not user.goal:
        db.close()

        return {
            "found": False,
            "answer": (
                "Для формирования персональных рекомендаций сначала заполните профиль: "
                "укажите рост, вес, рассчитайте ИМТ и выберите цель."
            ),
            "articles": []
        }

    requested_goal = get_requested_goal(chat_request.message)

    if requested_goal and requested_goal != user.goal:
        available_goals = get_available_goals(user.bmi_category)

        if requested_goal not in available_goals:
            db.close()

            return {
                "found": False,
                "answer": (
                    f"Для вашей категории ИМТ цель «{requested_goal}» недоступна. "
                    f"Система может формировать рекомендации только по доступным целям: "
                    f"{', '.join(available_goals)}."
                ),
                "articles": []
            }

        db.close()

        return {
            "found": False,
            "answer": (
                f"Сейчас в вашем профиле выбрана цель: «{user.goal}». "
                f"Рекомендации формируются с учётом выбранной цели. "
                f"Если вы хотите получать рекомендации для цели «{requested_goal}», "
                f"измените цель в профиле."
            ),
            "articles": []
        }    



    user_context = ""

    if user:
        user_context = (
            f"Данные пользователя:\n"
            f"- Рост: {user.height if user.height else 'не указан'} см\n"
            f"- Вес: {user.weight if user.weight else 'не указан'} кг\n"
            f"- ИМТ: {user.bmi if user.bmi else 'не рассчитан'}\n"
            f"- Категория ИМТ: {user.bmi_category if user.bmi_category else 'не определена'}\n"
            f"- Цель: {user.goal if user.goal else 'не выбрана'}\n"
            f"- Ограничения здоровья: {user.health_restrictions if user.health_restrictions else 'отсутствуют'}\n\n"
        )

    personalized_question = (
        user_context +
        "Вопрос пользователя:\n" +
        chat_request.message
    )

    articles = []

    if user and user.bmi_category:
        articles = find_article_by_bmi_category(
            db,
            user.bmi_category
        )
    else:
        articles = search_articles_by_question(
            db,
            personalized_question,
            limit=1
        )

    filtered_articles = []

    for article in articles:
        if user and user.goal:
            article = filter_article_by_goal(
                article,
                user.goal
            )

        filtered_articles.append(article)

        articles = filtered_articles


    answer = ""
    found_articles = []

    if articles:
        found_articles = [
            {
                "id": article.id,
                "title": article.title
            }
            for article in articles
        ]

        response_mode = define_response_mode(chat_request.message)

        if response_mode == "unknown":
            answer = (
                "Я могу отвечать только на вопросы, связанные с физической активностью, "
                "упражнениями и подходящим питанием."
            )
        else:
            answer = build_personal_recommendation(
                articles[0].content,
                user.health_restrictions,
                response_mode
            )
    else:
        answer = "Информация не найдена по вашему запросу."

    db.close()

    return {
        "found": bool(articles),
        "answer": answer,
        "articles": found_articles
    }


@app.get("/admin/articles/new")
async def new_article_page(request: Request):
    user_role = request.cookies.get("user_role")

    if user_role != "admin":
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        name="admin_article_new.html",
        request=request,
        context={
            "user_role": user_role
        }
    )


@app.post("/admin/articles/new")
async def create_article(
    request: Request,
    title: str = Form(...),
    content: str = Form(...)
):
    user_role = request.cookies.get("user_role")

    if user_role != "admin":
        return RedirectResponse(url="/", status_code=303)

    db = SessionLocal()

    new_article = Article(
        title=title,
        content=content
    )

    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    db.close()

    return RedirectResponse(url="/admin/articles/new", status_code=303)

@app.post("/admin/articles/{article_id}/delete")
async def delete_article(
    request: Request,
    article_id: int
):
    user_role = request.cookies.get("user_role")

    if user_role != "admin":
        return RedirectResponse(
            url="/",
            status_code=303
        )

    db = SessionLocal()

    article = (
        db.query(Article)
        .filter(Article.id == article_id)
        .first()
    )

    if article:
        db.delete(article)
        db.commit()

    db.close()

    return RedirectResponse(
        url="/articles",
        status_code=303
    )
