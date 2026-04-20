(function () {
    const bubbles = document.querySelectorAll("[data-djgent-chat-bubble]");
    const closeDurationMs = 240;
    const themeKey = "djgent-chat-theme";

    function getStoredTheme() {
        const storedTheme = window.localStorage.getItem(themeKey);
        if (storedTheme === "dark" || storedTheme === "light") {
            return storedTheme;
        }
        return "light";
    }

    bubbles.forEach((bubble) => {
        const openButton = bubble.querySelector("[data-djgent-chat-open]");
        const closeButton = bubble.querySelector("[data-djgent-chat-close]");
        const themeButton = bubble.querySelector("[data-theme-toggle]");
        const themeIcon = bubble.querySelector("[data-theme-icon]");
        const overlay = bubble.querySelector("[data-djgent-chat-overlay]");
        const panel = bubble.querySelector("[data-djgent-chat-panel]");
        const frame = bubble.querySelector("[data-djgent-chat-frame]");
        let closeTimerId = null;

        if (
            !openButton ||
            !closeButton ||
            !themeButton ||
            !themeIcon ||
            !overlay ||
            !panel ||
            !frame
        ) {
            return;
        }

        function syncTheme(theme) {
            document.body.dataset.theme = theme;
            themeIcon.textContent = theme === "dark" ? "☀" : "☾";
            themeButton.setAttribute(
                "aria-label",
                theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            );
            themeButton.setAttribute(
                "title",
                theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            );

            try {
                const frameDoc = frame.contentWindow?.document;
                if (frameDoc?.body) {
                    frameDoc.body.dataset.theme = theme;
                }
            } catch (_error) {
                // Ignore iframe sync issues until the frame is available.
            }
        }

        function toggleTheme() {
            const nextTheme = getStoredTheme() === "dark" ? "light" : "dark";
            window.localStorage.setItem(themeKey, nextTheme);
            syncTheme(nextTheme);
        }

        function setOpenState(isOpen) {
            if (isOpen) {
                if (closeTimerId) {
                    window.clearTimeout(closeTimerId);
                    closeTimerId = null;
                }
                bubble.classList.remove("is-closing");
                panel.hidden = false;
                overlay.hidden = false;
                panel.removeAttribute("inert");
                panel.setAttribute("aria-hidden", "false");
                openButton.setAttribute("aria-expanded", "true");
                document.body.classList.add("djgent-chat-bubble-open");

                requestAnimationFrame(() => {
                    bubble.classList.add("is-open");
                });

                if (!frame.getAttribute("src")) {
                    frame.setAttribute("src", frame.dataset.src || "");
                }
                closeButton.focus();
                return;
            }

            bubble.classList.remove("is-open");
            bubble.classList.add("is-closing");
            panel.setAttribute("aria-hidden", "true");
            panel.setAttribute("inert", "");
            openButton.setAttribute("aria-expanded", "false");
            document.body.classList.remove("djgent-chat-bubble-open");

            if (closeTimerId) {
                window.clearTimeout(closeTimerId);
            }
            closeTimerId = window.setTimeout(() => {
                panel.hidden = true;
                overlay.hidden = true;
                bubble.classList.remove("is-closing");
                closeTimerId = null;
            }, closeDurationMs);

            openButton.focus();
        }

        openButton.addEventListener("click", () => {
            setOpenState(true);
        });

        themeButton.addEventListener("click", () => {
            toggleTheme();
        });

        closeButton.addEventListener("click", () => {
            setOpenState(false);
        });

        overlay.addEventListener("click", () => {
            setOpenState(false);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && !panel.hidden) {
                setOpenState(false);
            }
        });

        frame.addEventListener("load", () => {
            syncTheme(getStoredTheme());
        });

        syncTheme(getStoredTheme());
    });
})();
