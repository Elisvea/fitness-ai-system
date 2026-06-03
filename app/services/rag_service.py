from types import SimpleNamespace

import chromadb

from app.models import Article
from app.services.embedding_service import (
    create_embedding,
    create_embeddings,
    split_text_into_chunks
)


CHROMA_PATH = "app/chroma_db"
COLLECTION_NAME = "fitness_materials"

MAX_DISTANCE = 0.65


chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={
        "hnsw:space": "cosine"
    }
)


def index_articles(db):
    articles = db.query(Article).all()

    ids = []
    documents = []
    metadatas = []

    for article in articles:
        full_text = (
            f"Название: {article.title}\n"
            f"{article.content}"
        )

        chunks = split_text_into_chunks(full_text)

        for index, chunk in enumerate(chunks):
            ids.append(f"article_{article.id}_chunk_{index}")
            documents.append(chunk)
            metadatas.append({
                "article_id": article.id,
                "title": article.title,
                "chunk_index": index
            })

    if not documents:
        return

    embeddings = create_embeddings(documents)

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings
    )


def search_articles_by_question(db, question: str, limit: int = 3):
    index_articles(db)

    question_embedding = create_embedding(question)

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=8,
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    found_articles = {}

    for document, metadata, distance in zip(documents, metadatas, distances):
        if distance > MAX_DISTANCE:
            continue

        article_id = metadata["article_id"]

        if article_id not in found_articles:
            found_articles[article_id] = {
                "id": article_id,
                "title": metadata["title"],
                "chunks": []
            }

        found_articles[article_id]["chunks"].append(document)

    result = []

    for article_data in found_articles.values():
        result.append(
            SimpleNamespace(
                id=article_data["id"],
                title=article_data["title"],
                category="Статья",
                content="\n\n".join(article_data["chunks"])
            )
        )

        if len(result) >= limit:
            break

    return result