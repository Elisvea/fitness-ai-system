import os
import ollama


os.environ["NO_PROXY"] = "localhost,127.0.0.1"
os.environ["no_proxy"] = "localhost,127.0.0.1"


MODEL_NAME = "qwen2.5:3b"

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

    profile_text = ""
    real_question = question

    if "Вопрос пользователя:" in question:
        parts = question.split("Вопрос пользователя:", 1)
        profile_text = parts[0].strip()
        real_question = parts[1].strip()

    print("\n=== PROFILE ===")
    print(profile_text)

    print("\n=== QUESTION ===")
    print(real_question)
   
    
    context_parts = []

    for article in articles:
        context_parts.append(
            f"""
Название материала:
{article.title}

Содержание:
{article.content}
"""
        )

    context = "\n\n".join(context_parts)


    history_text = ""

    for message in history[-3:]:
        role = (
            "Пользователь"
            if message.role == "user"
            else "Ассистент"
        )

        history_text += (
            f"{role}: "
            f"{message.content}\n"
        )
    prompt = f"""
Ты — ИИ-ассистент системы поддержки здорового образа жизни.

Используй только переданный контекст.

Запрещено:

— придумывать рекомендации;
— менять упражнения;
— менять нагрузки;
— добавлять новые ограничения;
— использовать знания вне контекста.

Если информации недостаточно —
сообщи об этом.

Если вопрос не относится к:

— физической активности;
— упражнениям;
— питанию;
— здоровому образу жизни,

ответь строго:

Я могу отвечать только на вопросы, связанные с физической активностью, упражнениями и подходящим питанием.

Контекст:

{context}

История:

{history_text}

Вопрос:

{real_question}

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
                "num_predict": 600,
                "num_ctx": 8192,
                "temperature": 0
            }
        )

        answer = (
            response["message"]["content"]
            .replace("**", "")
            .replace("#", "")
            .strip()
        )

        if len(answer) < 40:
            return (
                "Не удалось сформировать развёрнутый ответ. "
                "Попробуйте уточнить вопрос."
            )

        return answer

    except Exception as error:
        print(error)

        return (
            "Сейчас не удалось сформировать ответ. "
            "Попробуйте повторить запрос."
        )