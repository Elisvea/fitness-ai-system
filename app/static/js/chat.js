let chatHistory = [];
let isWaitingForAnswer = false;

function openChat() {
    document.getElementById("chatPanel").classList.add("show");
    document.getElementById("openChatButton").style.display = "none";

    // Загружаем историю чата из БД при открытии
    loadChatHistory();
}

function closeChat() {
    document.getElementById("chatPanel").classList.remove("show");
    document.getElementById("openChatButton").style.display = "block";
}

// Компактные текстовые ссылки на статьи
function renderSources(sources) {
    const container = document.createElement("div");
    container.className = "chat-sources";

    const title = document.createElement("div");
    title.className = "chat-sources-title";
    title.textContent = "Использованные материалы:";

    container.appendChild(title);

    sources.forEach(source => {
        const link = document.createElement("a");
        link.className = "chat-source-link";
        link.href = `/articles/${source.id}`;
        link.target = "_blank";
        link.textContent = `📄 ${source.title}`;

        container.appendChild(link);
    });

    return container;
}

// Загружаем историю из БД
async function loadChatHistory() {
    try {
        const response = await fetch("/chat/history");
        const history = await response.json();

        chatHistory = history.slice(-20); // максимум 20 последних сообщений

        const messages = document.getElementById("chatMessages");
        messages.innerHTML = "";

        chatHistory.forEach(msg => {
            const div = document.createElement("div");
            div.className = msg.role === "user" ? "user-message" : "bot-message";
            div.textContent = msg.content;
            messages.appendChild(div);
        });

        messages.scrollTop = messages.scrollHeight;
    } catch (error) {
        console.error("Ошибка загрузки истории чата:", error);
    }
}


function formatAnswer(answer) {
    return answer
        .trim()
        .split("\n")
        .filter(line => line.trim() !== "")
        .map(line => {
            const cleanLine = line.trim();

            if (cleanLine.startsWith("•")) {
                return `<div class="answer-list-item">${cleanLine}</div>`;
            }

            return `<p>${cleanLine}</p>`;
        })
        .join("");
}


async function sendMessage() {
    const input = document.getElementById("chatInput");
    const text = input.value.trim();
    if (text === "" || isWaitingForAnswer) return;

    isWaitingForAnswer = true;
    const messages = document.getElementById("chatMessages");

    // Сообщение пользователя
    const userMessage = document.createElement("div");
    userMessage.className = "user-message";
    userMessage.textContent = text;
    messages.appendChild(userMessage);
    input.value = "";

    // Заглушка для бота
    const botMessage = document.createElement("div");
    botMessage.className = "bot-message";
    botMessage.textContent = "ИИ подготавливает ответ...";
    messages.appendChild(botMessage);
    messages.scrollTop = messages.scrollHeight;

    try {
        const response = await fetch("/chat", {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
        message: text,
        history: chatHistory
    })
});


        if (!response.ok) {
            throw new Error(
                `Ошибка сервера: ${response.status}`
            );
        }


        const data = await response.json();


        if (!data || !data.answer) {
            throw new Error(
                "Некорректный ответ сервера"
            );
        }


        botMessage.textContent = "";

        const answerText = document.createElement("div");
        answerText.className = "rag-answer";
        answerText.innerHTML = formatAnswer(data.answer);
        botMessage.appendChild(answerText);

        // Отображение источников в компактном виде
        // Отображение источников только если есть реальный ответ
        if (
            data.found &&
            data.articles &&
            data.articles.length > 0 &&
            !data.answer.includes("не могу дать по нему ответ") &&
            !data.answer.includes("Информация не найдена")
        ) {
            const sourcesBlock = renderSources(data.articles);
            botMessage.appendChild(sourcesBlock);
        }

        // Сохраняем локально и в БД
        chatHistory.push({ role: "user", content: text });
        chatHistory.push({ role: "assistant", content: data.answer });
        if (chatHistory.length > 20) chatHistory = chatHistory.slice(-20);

        messages.scrollTop = messages.scrollHeight;

    } catch (error) {
        console.error("Ошибка:", error);
        botMessage.textContent = "Ошибка соединения с сервером.";
    } finally {
        isWaitingForAnswer = false;
    }
}

// Отправка сообщения по Enter
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("chatInput");
    if (input) {
        input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                sendMessage();
            }
        });
    }
});