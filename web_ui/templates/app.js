function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function highlightCode(rawCode) {
  const escaped = escapeHtml(rawCode);
  const pattern = /(#.*$|\/\/.*$)|(&quot;[^&]*?&quot;|&#39;[^&]*?&#39;)|\b(function|def|class|import|from|return|if|elif|else|for|while|const|let|var|async|await|try|except|catch|finally|True|False|None|null|true|false|new|public|private|static|void|as|with)\b|\b(\d+(?:\.\d+)?)\b/gm;
  return escaped.replace(pattern, (match, comment, string, keyword, number) => {
    if (comment !== undefined) return `<span class="tok-comment">${comment}</span>`;
    if (string !== undefined) return `<span class="tok-string">${string}</span>`;
    if (keyword !== undefined) return `<span class="tok-keyword">${keyword}</span>`;
    if (number !== undefined) return `<span class="tok-number">${number}</span>`;
    return match;
  });
}

function inlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  return html;
}

function renderMarkdownTable(rows) {
  const dataRows = rows.filter((r) => !/^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(r));
  if (!dataRows.length) return "";
  const parsed = dataRows.map((r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()));
  const [headerRow, ...bodyRows] = parsed;
  let html = '<table class="md-table"><thead><tr>' + headerRow.map((h) => `<th>${inlineMarkdown(h)}</th>`).join("") + "</tr></thead><tbody>";
  bodyRows.forEach((row) => {
    html += "<tr>" + row.map((c) => `<td>${inlineMarkdown(c)}</td>`).join("") + "</tr>";
  });
  html += "</tbody></table>";
  return html;
}

function renderMarkdown(rawText) {
  const lines = rawText.split("\n");
  let html = "";
  let inCodeBlock = false;
  let codeLang = "";
  let codeBuffer = [];
  let inTable = false;
  let tableRows = [];
  let listBuffer = [];
  let listType = null;

  function flushList() {
    if (listBuffer.length) {
      const tag = listType === "ol" ? "ol" : "ul";
      html += `<${tag}>` + listBuffer.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("") + `</${tag}>`;
      listBuffer = [];
      listType = null;
    }
  }
  function flushTable() {
    if (tableRows.length) {
      html += renderMarkdownTable(tableRows);
      tableRows = [];
    }
    inTable = false;
  }

  for (const line of lines) {
    const fenceMatch = line.match(/^\s*```(\w*)\s*$/);
    if (fenceMatch) {
      if (inCodeBlock) {
        html += `<pre class="code-block"><code>${highlightCode(codeBuffer.join("\n"))}</code></pre>`;
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        flushList();
        flushTable();
        inCodeBlock = true;
        codeLang = fenceMatch[1] || "";
      }
      continue;
    }
    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    if (/^\s*\|.*\|\s*$/.test(line)) {
      inTable = true;
      tableRows.push(line);
      continue;
    } else if (inTable) {
      flushTable();
    }

    const headerMatch = line.match(/^(#{1,4})\s+(.*)/);
    if (headerMatch) {
      flushList();
      const level = headerMatch[1].length + 2;
      html += `<h${level}>${inlineMarkdown(headerMatch[2])}</h${level}>`;
      continue;
    }

    const ulMatch = line.match(/^\s*[-*]\s+(.*)/);
    const olMatch = line.match(/^\s*\d+\.\s+(.*)/);
    if (ulMatch) {
      if (listType !== "ul") { flushList(); listType = "ul"; }
      listBuffer.push(ulMatch[1]);
      continue;
    } else if (olMatch) {
      if (listType !== "ol") { flushList(); listType = "ol"; }
      listBuffer.push(olMatch[1]);
      continue;
    } else {
      flushList();
    }

    if (line.trim() === "") continue;
    html += `<p>${inlineMarkdown(line)}</p>`;
  }

  flushList();
  flushTable();
  if (inCodeBlock) {
    html += `<pre class="code-block"><code>${highlightCode(codeBuffer.join("\n"))}</code></pre>`;
  }

  return html;
}

let currentConversationId = null;
let streamingBubble = null;
let isGenerating = false;
let pendingAttachment = null;
let lastUserText = null;

function api() { return window.pywebview.api; }

function switchView(view) {
  document.querySelectorAll(".view").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("active"));

  if (view === "home") {
    document.getElementById("view-chat").classList.add("active");
    showHomeGreeting();
    document.querySelector('.nav-item[data-view="chat"]').classList.add("active");
    return;
  }

  document.getElementById("view-" + view).classList.add("active");
  const navItem = document.querySelector(`.nav-item[data-view="${view}"]`);
  if (navItem) navItem.classList.add("active");

  if (view === "history") loadHistory();
  if (view === "settings") loadSettings();
  if (view === "about") loadAbout();
}

document.querySelectorAll(".nav-item").forEach((item) => {
  item.addEventListener("click", () => {
    const view = item.dataset.view;
    if (view === "chat") { startNewChat(); return; }
    switchView(view);
  });
});

function showHomeGreeting() {
  document.getElementById("home-greeting").style.display = "flex";
  document.getElementById("messages").style.display = "none";
  document.getElementById("messages").innerHTML = "";
  currentConversationId = null;
  lastUserText = null;
  updatePinButton(false, false);
}

async function startNewChat() {
  showHomeGreeting();
  document.getElementById("chat-title").textContent = "Nuevo Chat";
  switchView("chat");
}

function renderMessage(message) {
  document.getElementById("home-greeting").style.display = "none";
  document.getElementById("messages").style.display = "block";

  const row = document.createElement("div");
  row.className = "bubble-row " + (message.isUser ? "user" : "ai");

  const bubble = document.createElement("div");
  bubble.className = "bubble " + (message.isUser ? "user" : "ai");
  bubble.dataset.messageId = message.id || "";

  const contentDiv = document.createElement("div");
  contentDiv.className = "bubble-content";
  if (message.isUser) {
    contentDiv.innerHTML = escapeHtml(message.content).replace(/\n/g, "<br>");
  } else {
    contentDiv.innerHTML = renderMarkdown(message.content);
  }
  bubble.appendChild(contentDiv);

  const meta = document.createElement("div");
  meta.className = "bubble-meta";
  const time = document.createElement("span");
  time.textContent = message.timestamp;
  meta.appendChild(time);

  if (!message.isUser) {
    const actions = document.createElement("span");
    const regenLink = document.createElement("span");
    regenLink.className = "bubble-action";
    regenLink.textContent = "↻ Regenerar";
    regenLink.style.marginRight = "10px";
    regenLink.addEventListener("click", () => { if (lastUserText) regenerate(lastUserText); });

    const copyLink = document.createElement("span");
    copyLink.className = "bubble-action";
    copyLink.textContent = "Copiar";
    copyLink.addEventListener("click", () => navigator.clipboard.writeText(message.content));

    actions.appendChild(regenLink);
    actions.appendChild(copyLink);
    meta.appendChild(actions);
  } else if (message.id) {
    const editLink = document.createElement("span");
    editLink.className = "bubble-action";
    editLink.textContent = "✏️ Editar";
    editLink.addEventListener("click", () => startEditingMessage(bubble, message));
    meta.appendChild(editLink);
  }

  bubble.appendChild(meta);
  row.appendChild(bubble);
  document.getElementById("messages").appendChild(row);
  document.getElementById("messages").scrollTop = document.getElementById("messages").scrollHeight;

  if (message.isUser) lastUserText = message.content;
  return bubble;
}

let typingIndicatorEl = null;

function showTypingIndicator() {
  if (typingIndicatorEl) return;
  document.getElementById("home-greeting").style.display = "none";
  document.getElementById("messages").style.display = "block";

  const row = document.createElement("div");
  row.className = "bubble-row ai";
  const bubble = document.createElement("div");
  bubble.className = "bubble ai typing-indicator";
  bubble.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
  row.appendChild(bubble);
  document.getElementById("messages").appendChild(row);
  document.getElementById("messages").scrollTop = document.getElementById("messages").scrollHeight;
  typingIndicatorEl = row;
}

function hideTypingIndicator() {
  if (typingIndicatorEl) {
    typingIndicatorEl.remove();
    typingIndicatorEl = null;
  }
}

function setGenerating(generating) {
  isGenerating = generating;
  const sendBtn = document.getElementById("send-btn");
  const textEntry = document.getElementById("text-entry");
  if (generating) {
    sendBtn.textContent = "Detener";
    sendBtn.classList.add("stop");
    textEntry.disabled = true;
    showTypingIndicator();
  } else {
    sendBtn.textContent = "Enviar";
    sendBtn.classList.remove("stop");
    textEntry.disabled = false;
    hideTypingIndicator();
  }
}

async function sendMessage() {
  if (isGenerating) {
    await api().stop_generation();
    return;
  }

  const textEntry = document.getElementById("text-entry");
  const text = textEntry.value.trim();
  if (!text) return;

  const attachmentPath = pendingAttachment ? pendingAttachment.path : null;
  textEntry.value = "";
  textEntry.style.height = "auto";
  clearAttachmentChip();

  setGenerating(true);
  const result = await api().send_message(text, attachmentPath);
  currentConversationId = result.conversationId;
  document.getElementById("chat-title").textContent = text.slice(0, 40);
}

document.getElementById("send-btn").addEventListener("click", sendMessage);

document.getElementById("text-entry").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.getElementById("text-entry").addEventListener("input", (e) => {
  e.target.style.height = "auto";
  e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
});

async function regenerate(question) {
  setGenerating(true);
  await api().regenerate_message(question);
}

function startEditingMessage(bubble, message) {
  const contentDiv = bubble.querySelector(".bubble-content");
  const originalHTML = contentDiv.innerHTML;

  contentDiv.innerHTML = "";
  const textarea = document.createElement("textarea");
  textarea.className = "edit-textarea";
  textarea.value = message.content;
  contentDiv.appendChild(textarea);

  const actionsRow = document.createElement("div");
  actionsRow.className = "edit-actions";

  const saveBtn = document.createElement("span");
  saveBtn.className = "bubble-action";
  saveBtn.textContent = "Guardar y reenviar";
  saveBtn.addEventListener("click", async () => {
    const newText = textarea.value.trim();
    if (!newText || isGenerating) return;
    setGenerating(true);
    await api().edit_message(currentConversationId, message.id, newText);
  });

  const cancelBtn = document.createElement("span");
  cancelBtn.className = "bubble-action";
  cancelBtn.textContent = "Cancelar";
  cancelBtn.addEventListener("click", () => {
    contentDiv.innerHTML = originalHTML;
  });

  actionsRow.appendChild(saveBtn);
  actionsRow.appendChild(cancelBtn);
  contentDiv.appendChild(actionsRow);
  textarea.focus();
}

document.getElementById("btn-attach").addEventListener("click", async () => {
  const result = await api().attach_file();
  if (!result.ok) {
    if (result.error) alert(result.error);
    return;
  }
  pendingAttachment = { path: result.path, name: result.name };
  document.getElementById("attachment-chip").style.display = "flex";
  document.getElementById("attachment-name").textContent = "📎 " + result.name;
});

document.getElementById("attachment-remove").addEventListener("click", clearAttachmentChip);

function clearAttachmentChip() {
  pendingAttachment = null;
  document.getElementById("attachment-chip").style.display = "none";
}

function updatePinButton(active, enabled) {
  const btn = document.getElementById("btn-pin");
  btn.disabled = !enabled;
  btn.classList.toggle("active", active);
}

document.getElementById("btn-pin").addEventListener("click", async () => {
  const result = await api().toggle_file_context(false);
  if (!result.active) return;
  const confirmed = confirm(`¿Querés dejar de preguntar sobre «${result.filename}»?\n\nCancelá si preferís que se mantenga activo.`);
  if (confirmed) {
    const finalResult = await api().toggle_file_context(true);
    updatePinButton(finalResult.active, finalResult.active);
  }
});

let isDictating = false;
document.getElementById("btn-mic").addEventListener("click", async () => {
  if (!isDictating) {
    const result = await api().start_dictation();
    if (!result.ok) { alert(result.error); return; }
    isDictating = true;
    document.getElementById("btn-mic").classList.add("active");
  } else {
    isDictating = false;
    document.getElementById("btn-mic").classList.remove("active");
    await api().stop_dictation();
  }
});

async function loadHistory() {
  const grouped = await api().list_grouped_conversations();
  const container = document.getElementById("history-list");
  container.innerHTML = "";

  grouped.forEach((group) => {
    const label = document.createElement("div");
    label.className = "history-group-label has-visible";
    label.dataset.group = group.group;
    label.textContent = group.group.toUpperCase();
    container.appendChild(label);

    group.conversations.forEach((conv) => {
      const item = document.createElement("div");
      item.className = "history-item";
      item.dataset.title = conv.title.toLowerCase();
      item.dataset.group = group.group;

      const title = document.createElement("span");
      title.className = "title";
      title.textContent = conv.title;
      title.addEventListener("click", () => openConversation(conv.id, conv.title));

      const actions = document.createElement("span");
      actions.className = "history-actions";

      const exportBtn = document.createElement("span");
      exportBtn.textContent = "📤";
      exportBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const result = await api().export_conversation(conv.id, conv.title);
        if (result.ok) alert("Se guardó en:\n" + result.path);
        else if (result.error) alert(result.error);
      });

      const deleteBtn = document.createElement("span");
      deleteBtn.textContent = "🗑";
      deleteBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (confirm("¿Eliminar esta conversación?")) {
          await api().delete_conversation(conv.id);
          loadHistory();
        }
      });

      actions.appendChild(exportBtn);
      actions.appendChild(deleteBtn);
      item.appendChild(title);
      item.appendChild(actions);
      container.appendChild(item);
    });
  });

  filterHistory(document.getElementById("history-search").value);
}

function filterHistory(query) {
  const normalized = query.trim().toLowerCase();
  const groups = new Map();

  document.querySelectorAll(".history-item").forEach((item) => {
    const matches = !normalized || item.dataset.title.includes(normalized);
    item.style.display = matches ? "flex" : "none";
    const group = item.dataset.group;
    groups.set(group, (groups.get(group) || false) || matches);
  });

  document.querySelectorAll(".history-group-label").forEach((label) => {
    const anyVisible = groups.get(label.dataset.group) || false;
    label.classList.toggle("has-visible", anyVisible);
  });

  const anyVisibleAtAll = Array.from(groups.values()).some(Boolean);
  const emptyState = document.getElementById("history-empty-state");
  if (emptyState) {
    emptyState.style.display = (normalized && !anyVisibleAtAll) ? "flex" : "none";
  }
}

document.getElementById("history-search").addEventListener("input", (e) => {
  filterHistory(e.target.value);
});

async function openConversation(id, title) {
  currentConversationId = id;
  const messages = await api().get_conversation_messages(id);
  document.getElementById("messages").innerHTML = "";
  document.getElementById("home-greeting").style.display = "none";
  document.getElementById("messages").style.display = "block";
  messages.forEach(renderMessage);
  document.getElementById("chat-title").textContent = title;
  switchView("chat");
  document.querySelector('.nav-item[data-view="chat"]').classList.add("active");
}

async function loadSettings() {
  const settings = await api().get_settings();
  document.getElementById("chk-auto-check").checked = settings.checkUpdatesOnStartup;
  document.getElementById("chk-silent").checked = settings.silentUpdatesEnabled;
}

document.getElementById("chk-auto-check").addEventListener("change", (e) => {
  api().update_setting("checkUpdatesOnStartup", e.target.checked);
});
document.getElementById("chk-silent").addEventListener("change", (e) => {
  api().update_setting("silentUpdatesEnabled", e.target.checked);
});

document.querySelectorAll(".help-card-header").forEach((header) => {
  header.addEventListener("click", () => {
    const body = header.nextElementSibling;
    body.classList.toggle("expanded");
    header.querySelector(".chevron").textContent = body.classList.contains("expanded") ? "▾" : "▸";
  });
});

function statusColor(ok) { return ok ? "#1F9D55" : "#D9A400"; }

async function loadAbout() {
  const status = await api().get_about_status();
  document.getElementById("about-version").textContent = `Versión ${status.version} · Build ${status.build}`;

  const aiTile = document.getElementById("about-ai");
  aiTile.textContent = (status.aiConnected ? "🟢 " : "🔴 ") + status.aiEngine;
  aiTile.style.color = statusColor(status.aiConnected);

  const keyringTile = document.getElementById("about-keyring");
  keyringTile.textContent = status.secureStorageAvailable ? "🟢 Disponible" : "🟡 Modo de respaldo";
  keyringTile.style.color = statusColor(status.secureStorageAvailable);

  const micTile = document.getElementById("about-mic");
  micTile.textContent = status.microphoneDetected ? "🟢 Detectado" : "🟡 No detectado";
  micTile.style.color = statusColor(status.microphoneDetected);

  document.getElementById("about-update").textContent = status.lastUpdateCheck;
  document.getElementById("about-session").textContent = `${status.displayName} · ${status.aiEngine}`;
}

document.getElementById("btn-check-updates").addEventListener("click", () => {
  document.getElementById("about-note").textContent = "Buscando...";
  api().check_updates_now();
});

document.getElementById("btn-copy-diagnostics").addEventListener("click", async () => {
  const text = await api().build_diagnostics_text();
  await navigator.clipboard.writeText(text);
  document.getElementById("about-note").textContent = "✓ Copiado al portapapeles";
});

document.getElementById("btn-ms-login").addEventListener("click", () => { api().start_device_login(); });

document.getElementById("link-contact-it").addEventListener("click", (e) => {
  e.preventDefault();
  document.getElementById("login-view").classList.remove("active");
  document.getElementById("guest-ticket-view").classList.add("active");
});

document.getElementById("btn-back-to-login").addEventListener("click", () => {
  document.getElementById("guest-ticket-view").classList.remove("active");
  document.getElementById("login-view").classList.add("active");
  document.getElementById("guest-ticket-message").textContent = "";
});

const gtDetalle = document.getElementById("gt-detalle");
const gtDetalleCount = document.getElementById("gt-detalle-count");
gtDetalle.addEventListener("input", () => {
  const len = gtDetalle.value.length;
  gtDetalleCount.textContent = `${len}/250`;
  gtDetalleCount.parentElement.classList.toggle("over-limit", len >= 250);
});

document.getElementById("btn-submit-guest-ticket").addEventListener("click", async () => {
  const requerimiento = document.getElementById("gt-requerimiento").value.trim();
  const tipo = document.getElementById("gt-tipo").value;
  const cedula = document.getElementById("gt-cedula").value.trim();
  const nombre = document.getElementById("gt-nombre").value.trim();
  const correo = document.getElementById("gt-correo").value.trim();
  const celular = document.getElementById("gt-celular").value.trim();
  const detalle = document.getElementById("gt-detalle").value.trim();
  const anydesk = document.getElementById("gt-anydesk").value.trim();

  const messageEl = document.getElementById("guest-ticket-message");
  const setMessage = (text, tone) => {
    messageEl.innerHTML = "";
    if (!text) return;
    if (tone) {
      const dot = document.createElement("span");
      dot.className = "status-dot";
      dot.style.background = tone;
      messageEl.appendChild(dot);
    }
    const span = document.createElement("span");
    span.style.color = tone || "var(--text-600)";
    span.textContent = text;
    messageEl.appendChild(span);
  };

  const faltantes = [];
  if (!requerimiento) faltantes.push("requerimiento en");
  if (!tipo) faltantes.push("tipo de solicitud");
  if (!cedula) faltantes.push("cédula");
  if (!nombre) faltantes.push("nombre del solicitante");
  if (!correo) faltantes.push("correo del solicitante");
  if (!celular) faltantes.push("celular del solicitante");
  if (!detalle) faltantes.push("detalle de la solicitud");

  if (faltantes.length) {
    setMessage("Falta completar: " + faltantes.join(", ") + ".", "var(--status-red)");
    return;
  }

  if (detalle.length > 250) {
    setMessage("El detalle de la solicitud supera los 250 caracteres. Resumilo un poco.", "var(--status-red)");
    return;
  }

  const submitBtn = document.getElementById("btn-submit-guest-ticket");
  submitBtn.disabled = true;
  submitBtn.textContent = "Enviando...";
  setMessage("");

  try {
    const result = await api().submit_ticket({
      requerimiento_en: requerimiento,
      tipo_solicitud: tipo,
      cedula: cedula,
      nombre_solicitante: nombre,
      correo_solicitante: correo,
      celular_solicitante: celular,
      detalle_solicitud: detalle,
      id_anydesk: anydesk,
    });

    if (result.ok) {
      setMessage("Ticket enviado. Mesa de Ayuda de IT te va a contactar a " + correo + ".", "var(--status-green)");
      ["gt-requerimiento", "gt-cedula", "gt-nombre", "gt-correo", "gt-celular", "gt-detalle", "gt-anydesk"].forEach((id) => {
        document.getElementById(id).value = "";
      });
      gtDetalleCount.textContent = "0/250";
      gtDetalleCount.parentElement.classList.remove("over-limit");
    } else {
      setMessage("No se pudo enviar el ticket: " + (result.error || "error desconocido") + ".", "var(--status-red)");
    }
  } catch (err) {
    setMessage("No se pudo enviar el ticket. Intentá de nuevo en un momento.", "var(--status-red)");
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Enviar ticket";
  }
});

function enterApp(displayName) {
  document.getElementById("login-view").classList.remove("active");
  document.getElementById("app").style.display = "flex";
  document.getElementById("user-name").textContent = displayName || "Invitado";
  document.getElementById("user-avatar").textContent = displayName
    ? displayName.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()
    : "IN";
  api().connect_ai_provider().then((result) => {
    const statusEl = document.getElementById("ai-status");
    statusEl.innerHTML = "";
    statusEl.classList.toggle("online", result.connected);
    statusEl.classList.toggle("offline", !result.connected);
    const dot = document.createElement("span");
    dot.className = "status-dot";
    const label = document.createElement("span");
    label.textContent = result.connected ? ("IA · " + result.engine) : "Sin conexión";
    statusEl.appendChild(dot);
    statusEl.appendChild(label);
  });
}

window.vickyEvent = function (event, payload) {
  if (event === "login_code_ready") {
    const box = document.getElementById("login-code-box");
    box.style.display = "block";
    box.innerHTML = `
      <div class="device-code-card">
        <div class="device-code-label">Verificá el inicio de sesión</div>
        <div class="device-code-desc">
          Se abrió <a href="${payload.url}" id="device-code-link">${payload.url}</a> en tu navegador.
          Si no se abrió sola, entrá manualmente e ingresá este código:
        </div>
        <div class="device-code-value-row">
          <span class="device-code-value" id="device-code-value">${payload.code}</span>
          <button class="device-code-copy-btn" id="device-code-copy-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="8.5" y="8.5" width="11" height="11" rx="1.6"/><path d="M15.5 8.5V6.6A1.6 1.6 0 0 0 13.9 5H6.6A1.6 1.6 0 0 0 5 6.6v7.3a1.6 1.6 0 0 0 1.6 1.6h1.9"/></svg>
            <span id="device-code-copy-label">Copiar</span>
          </button>
        </div>
      </div>`;

    document.getElementById("device-code-link").addEventListener("click", (e) => {
      e.preventDefault();
      window.open(payload.url, "_blank");
    });

    document.getElementById("device-code-copy-btn").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      try {
        await navigator.clipboard.writeText(payload.code);
        btn.classList.add("copied");
        document.getElementById("device-code-copy-label").textContent = "¡Copiado!";
        setTimeout(() => {
          btn.classList.remove("copied");
          document.getElementById("device-code-copy-label").textContent = "Copiar";
        }, 1800);
      } catch (err) {
        document.getElementById("device-code-copy-label").textContent = "No se pudo copiar";
      }
    });
  } else if (event === "login_complete") {
    if (payload.success) {
      enterApp(payload.displayName);
    } else {
      document.getElementById("login-message").textContent = payload.message || "No se pudo iniciar sesión.";
    }
  } else if (event === "message_added") {
    if (currentConversationId === null) currentConversationId = payload.conversationId;
    if (payload.conversationId === currentConversationId) {
      if (!payload.message.isUser) hideTypingIndicator();
      renderMessage(payload.message);
    }
  } else if (event === "file_context_state") {
    updatePinButton(payload.active, payload.enabled);
  } else if (event === "generation_started") {
    if (currentConversationId === null) currentConversationId = payload.conversationId;
    if (payload.conversationId === currentConversationId) {
      setGenerating(true);
      streamingBubble = null;
    }
  } else if (event === "token") {
    if (payload.conversationId !== currentConversationId) return;
    hideTypingIndicator();
    if (!streamingBubble) {
      streamingBubble = renderMessage({ content: "", isUser: false, timestamp: "" });
    }
    streamingBubble.querySelector(".bubble-content").textContent += payload.delta;
  } else if (event === "generation_finished") {
    setGenerating(false);
    if (payload.conversationId === currentConversationId) {
      document.getElementById("messages").innerHTML = "";
      openConversation(currentConversationId, document.getElementById("chat-title").textContent);
    }
    streamingBubble = null;
  } else if (event === "conversation_title_updated") {
    if (payload.conversationId === currentConversationId) {
      document.getElementById("chat-title").textContent = payload.title;
    }
  } else if (event === "conversation_reset") {
    if (payload.conversationId === currentConversationId) {
      openConversation(currentConversationId, document.getElementById("chat-title").textContent);
    }
  } else if (event === "clarification_needed") {
    const names = payload.options.map((o) => o.filename).join(", ");
    if (payload.conversationId === currentConversationId) {
      renderMessage({ content: `¿Sobre cuál de estos te referís? ${names}`, isUser: false, timestamp: "" });
    }
  } else if (event === "dictation_result") {
    if (payload.text) {
      const entry = document.getElementById("text-entry");
      entry.value = (entry.value ? entry.value + " " : "") + payload.text;
    } else {
      alert("No se pudo transcribir el audio grabado.");
    }
  } else if (event === "update_check_result") {
    const note = document.getElementById("about-note");
    if (payload.error) {
      note.textContent = "Error: " + payload.error;
    } else if (payload.available) {
      note.textContent = `Hay una versión nueva: ${payload.version}`;
      openUpdateModal(payload);
    } else {
      note.textContent = "Ya estás en la última versión.";
    }
  } else if (event === "update_download_progress") {
    const fill = document.getElementById("update-progress-fill");
    const percentEl = document.getElementById("update-progress-percent");
    const speedEl = document.getElementById("update-progress-speed");
    const pct = Math.min(100, Math.round(payload.percent || 0));
    fill.style.width = pct + "%";
    percentEl.textContent = pct + "%";
    speedEl.textContent = payload.speedBytesPerSec ? formatBytesPerSec(payload.speedBytesPerSec) : "";
  } else if (event === "update_download_complete") {
    onUpdateDownloadComplete(payload);
  }
};

function formatBytesPerSec(bytesPerSec) {
  if (bytesPerSec > 1024 * 1024) return (bytesPerSec / (1024 * 1024)).toFixed(1) + " MB/s";
  if (bytesPerSec > 1024) return (bytesPerSec / 1024).toFixed(0) + " KB/s";
  return Math.round(bytesPerSec) + " B/s";
}

function setUpdateModalMessage(text, tone) {
  const el = document.getElementById("update-modal-message");
  el.innerHTML = "";
  if (!text) { el.style.display = "none"; return; }
  el.style.display = "flex";
  if (tone) {
    const dot = document.createElement("span");
    dot.className = "status-dot";
    dot.style.background = tone;
    el.appendChild(dot);
  }
  const span = document.createElement("span");
  span.style.color = tone || "var(--text-600)";
  span.textContent = text;
  el.appendChild(span);
}

function openUpdateModal(payload) {
  document.getElementById("update-modal-version").textContent = payload.version;
  const notesEl = document.getElementById("update-modal-notes");
  notesEl.innerHTML = "";
  (payload.notes || []).forEach((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    notesEl.appendChild(li);
  });
  document.getElementById("update-modal-title").textContent = "Hay una versión nueva disponible";
  document.getElementById("update-modal-progress").style.display = "none";
  setUpdateModalMessage("");

  const actions = document.getElementById("update-modal-actions");
  actions.innerHTML = "";
  const laterBtn = document.createElement("button");
  laterBtn.className = "btn";
  laterBtn.textContent = "Más tarde";
  laterBtn.addEventListener("click", closeUpdateModal);
  const nowBtn = document.createElement("button");
  nowBtn.className = "btn primary";
  nowBtn.textContent = "Actualizar ahora";
  nowBtn.addEventListener("click", startUpdateDownload);
  actions.appendChild(laterBtn);
  actions.appendChild(nowBtn);

  document.getElementById("update-modal-overlay").classList.add("active");
}

function closeUpdateModal() {
  document.getElementById("update-modal-overlay").classList.remove("active");
}

async function startUpdateDownload() {
  document.getElementById("update-modal-title").textContent = "Descargando actualización...";
  document.getElementById("update-modal-progress").style.display = "block";
  document.getElementById("update-progress-fill").style.width = "0%";
  document.getElementById("update-progress-percent").textContent = "0%";
  document.getElementById("update-progress-speed").textContent = "";
  setUpdateModalMessage("");

  const actions = document.getElementById("update-modal-actions");
  actions.innerHTML = "";
  const cancelBtn = document.createElement("button");
  cancelBtn.className = "btn";
  cancelBtn.textContent = "Cancelar";
  cancelBtn.addEventListener("click", async () => {
    await api().cancel_update_download();
    closeUpdateModal();
  });
  actions.appendChild(cancelBtn);

  const result = await api().download_update_now();
  if (!result.ok) {
    setUpdateModalMessage(result.error || "No se pudo iniciar la descarga.", "var(--status-red)");
    actions.innerHTML = "";
    const retryBtn = document.createElement("button");
    retryBtn.className = "btn primary";
    retryBtn.textContent = "Reintentar";
    retryBtn.addEventListener("click", startUpdateDownload);
    actions.appendChild(retryBtn);
  }
}

function onUpdateDownloadComplete(payload) {
  const actions = document.getElementById("update-modal-actions");
  actions.innerHTML = "";

  if (!payload.ok) {
    document.getElementById("update-modal-title").textContent = "No se pudo descargar la actualización";
    setUpdateModalMessage(payload.error || "Error desconocido durante la descarga.", "var(--status-red)");
    const retryBtn = document.createElement("button");
    retryBtn.className = "btn primary";
    retryBtn.textContent = "Reintentar";
    retryBtn.addEventListener("click", startUpdateDownload);
    actions.appendChild(retryBtn);
    return;
  }

  document.getElementById("update-modal-title").textContent = "Actualización lista para instalar";
  document.getElementById("update-progress-fill").style.width = "100%";
  document.getElementById("update-progress-percent").textContent = "100%";
  setUpdateModalMessage("Descarga verificada correctamente.", "var(--status-green)");

  const laterBtn = document.createElement("button");
  laterBtn.className = "btn";
  laterBtn.textContent = "Más tarde";
  laterBtn.addEventListener("click", closeUpdateModal);

  const installBtn = document.createElement("button");
  installBtn.className = "btn primary";
  installBtn.textContent = "Instalar y reiniciar";
  installBtn.addEventListener("click", async () => {
    installBtn.disabled = true;
    installBtn.textContent = "Instalando...";
    setUpdateModalMessage("Vicky se va a cerrar para completar la instalación...", "var(--text-600)");
    const result = await api().install_update_now();
    if (!result.ok) {
      installBtn.disabled = false;
      installBtn.textContent = "Instalar y reiniciar";
      setUpdateModalMessage(result.error || "No se pudo iniciar el instalador.", "var(--status-red)");
    }
  });

  actions.appendChild(laterBtn);
  actions.appendChild(installBtn);
}

document.getElementById("update-modal-overlay").addEventListener("click", (e) => {
  if (e.target.id === "update-modal-overlay") closeUpdateModal();
});

window.addEventListener("pywebviewready", async () => {
  const configured = await api().login_is_configured();
  if (!configured) {
    const result = await api().continue_as_guest();
    enterApp(result.displayName);
    return;
  }

  const loginMessage = document.getElementById("login-message");
  loginMessage.textContent = "Verificando si ya iniciaste sesión antes...";

  const silent = await api().try_silent_login();
  if (silent.success) {
    enterApp(silent.displayName);
  } else {
    loginMessage.textContent = "";
  }
});

document.addEventListener("keydown", (e) => {
  const ctrlOrCmd = e.ctrlKey || e.metaKey;

  if (ctrlOrCmd && e.key.toLowerCase() === "n") {
    e.preventDefault();
    startNewChat();
    return;
  }

  if (e.key === "Escape") {
    if (isGenerating) {
      api().stop_generation();
      return;
    }
    if (pendingAttachment) {
      clearAttachmentChip();
      return;
    }
  }
});

const chatView = document.getElementById("view-chat");
const dropOverlay = document.getElementById("drop-overlay");
let dragCounter = 0;

chatView.addEventListener("dragenter", (e) => {
  e.preventDefault();
  dragCounter += 1;
  dropOverlay.classList.add("active");
});

chatView.addEventListener("dragover", (e) => {
  e.preventDefault();
});

chatView.addEventListener("dragleave", (e) => {
  e.preventDefault();
  dragCounter = Math.max(0, dragCounter - 1);
  if (dragCounter === 0) dropOverlay.classList.remove("active");
});

chatView.addEventListener("drop", async (e) => {
  e.preventDefault();
  dragCounter = 0;
  dropOverlay.classList.remove("active");

  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = async () => {
    const base64Data = reader.result.split(",")[1];
    const result = await api().attach_file_from_bytes(file.name, base64Data);
    if (!result.ok) {
      if (result.error) alert(result.error);
      return;
    }
    pendingAttachment = { path: result.path, name: result.name };
    document.getElementById("attachment-chip").style.display = "flex";
    document.getElementById("attachment-name").textContent = "📎 " + result.name;
  };
  reader.readAsDataURL(file);
});

// ---------------------------------------------------------------------
// Chips de preguntas frecuentes (pantalla de Inicio)
// ---------------------------------------------------------------------
document.querySelectorAll(".faq-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    const textEntry = document.getElementById("text-entry");
    textEntry.value = chip.dataset.prompt || "";
    sendMessage();
  });
});

// ---------------------------------------------------------------------
// Panel de perfil desplegable (info de la cuenta de Microsoft + cerrar sesión)
// ---------------------------------------------------------------------
const userToggle = document.getElementById("sidebar-user-toggle");

async function openProfilePanel() {
  const profile = await api().get_profile();
  const detailsEl = document.getElementById("profile-details");
  detailsEl.innerHTML = "";

  if (profile.isGuest) {
    document.getElementById("profile-name").textContent = "Invitado";
    document.getElementById("profile-email").textContent = "Sesión sin cuenta corporativa";
    document.getElementById("profile-avatar").textContent = "IN";
  } else {
    document.getElementById("profile-name").textContent = profile.displayName || "Usuario";
    document.getElementById("profile-email").textContent = profile.email || "";
    document.getElementById("profile-avatar").textContent = (profile.displayName || "U")
      .split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

    const rows = [
      ["Cargo", profile.jobTitle],
      ["Área", profile.department],
      ["Sede", profile.officeLocation],
    ];
    rows.forEach(([label, value]) => {
      if (!value) return;
      const row = document.createElement("div");
      row.className = "profile-panel-detail-row";
      row.innerHTML = `<span class="profile-panel-detail-label">${label}</span><span class="profile-panel-detail-value"></span>`;
      row.querySelector(".profile-panel-detail-value").textContent = value;
      detailsEl.appendChild(row);
    });
  }
}

userToggle.addEventListener("click", async (e) => {
  const isOpen = userToggle.classList.contains("open");
  if (isOpen) {
    userToggle.classList.remove("open");
    return;
  }
  userToggle.classList.add("open");
  await openProfilePanel();
});

document.getElementById("profile-panel").addEventListener("click", (e) => e.stopPropagation());

document.addEventListener("click", (e) => {
  if (!userToggle.contains(e.target)) userToggle.classList.remove("open");
});

document.getElementById("btn-logout").addEventListener("click", async (e) => {
  e.stopPropagation();
  userToggle.classList.remove("open");
  await api().logout();

  document.getElementById("app").style.display = "none";
  document.getElementById("login-view").classList.add("active");
  document.getElementById("login-message").textContent = "";
  document.getElementById("login-code-box").style.display = "none";
  document.getElementById("login-code-box").innerHTML = "";
  document.getElementById("user-name").textContent = "Invitado";
  document.getElementById("user-avatar").textContent = "IN";
  currentConversationId = null;
});
