import os
import ollama

os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"

MODEL_NAME = "qwen2.5:3b"

client = ollama.Client(host="http://127.0.0.1:11434")

# Разрешённые темы для вопросов
ALLOWED_TOPICS = [
    "фитнес", "тренировки", "питание", "здоровье",
    "снижение веса", "набор мышечной массы", "здоровый образ жизни"
]

def check_topic(question: str) -> bool:
    """Проверяет, относится ли вопрос к разрешённым темам"""
    lower_q = question.lower()
    return any(topic in lower_q for topic in ALLOWED_TOPICS)

def generate_answer_with_context(question: str, articles: list, history: list = None):
    # Проверка темы до вызова модели
    if not check_topic(question):
        return (
            "Я могу помогать с вопросами о фитнесе, питании, тренировках, "
            "снижении веса, наборе мышечной массы и здоровом образе жизни. "
            "Этот вопрос не относится к моей теме, поэтому я не могу дать по нему ответ."
        )

    if history is None:
        history = []

    # Ограничиваем контекст 1500 символами
    context_parts = [
        f"Название статьи: {article.title}\n"
        f"Категория: {article.category}\n"
        f"Текст статьи: {article.content[:1500]}"
        for article in articles
    ]
    context = "\n\n".join(context_parts)

    # История последних 6 сообщений
    history_text = ""
    for message in history[-6:]:
        role = "Пользователь" if message.role == "user" else "Ассистент"
        history_text += f"{role}: {message.content}\n"

    prompt = f"""
Ты — русскоязычный ИИ-помощник по фитнесу, питанию и здоровью.
Отвечай строго на русском языке, не используй английские слова или смешанные (например 'balancedное').
Не используй Markdown, списки, *, #, смайлы.
Дай развернутый, но понятный ответ (5-7 предложений).
Учитывай историю диалога и предыдущие уточняющие вопросы.

История диалога:
{history_text}

Контекст:
{context}

Новый вопрос пользователя:
{question}

Ответь именно на новый вопрос пользователя. Если вопрос уточняющий, используй историю, чтобы понять контекст.
"""

    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            options={"num_predict": 300, "num_ctx": 2048, "temperature": 0.1}
        )

        answer = response["message"]["content"].strip()

        # проверка символов других языков
        if any(symbol in answer for symbol in ["你", "好", "是", "的", "了", "在", "人", "有", "中", "国"]):
            return "Произошла ошибка генерации ответа. Пожалуйста, попробуйте задать вопрос ещё раз."

        return answer

    except Exception as e:
        print("Ошибка Ollama:", e)
        return (
            "Я нашёл подходящие материалы, "
            "но сейчас не смог сгенерировать ответ моделью. "
            "Вы можете открыть найденные статьи ниже."
        )