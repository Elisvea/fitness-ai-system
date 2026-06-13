from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)

    height = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)
    bmi = Column(String, nullable=True)
    bmi_category = Column(String, nullable=True)
    goal = Column(String, nullable=True)
    health_restrictions = Column(Text, nullable=True)


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)



class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    username = Column(String(50))        # username пользователя
    role = Column(String(20))            # "user" или "assistant"
    content = Column(Text)               # текст сообщения
    created_at = Column(DateTime(timezone=True), server_default=func.now())