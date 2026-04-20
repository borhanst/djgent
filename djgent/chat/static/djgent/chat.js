/* ════════════════════════════════════════
   Djgent Chat — Frontend
   ════════════════════════════════════════ */

const initialMessages = JSON.parse(
    document.getElementById("initial-messages").textContent
);
const initialConversations = JSON.parse(
    document.getElementById("initial-conversations").textContent
);
const welcomeMessage = JSON.parse(
    document.getElementById("welcome-message-data").textContent
);

const config = window.djgentChatConfig;
const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const conversationIdEl = document.getElementById("conversation-id");
const chatTitleEl = document.getElementById("chat-title");
const conversationListEl = document.getElementById("conversation-list");
const composerNoteEl = document.getElementById("composer-note");
const sendButtonEl = formEl ? formEl.querySelector(".send-btn") : null;
const themeToggleEls = document.querySelectorAll("[data-theme-toggle]");
const themeIconEls = document.querySelectorAll("[data-theme-icon]");
const csrfTokenEl = document.querySelector("input[name=csrfmiddlewaretoken]");

const THEME_KEY = "djgent-chat-theme";

function getCsrfToken() {
    return csrfTokenEl ? csrfTokenEl.value : "";
}

// Mobile sidebar
const sidebarToggleEl = document.querySelector("[data-sidebar-toggle]");
const sidebarOverlayEl = document.querySelector("[data-sidebar-overlay]");
const sidebarEl = document.querySelector("[data-sidebar]");

let currentMessages = Array.isArray(initialMessages) ? [...initialMessages] : [];
let isPending = false;

/* ── Helpers ────────────────────────────── */

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

function formatTime(dateString) {
    if (!dateString) return "";
    const date = new Date(dateString);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ── Theme ──────────────────────────────── */

function getStoredTheme() {
    const stored = window.localStorage.getItem(THEME_KEY);
    if (stored === "dark" || stored === "light") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
    document.body.dataset.theme = theme;
    themeIconEls.forEach((el) => {
        el.textContent = theme === "dark" ? "☀" : "☾";
    });
}

function toggleTheme() {
    const next = document.body.dataset.theme === "dark" ? "light" : "dark";
    window.localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
}

/* ── Rendering ──────────────────────────── */

function renderMessage(message) {
    const role = message.role === "human" ? "user" : message.role;
    const roleMap = {
        user: { label: "You", initials: "U" },
        ai: { label: "Assistant", initials: "D" },
        system: { label: "System", initials: "✦" },
    };
    const meta = roleMap[role] || roleMap.ai;
    const time = message.created_at ? formatTime(message.created_at) : "";
    const contentHtml = role === "system"
        ? escapeHtml(message.content)
        : formatMarkdown(message.content);

    return `
        <article class="message ${role}">
            <div class="message-inner">
                <div class="message-avatar" aria-hidden="true">${meta.initials}</div>
                <div class="msg-content">
                    <div class="msg-header">
                        <span class="msg-role">${meta.label}</span>
                        ${time ? `<span class="msg-time">${time}</span>` : ""}
                    </div>
                    <div class="msg-text">${contentHtml}</div>
                </div>
            </div>
        </article>`;
}

function renderMessages(messages) {
    const typingBubble = isPending
        ? `<article class="message ai">
               <div class="message-inner">
                   <div class="message-avatar" aria-hidden="true">D</div>
                   <div class="msg-content">
                       <div class="typing-msg" aria-label="Assistant is typing">
                           <span class="typing-label">Thinking</span>
                           <span class="typing-dots" aria-hidden="true">
                               <span></span><span></span><span></span>
                           </span>
                       </div>
                   </div>
               </div>
           </article>`
        : "";

    if (!messages.length) {
        messagesEl.innerHTML =
            renderMessage({ role: "system", content: welcomeMessage }) + typingBubble;
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return;
    }

    messagesEl.innerHTML = messages.map(renderMessage).join("") + typingBubble;
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderConversationList(conversations, activeId) {
    if (!conversationListEl) return;

    if (!conversations.length) {
        conversationListEl.innerHTML =
            '<p class="empty-state">Your chat history will<br>appear here.</p>';
        return;
    }

    conversationListEl.innerHTML = conversations
        .map((c) => {
            const active = c.id === activeId ? "is-active" : "";
            return `<a class="conversation-item ${active}" href="${config.conversationPathPrefix}${c.id}/" data-conversation-id="${c.id}">
                        <strong>${escapeHtml(c.name)}</strong>
                        <span>${escapeHtml(c.preview || "")}</span>
                    </a>`;
        })
        .join("");
}

/* ── API ────────────────────────────────── */

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

/* ── Pending State ──────────────────────── */

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
            : "AI can make mistakes. Check important info.";
    }
}

/* ── Send Button Active State ───────────── */

function updateSendButtonState() {
    if (!sendButtonEl || !inputEl) return;
    const hasText = inputEl.value.trim().length > 0;
    sendButtonEl.classList.toggle("active", hasText);
}

/* ── Form Submit ────────────────────────── */

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
            const data = await postJson(config.chatApiUrl, {
                message,
                conversation_id: conversationIdEl.value || null,
            });

            currentMessages = [
                ...currentMessages,
                { role: "ai", content: data.message.content },
            ];
            isPending = false;
            renderMessages(currentMessages);

            if (data.conversation_id) {
                conversationIdEl.value = data.conversation_id;
                if (config.historyUpdatesEnabled) {
                    window.history.replaceState(
                        {},
                        "",
                        `${config.conversationPathPrefix}${data.conversation_id}/`
                    );
                }
            }

            if (
                !chatTitleEl.textContent ||
                chatTitleEl.textContent === "New conversation"
            ) {
                chatTitleEl.textContent = message.slice(0, 60);
            }

            renderConversationList(
                data.conversations || [],
                data.conversation_id || null
            );
        } catch (error) {
            currentMessages = [
                ...currentMessages,
                { role: "system", content: error.message },
            ];
            renderMessages(currentMessages);
        } finally {
            isPending = false;
            setPendingState(false);
            inputEl.focus();
        }
    });
}

/* ── Textarea ───────────────────────────── */

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

/* ── New Chat ───────────────────────────── */

document.addEventListener("click", (event) => {
    if (event.target.closest("[data-action='new-chat']")) {
        event.preventDefault();
        handleNewChat();
    }
});

async function handleNewChat() {
    try {
        await postJson(config.newChatUrl, {});
    } catch (_error) {
        // Reset locally.
    }

    conversationIdEl.value = "";
    chatTitleEl.textContent = "New conversation";
    currentMessages = [];
    isPending = false;
    renderMessages(currentMessages);
    if (config.historyUpdatesEnabled) {
        window.history.replaceState({}, "", config.chatBaseUrl);
    }
    inputEl.focus();
    closeMobileSidebar();
}

/* ── Theme Toggle ───────────────────────── */

themeToggleEls.forEach((btn) => {
    btn.addEventListener("click", toggleTheme);
});

/* ── Mobile Sidebar ─────────────────────── */

function openMobileSidebar() {
    if (sidebarEl) sidebarEl.classList.add("is-open");
    if (sidebarOverlayEl) sidebarOverlayEl.classList.add("is-visible");
    document.body.style.overflow = "hidden";
}

function closeMobileSidebar() {
    if (sidebarEl) sidebarEl.classList.remove("is-open");
    if (sidebarOverlayEl) sidebarOverlayEl.classList.remove("is-visible");
    document.body.style.overflow = "";
}

if (sidebarToggleEl) {
    sidebarToggleEl.addEventListener("click", () => {
        const isOpen = sidebarEl && sidebarEl.classList.contains("is-open");
        isOpen ? closeMobileSidebar() : openMobileSidebar();
    });
}

if (sidebarOverlayEl) {
    sidebarOverlayEl.addEventListener("click", closeMobileSidebar);
}

if (conversationListEl) {
    conversationListEl.addEventListener("click", () => {
        if (window.innerWidth <= 768) closeMobileSidebar();
    });
}

window.addEventListener("resize", () => {
    if (window.innerWidth > 768) closeMobileSidebar();
});

/* ── Init ───────────────────────────────── */

applyTheme(getStoredTheme());
renderMessages(initialMessages);
renderConversationList(initialConversations, config.selectedConversationId || null);
updateSendButtonState();
