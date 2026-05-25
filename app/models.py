from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    embedding = Column(Text, nullable=True)


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    username = Column(String(50))        # username пользователя
    role = Column(String(20))            # "user" или "assistant"
    content = Column(Text)               # текст сообщения
    created_at = Column(DateTime(timezone=True), server_default=func.now())