from app.models import Article
from app.services.embedding_service import (
    create_embedding,
    embedding_to_json,
    json_to_embedding,
    cosine_similarity
)


STOP_WORDS = {
    "и", "в", "во", "на", "по", "для", "с", "со", "о", "об",
    "как", "что", "это", "а", "но", "или", "если", "при",
    "мне", "меня", "мой", "моя", "можно", "нужно", "надо",
    "the", "a", "an", "is", "are", "to", "of", "in"
}


def normalize_text(text: str) -> list[str]:
    text = text.lower()

    symbols = ".,!?;:()[]{}«»\"'"
    for symbol in symbols:
        text = text.replace(symbol, " ")

    words = text.split()

    return [
        word for word in words
        if len(word) > 2 and word not in STOP_WORDS
    ]


def create_article_embeddings(db):
    articles = db.query(Article).all()

    for article in articles:
        if article.embedding is None:
            text_for_embedding = (
                f"{article.title}. "
                f"{article.category}. "
                f"{article.content}"
            )

            embedding = create_embedding(text_for_embedding)
            article.embedding = embedding_to_json(embedding)

    db.commit()


def search_articles_by_question(db, question: str, limit: int = 3):
    create_article_embeddings(db)

    question_embedding = create_embedding(question)

    articles = db.query(Article).filter(
        Article.embedding.isnot(None)
    ).all()

    scored_articles = []

    for article in articles:
        article_embedding = json_to_embedding(article.embedding)

        score = cosine_similarity(
            question_embedding,
            article_embedding
        )

        scored_articles.append({
            "article": article,
            "score": score
        })

    scored_articles.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    top_articles = [
        item["article"]
        for item in scored_articles[:limit]
        if item["score"] > 0.25
    ]

    if top_articles:
        return top_articles

    return search_articles_by_keywords(db, question, limit)


def search_articles_by_keywords(db, question: str, limit: int = 3):
    question_words = normalize_text(question)

    if not question_words:
        return []

    articles = db.query(Article).all()

    scored_articles = []

    for article in articles:
        title = article.title.lower()
        content = article.content.lower()
        category = article.category.lower()

        score = 0

        for word in question_words:
            if word in title:
                score += 5
            if word in category:
                score += 3
            if word in content:
                score += 1

        if score > 0:
            scored_articles.append({
                "article": article,
                "score": score
            })

    scored_articles.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return [
        item["article"]
        for item in scored_articles[:limit]
    ]