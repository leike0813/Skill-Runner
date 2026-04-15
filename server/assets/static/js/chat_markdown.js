(() => {
  "use strict";

  function safeText(value) {
    return typeof value === "string" ? value : "";
  }

  function createRenderer() {
    let parser = null;
    if (window.markdownit) {
      parser = window.markdownit({
        html: false,
        xhtmlOut: false,
        breaks: true,
        langPrefix: "language-",
        linkify: false,
        typographer: false,
        quotes: "\"\"''",
        highlight: null,
      });
      if (window.texmath && window.katex) {
        parser.use(window.texmath, {
          engine: window.katex,
          delimiters: "dollars",
          katexOptions: {
            throwOnError: false,
            output: "htmlAndMath",
            displayMode: false,
          },
        });
      }
    }

    function render(text) {
      if (!parser || typeof text !== "string") {
        return safeText(text);
      }
      try {
        return parser.render(text).trimEnd();
      } catch (error) {
        console.warn("Markdown render error, falling back to plain text:", error);
        return safeText(text);
      }
    }

    function renderInto(element, text, options = {}) {
      if (!(element instanceof HTMLElement)) return "";
      const className = typeof options.className === "string" && options.className.trim()
        ? options.className.trim()
        : "chat-markdown";
      if (className) {
        element.classList.add(className);
      }
      const html = render(text);
      if (parser) {
        element.innerHTML = html;
      } else {
        element.textContent = safeText(text);
      }
      return html;
    }

    return {
      render,
      renderInto,
    };
  }

  window.SkillRunnerChatMarkdown = {
    createRenderer,
  };
})();
