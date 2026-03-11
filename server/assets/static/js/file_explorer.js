(() => {
  "use strict";

  function safeText(value) {
    return typeof value === "string" ? value : "";
  }

  function parentPath(path) {
    const idx = path.lastIndexOf("/");
    return idx >= 0 ? path.slice(0, idx) : "";
  }

  function hasCollapsedAncestor(path, collapsedSet) {
    let parent = parentPath(path);
    while (parent) {
      if (collapsedSet.has(parent)) return true;
      parent = parentPath(parent);
    }
    return false;
  }

  function formatLabelByType(format, labels) {
    const key = safeText(format).toLowerCase();
    if (labels && typeof labels === "object" && labels[key]) return labels[key];
    return key || "text";
  }

  function renderPreviewPayload(targetEl, relativePath, preview, options = {}) {
    if (!targetEl) return;
    const i18n = options.i18n || {};
    const formatLabels = options.formatLabels || {};
    targetEl.textContent = "";

    const titleEl = document.createElement("div");
    titleEl.className = options.titleClass || "preview-title";
    titleEl.textContent = safeText(relativePath);
    targetEl.appendChild(titleEl);

    const mode = safeText(preview && preview.mode);
    if (mode === "text") {
      const detectedFormat = safeText((preview && preview.detected_format) || "text");
      const metaEl = document.createElement("div");
      metaEl.className = options.metaClass || "preview-meta";
      metaEl.textContent = `${safeText((preview && preview.meta) || "text")} · ${formatLabelByType(detectedFormat, formatLabels)}`;
      targetEl.appendChild(metaEl);

      const renderedHtml = safeText(preview && preview.rendered_html).trim();
      if (renderedHtml) {
        const richEl = document.createElement("div");
        richEl.className = options.richClass || "preview-markdown";
        richEl.innerHTML = renderedHtml;
        targetEl.appendChild(richEl);
        return;
      }

      const pre = document.createElement("pre");
      pre.className = options.preClass || "preview-content";
      if (detectedFormat === "json") {
        const pretty = safeText(preview && preview.json_pretty).trim();
        pre.textContent = pretty || safeText(preview && preview.content);
      } else {
        pre.textContent = safeText(preview && preview.content);
      }
      targetEl.appendChild(pre);
      return;
    }

    if (mode === "too_large") {
      const warn = document.createElement("div");
      warn.className = options.warnClass || "preview-empty";
      warn.textContent = i18n.fileTooLarge || "File too large to preview";
      targetEl.appendChild(warn);
      const meta = document.createElement("div");
      meta.className = options.metaClass || "preview-meta";
      meta.textContent = `${Number((preview && preview.size) || 0)} ${i18n.fileBytes || "bytes"}`;
      targetEl.appendChild(meta);
      return;
    }

    const unsupported = document.createElement("div");
    unsupported.className = options.warnClass || "preview-empty";
    unsupported.textContent = i18n.fileNotPreviewable || "Not previewable";
    targetEl.appendChild(unsupported);
    const meta = document.createElement("div");
    meta.className = options.metaClass || "preview-meta";
    meta.textContent = safeText((preview && preview.meta) || i18n.fileNoInfo || "No information");
    targetEl.appendChild(meta);
  }

  function renderPreviewLoading(targetEl, relativePath, options = {}) {
    if (!targetEl) return;
    const i18n = options.i18n || {};
    targetEl.textContent = "";

    const titleEl = document.createElement("div");
    titleEl.className = options.titleClass || "preview-title";
    titleEl.textContent = safeText(relativePath);
    targetEl.appendChild(titleEl);

    const wrap = document.createElement("div");
    wrap.className = "sr-loading-wrap";
    const spinner = document.createElement("span");
    spinner.className = "sr-spinner";
    spinner.setAttribute("aria-hidden", "true");
    wrap.appendChild(spinner);
    const text = document.createElement("span");
    text.textContent = safeText(i18n.filePreviewLoading) || "Loading preview...";
    wrap.appendChild(text);
    targetEl.appendChild(wrap);
  }

  function mountFileExplorer(options) {
    const treeEl = options.treeEl;
    const previewEl = options.previewEl;
    if (!treeEl || !previewEl) {
      throw new Error("mountFileExplorer requires treeEl and previewEl");
    }

    const i18n = options.i18n || {};
    const indentPx = Number(options.indentPx || 14);
    const defaultCollapsed = options.defaultCollapsed !== false;
    const collapsedSet = new Set();
    const rows = [];

    function renderNoFiles(message) {
      treeEl.textContent = message || i18n.fileTreeNoFiles || "No files.";
    }

    function showPreviewHint() {
      previewEl.innerHTML = `<div class="${options.hintClass || "preview-empty"}">${i18n.fileTreeSelectHint || "Select a file from the left panel to preview."}</div>`;
    }

    function updateTreeVisibility() {
      for (const item of rows) {
        item.row.style.display = hasCollapsedAncestor(item.path, collapsedSet) ? "none" : "";
        if (item.isDir && item.toggleEl) {
          const expanded = !collapsedSet.has(item.path);
          item.toggleEl.textContent = expanded ? "▼" : "▶";
          item.toggleEl.setAttribute("aria-expanded", expanded ? "true" : "false");
        }
      }
    }

    function waitForPaint() {
      if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
        return new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
      }
      return Promise.resolve();
    }

    async function onFileClick(entry) {
      if (typeof options.onOpenFile !== "function") return;
      try {
        renderPreviewLoading(previewEl, safeText(entry && entry.path), {
          ...options.previewOptions,
          i18n,
        });
        await waitForPaint();
        const result = await options.onOpenFile(entry);
        if (!result) return;
        if (result.kind === "html") {
          previewEl.innerHTML = safeText(result.html);
          return;
        }
        if (result.kind === "payload") {
          renderPreviewPayload(
            previewEl,
            safeText(result.relativePath || entry.path),
            result.preview || {},
            {
              ...options.previewOptions,
              i18n,
              formatLabels: options.formatLabels || {},
            },
          );
          return;
        }
      } catch (_error) {
        const cls = options.hintClass || "preview-empty";
        const msg = i18n.fileReadFailed || "Read failed.";
        previewEl.innerHTML = `<div class="${cls}">${msg}</div>`;
      }
    }

    function renderTree(entries) {
      treeEl.textContent = "";
      rows.length = 0;
      collapsedSet.clear();
      if (!Array.isArray(entries) || entries.length === 0) {
        renderNoFiles();
        return;
      }

      for (const entry of entries) {
        const row = document.createElement("div");
        row.className = options.rowClass || "file-entry";
        const depth = Number(entry && entry.depth ? entry.depth : 0);
        row.style.paddingLeft = `${Math.max(0, depth) * indentPx}px`;

        const isDir = Boolean(entry && entry.is_dir);
        const path = safeText(entry && entry.path);
        const name = safeText((entry && (entry.name || entry.path)) || "");

        let toggleEl = null;
        if (isDir) {
          toggleEl = document.createElement("button");
          toggleEl.type = "button";
          toggleEl.className = options.toggleClass || "tree-toggle-btn";
          toggleEl.textContent = "▶";
          toggleEl.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (collapsedSet.has(path)) {
              collapsedSet.delete(path);
            } else {
              collapsedSet.add(path);
            }
            updateTreeVisibility();
          });
          row.appendChild(toggleEl);
          const label = document.createElement("span");
          label.className = options.dirClass || "";
          label.textContent = `📁 ${name}/`;
          row.appendChild(label);
          if (defaultCollapsed && path) collapsedSet.add(path);
        } else {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = options.fileButtonClass || "";
          btn.textContent = `📄 ${name}`;
          btn.addEventListener("click", () => onFileClick({ ...entry, path }));
          row.appendChild(btn);
        }

        treeEl.appendChild(row);
        rows.push({ row, path, isDir, toggleEl });
      }
      updateTreeVisibility();
    }

    async function load() {
      if (typeof options.getEntries !== "function") {
        renderNoFiles(i18n.fileTreeUnavailable || "File tree unavailable.");
        return;
      }
      treeEl.textContent = i18n.fileTreeLoading || "Loading...";
      showPreviewHint();
      try {
        const entries = await options.getEntries();
        renderTree(Array.isArray(entries) ? entries : []);
      } catch (_error) {
        renderNoFiles(i18n.fileTreeUnavailable || "File tree unavailable.");
      }
    }

    return {
      load,
      renderPreviewPayload: (relativePath, preview) =>
        renderPreviewPayload(previewEl, relativePath, preview, {
          ...options.previewOptions,
          i18n,
          formatLabels: options.formatLabels || {},
        }),
    };
  }

  window.SkillRunnerFileExplorer = {
    mountFileExplorer,
    renderPreviewPayload,
  };
})();
