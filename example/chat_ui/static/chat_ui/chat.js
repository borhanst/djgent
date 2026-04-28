/* Example Chat UI */

const initialMessages = JSON.parse(
    document.getElementById("initial-messages").textContent
);
const initialConversations = JSON.parse(
    document.getElementById("initial-conversations").textContent
);

const config = window.djgentChatConfig;
const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const conversationIdEl = document.getElementById("conversation-id");
const chatTitleEl = document.getElementById("chat-title");
const conversationListEl = document.getElementById("conversation-list");
const composerNoteEl = document.getElementById("composer-note");
const sendButtonEl = formEl ? formEl.querySelector(".send-button") : null;
const csrfTokenEl = document.querySelector("input[name=csrfmiddlewaretoken]");

function getCsrfToken() {
    return csrfTokenEl ? csrfTokenEl.value : "";
}

let currentMessages = Array.isArray(initialMessages) ? [...initialMessages] : [];
let isPending = false;

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatMarkdown(text) {
    let formatted = escapeHtml(text);
    formatted = formatted.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    formatted = formatted.split('\n\n').map(p => `<p>${p}</p>`).join('');
    formatted = formatted.replace(/\n/g, '<br>');
    return formatted;
}

function renderMessage(message) {
    const role = message.role === "human" ? "user" : message.role;
    const badgeMap = {
        user: "U",
        ai: "D",
        system: "✦",
    };
    const badge = badgeMap[role] || "D";
    const contentHtml = role === "system"
        ? escapeHtml(message.content)
        : formatMarkdown(message.content);

    return `<article class="message ${role}">
        <div class="message-inner">
            <div class="message-badge">${badge}</div>
            <div class="message-content">${contentHtml}</div>
        </div>
    </article>`;
}

function renderMessages(messages) {
    const typingBubble = isPending
        ? `<article class="message ai">
               <div class="message-inner">
                   <div class="typing-message" aria-label="Assistant is typing">
                       <span class="typing-label">Thinking</span>
                       <span class="typing-dots" aria-hidden="true">
                           <span></span><span></span><span></span>
                       </span>
                   </div>
               </div>
           </article>`
        : "";

    if (!messages.length) {
        messagesEl.innerHTML =
            `<article class="message system"><div class="message-inner"><div class="message-badge">✦</div><div class="message-content">Start with a question. Conversation history is stored with djgent's database memory backend.</div></div></article>` +
            typingBubble;
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return;
    }

    messagesEl.innerHTML = messages.map(renderMessage).join("") + typingBubble;
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderConversationList(conversations, activeId) {
    if (!conversations.length) {
        conversationListEl.innerHTML = `<p class="empty-state">Your chat history will appear here.</p>`;
        return;
    }

    conversationListEl.innerHTML = conversations
        .map((c) => {
            const active = c.id === activeId ? "is-active" : "";
            return `<a class="conversation-item ${active}" href="/chat/${c.id}/" data-conversation-id="${c.id}">
                        <strong>${escapeHtml(c.name)}</strong>
                        <span>${escapeHtml(c.preview)}</span>
                    </a>`;
        })
        .join("");
}

function appendAssistantDelta(delta) {
    const lastMessage = currentMessages[currentMessages.length - 1];
    if (lastMessage && lastMessage.role === "ai" && lastMessage.isStreaming) {
        lastMessage.content = `${lastMessage.content || ""}${delta}`;
        renderMessages(currentMessages);
        return;
    }

    currentMessages = [
        ...currentMessages,
        { role: "ai", content: delta, isStreaming: true },
    ];
    renderMessages(currentMessages);
}

function finishAssistantDraft(content) {
    const lastMessage = currentMessages[currentMessages.length - 1];
    if (lastMessage && lastMessage.role === "ai") {
        lastMessage.content = content;
        delete lastMessage.isStreaming;
    } else {
        currentMessages = [...currentMessages, { role: "ai", content }];
    }
    renderMessages(currentMessages);
}

async function postJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed.");
    return data;
}

function parseSseEvent(rawEvent) {
    const event = { type: "message", data: "" };
    rawEvent.split("\n").forEach((line) => {
        if (line.startsWith("event:")) {
            event.type = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
            event.data += line.slice(5).trim();
        }
    });
    return event;
}

async function postStream(url, payload, onEvent) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ ...payload, stream: true }),
    });

    if (!response.body) {
        throw new Error("Streaming is not supported by this browser.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const rawEvent of events) {
            if (!rawEvent.trim()) continue;
            const parsed = parseSseEvent(rawEvent);
            const data = parsed.data ? JSON.parse(parsed.data) : {};
            onEvent(parsed.type, data);
        }

        if (done) break;
    }

    if (!response.ok) {
        throw new Error("Request failed.");
    }
}

function setPendingState(pending) {
    if (sendButtonEl) {
        sendButtonEl.disabled = pending;
        sendButtonEl.classList.toggle("is-loading", pending);
        sendButtonEl.classList.toggle("active", !pending);
    }
    if (inputEl) inputEl.disabled = pending;
    if (composerNoteEl) {
        composerNoteEl.textContent = pending
            ? "Waiting for response..."
            : "Shift+Enter for a new line.";
    }
}

function updateSendButtonState() {
    if (!sendButtonEl || !inputEl) return;
    sendButtonEl.classList.toggle("active", inputEl.value.trim().length > 0);
}

if (formEl) {
    formEl.addEventListener("submit", async (event) => {
        event.preventDefault();

        const message = inputEl.value.trim();
        if (!message) return;

        currentMessages = [...currentMessages, { role: "human", content: message }];
        inputEl.value = "";
        inputEl.style.height = "auto";
        updateSendButtonState();
        isPending = true;
        renderMessages(currentMessages);
        setPendingState(true);

        try {
            let finalData = null;
            const payload = {
                message,
                conversation_id: conversationIdEl.value || null,
            };

            if (config.streamingEnabled) {
                await postStream(config.chatApiUrl, payload, (eventType, data) => {
                    if (eventType === "message.delta") {
                        isPending = false;
                        appendAssistantDelta(data.delta || "");
                        return;
                    }

                    if (eventType === "message.complete") {
                        isPending = false;
                        finishAssistantDraft(data.content || "");
                        return;
                    }

                    if (eventType === "run.end") {
                        finalData = data;
                        return;
                    }

                    if (eventType === "error") {
                        throw new Error(data.error || "Streaming failed.");
                    }
                });
            } else {
                finalData = await postJson(config.chatApiUrl, payload);
                currentMessages = [
                    ...currentMessages,
                    { role: "ai", content: finalData.message.content },
                ];
            }

            isPending = false;
            renderMessages(currentMessages);

            if (finalData && finalData.conversation_id) {
                conversationIdEl.value = finalData.conversation_id;
            }

            if (!chatTitleEl.textContent || chatTitleEl.textContent === "New conversation") {
                chatTitleEl.textContent = message.slice(0, 60);
            }

            if (finalData) {
                renderConversationList(
                    finalData.conversations || [],
                    finalData.conversation_id || null
                );
            }
            if (finalData && finalData.conversation_id) {
                window.history.replaceState({}, "", `/chat/${finalData.conversation_id}/`);
            }
        } catch (error) {
            const lastMessage = currentMessages[currentMessages.length - 1];
            if (lastMessage && lastMessage.role === "ai" && lastMessage.isStreaming) {
                delete lastMessage.isStreaming;
            }
            currentMessages = [...currentMessages, { role: "system", content: error.message }];
            renderMessages(currentMessages);
        } finally {
            isPending = false;
            setPendingState(false);
            inputEl.focus();
        }
    });
}

if (inputEl) {
    inputEl.addEventListener("input", () => {
        inputEl.style.height = "auto";
        inputEl.style.height = `${Math.min(inputEl.scrollHeight, 180)}px`;
        updateSendButtonState();
    });

    inputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (formEl) formEl.requestSubmit();
        }
    });
}

document.addEventListener("click", (event) => {
    if (event.target.closest("[data-action='new-chat']")) {
        event.preventDefault();
        handleNewChat();
    }
});

async function handleNewChat() {
    let data = null;
    try {
        data = await postJson(config.newChatUrl, {});
    } catch (_error) {
        data = null;
    }

    if (data && data.redirect_url) {
        window.location.assign(data.redirect_url);
        return;
    }

    conversationIdEl.value = data && data.conversation_id ? data.conversation_id : "";
    chatTitleEl.textContent = "New conversation";
    currentMessages = [];
    isPending = false;
    renderMessages(currentMessages);
    if (data) {
        renderConversationList(data.conversations || [], data.conversation_id || null);
    }
    window.history.replaceState({}, "", data && data.redirect_url ? data.redirect_url : "/");
    inputEl.focus();
}

renderMessages(initialMessages);
renderConversationList(initialConversations, config.selectedConversationId || null);
updateSendButtonState();
