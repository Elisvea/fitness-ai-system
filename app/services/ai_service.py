import os
import ollama


os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"


MODEL_NAME = "qwen2.5:7b"

client = ollama.Client(
    host="http://127.0.0.1:11434"
)


def generate_answer_with_context(
    question: str,
    articles: list,
    history: list = None
):
    if history is None:
        history = []

    context_parts = []

    for article in articles:
        context_parts.append(
            f"Название материала: {article.title}\n"
            f"Категория: {article.category}\n"
            f"Фрагмент материала:\n{article.content[:1200]}"
        )

    context = "\n\n".join(context_parts)

    history_text = ""

    for message in history[-6:]:
        role = "Пользователь"

        if message.role == "assistant":
            role = "Ассистент"

        history_text += f"{role}: {message.content}\n"

    prompt = f"""
Ты — русскоязычный ИИ-помощник по фитнесу, питанию, тренировкам и здоровому образу жизни.

Правила ответа:
1. Отвечай только на русском языке.
2. Отвечай естественно и понятно.
3. Не начинай ответ фразами вроде "Ваш запрос включает" или "В вашем вопросе".
4. Не используй английские слова.
5. Не используй Markdown-разметку, символы *, # и списки.
6. Используй только информацию из найденных материалов.
7. Если в материалах нет ответа, напиши: "Информация не найдена в материалах сайта."
8. Если вопрос уточняющий, используй историю диалога, чтобы понять, о чём идёт речь.
9. Не повторяй предыдущий ответ дословно.
10. Дай ответ в 3–6 предложениях.

История диалога:
{history_text}

Найденные материалы:
{context}

Вопрос пользователя:
{question}

Ответ:
"""

    try:
        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            stream=False,
            options={
                "num_predict": 220,
                "num_ctx": 1536,
                "temperature": 0.1
            }
        )

        answer = response["message"]["content"].strip()

        if any(
            symbol in answer
            for symbol in ["你", "好", "是", "的", "了", "在", "人", "有", "中", "国"]
        ):
            return (
                "Произошла ошибка генерации ответа. "
                "Пожалуйста, попробуйте задать вопрос ещё раз."
            )

        return answer

    except Exception as error:
        print("Ошибка Ollama:", error)

        return (
            "Я нашёл подходящие материалы, "
            "но сейчас не смог сгенерировать ответ моделью. "
            "Проверьте, запущена ли Ollama и доступна ли модель qwen2.5:3b."
        )