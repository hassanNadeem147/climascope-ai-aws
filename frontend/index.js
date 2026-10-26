"use strict";

document.documentElement.classList.add("anim");

document.addEventListener("DOMContentLoaded", () => {
  const authView = document.querySelector("#auth-view");
  const chatView = document.querySelector("#chat-view");
  const authForm = document.querySelector("#auth-form");
  const authMessage = document.querySelector("#auth-message");
  const authSubmit = document.querySelector("#auth-submit");
  const authSubmitLabel = document.querySelector("#auth-submit-label");
  const nameField = document.querySelector("#name-field");
  const fullNameInput = document.querySelector("#full-name");
  const emailInput = document.querySelector("#email");
  const passwordInput = document.querySelector("#password");
  const passwordHint = document.querySelector("#password-hint");
  const loginTab = document.querySelector("#login-tab");
  const registerTab = document.querySelector("#register-tab");
  const formHeading = document.querySelector("#form-heading");
  const formSubheading = document.querySelector("#form-subheading");
  const accountControls = document.querySelector("#account-controls");
  const accountName = document.querySelector("#account-name");
  const logoutButton = document.querySelector("#logout-button");
  const chatForm = document.querySelector("#chat-form");
  const questionInput = document.querySelector("#question");
  const sendButton = document.querySelector("#send-button");
  const conversation = document.querySelector("#conversation");
  const welcomePanel = document.querySelector("#welcome-panel");
  const chatHeading = document.querySelector("#chat-heading");
  const suggestions = document.querySelector(".suggestions");

  let mode = "login";
  let accessToken = null;
  let threadId = null;
  let activeRequest = null;
  let isStreaming = false;

  function setEntranceFinished() {
    document.documentElement.classList.remove("anim");
  }

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    setEntranceFinished();
  } else {
    window.setTimeout(setEntranceFinished, 1800);
  }

  function showMessage(element, message, kind) {
    element.textContent = message;
    element.dataset.kind = kind;
    element.hidden = !message;
  }

  function setMode(nextMode) {
    mode = nextMode;
    const registering = mode === "register";

    loginTab.classList.toggle("is-active", !registering);
    registerTab.classList.toggle("is-active", registering);
    loginTab.setAttribute("aria-selected", String(!registering));
    registerTab.setAttribute("aria-selected", String(registering));
    nameField.hidden = !registering;
    fullNameInput.disabled = !registering;
    fullNameInput.required = registering;
    authForm.action = registering ? "/api/v1/auth/register" : "/api/v1/auth/login";
    passwordInput.autocomplete = registering ? "new-password" : "current-password";
    passwordInput.minLength = registering ? 8 : 1;
    passwordHint.hidden = !registering;
    formHeading.textContent = registering ? "Create your account" : "Welcome back";
    formSubheading.textContent = registering
      ? "Join ClimaScope AI to explore climate research."
      : "Sign in to continue to ClimaScope AI.";
    authSubmitLabel.textContent = registering ? "Create account" : "Sign in";
    showMessage(authMessage, "", "");
  }

  function readableError(payload, fallback) {
    const detail = payload && payload.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => item && typeof item.msg === "string" ? item.msg : "")
        .filter(Boolean);
      if (messages.length) return messages.join(" ");
    }
    return fallback;
  }

  async function requestJson(path, body) {
    let response;
    try {
      response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
      });
    } catch {
      throw new Error("Could not reach ClimaScope AI. Check that the app server is running and try again.");
    }

    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(readableError(payload, `Request failed (${response.status}).`));
    }
    return payload;
  }

  async function authenticate(event) {
    event.preventDefault();
    if (!authForm.reportValidity()) return;

    authSubmit.disabled = true;
    authSubmit.classList.add("is-loading");
    showMessage(authMessage, "", "");

    try {
      const credentials = {
        email: emailInput.value.trim(),
        password: passwordInput.value,
      };

      if (mode === "register") {
        await requestJson("/api/v1/auth/register", {
          ...credentials,
          full_name: fullNameInput.value.trim(),
        });
        const tokenResponse = await requestJson("/api/v1/auth/login", credentials);
        enterChat(tokenResponse);
        return;
      }

      const tokenResponse = await requestJson("/api/v1/auth/login", credentials);
      enterChat(tokenResponse);
    } catch (error) {
      showMessage(
        authMessage,
        error instanceof Error ? error.message : "Authentication failed. Please try again.",
        "error",
      );
    } finally {
      authSubmit.disabled = false;
      authSubmit.classList.remove("is-loading");
    }
  }

  function enterChat(payload) {
    if (
      !payload
      || typeof payload.access_token !== "string"
      || !payload.access_token
      || !payload.user
      || typeof payload.user.full_name !== "string"
    ) {
      throw new Error("The server returned an invalid sign-in response.");
    }

    accessToken = payload.access_token;
    threadId = null;
    authView.hidden = true;
    chatView.hidden = false;
    accountControls.hidden = false;
    accountName.textContent = payload.user.full_name;
    authForm.reset();
    showMessage(authMessage, "", "");
    questionInput.focus();
  }

  function appendMessage(role, text) {
    const article = document.createElement("article");
    article.className = `message message-${role}`;

    const label = document.createElement("span");
    label.className = "message-label";
    label.textContent = role === "user" ? "You" : "ClimaScope AI";

    const content = document.createElement("div");
    content.className = "message-content";
    if (role === "assistant") {
      renderMarkdown(content, text);
    } else {
      content.textContent = text;
    }

    article.append(label, content);
    conversation.append(article);
    conversation.scrollTop = conversation.scrollHeight;
    return content;
  }

  function appendInlineMarkdown(parent, text) {
    const tokenPattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(\*\*|__)(?=\S)([\s\S]*?\S)\3|~~(?=\S)([\s\S]*?\S)~~|`([^`\n]+)`|(?<!\*)\*(?!\s)([^*\n]+?\S)\*(?!\*)|(?<!_)_(?!\s)([^_\n]+?\S)_(?!_)/g;
    let cursor = 0;

    for (const match of text.matchAll(tokenPattern)) {
      const index = match.index;
      if (index > cursor) {
        parent.append(document.createTextNode(text.slice(cursor, index).replace(/\*\*/g, "")));
      }

      let element;
      if (match[1] !== undefined) {
        let safeUrl;
        try {
          const parsedUrl = new URL(match[2]);
          if (parsedUrl.protocol === "https:" || parsedUrl.protocol === "http:") {
            safeUrl = parsedUrl.href;
          }
        } catch {
          safeUrl = undefined;
        }
        if (safeUrl) {
          element = document.createElement("a");
          element.href = safeUrl;
          element.target = "_blank";
          element.rel = "noopener noreferrer";
          appendInlineMarkdown(element, match[1]);
        } else {
          parent.append(document.createTextNode(match[0]));
        }
      } else if (match[4] !== undefined) {
        element = document.createElement("strong");
        appendInlineMarkdown(element, match[4]);
      } else if (match[5] !== undefined) {
        element = document.createElement("del");
        appendInlineMarkdown(element, match[5]);
      } else if (match[6] !== undefined) {
        element = document.createElement("code");
        element.textContent = match[6];
      } else if (match[7] !== undefined || match[8] !== undefined) {
        element = document.createElement("em");
        appendInlineMarkdown(element, match[7] ?? match[8]);
      }

      if (element) parent.append(element);
      cursor = index + match[0].length;
    }

    const remaining = text.slice(cursor);
    parent.append(document.createTextNode(remaining.replace(/\*\*/g, "")));
  }

  function splitTableRow(line) {
    let trimmed = line.trim();
    if (trimmed.startsWith("|")) trimmed = trimmed.slice(1);
    if (trimmed.endsWith("|")) trimmed = trimmed.slice(0, -1);
    return trimmed.split(/(?<!\\)\|/).map((cell) => cell.replace(/\\\|/g, "|").trim());
  }

  function isTableSeparator(line) {
    const cells = splitTableRow(line);
    return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
  }

  function isBlockStart(lines, index) {
    const line = lines[index];
    if (!line || !line.trim()) return true;
    return /^(?:#{1,6}\s|>\s?|[-*_]\s*(?:[-*_]\s*){2,}$|```|~~~|\s*[-+*]\s+|\s*\d+[.)]\s+)/.test(line)
      || (index + 1 < lines.length && isTableSeparator(lines[index + 1]));
  }

  function appendTable(parent, lines, startIndex) {
    const table = document.createElement("table");
    table.className = "markdown-table";
    const headers = splitTableRow(lines[startIndex]);
    const header = document.createElement("thead");
    const headerRow = document.createElement("tr");

    for (const value of headers) {
      const cell = document.createElement("th");
      appendInlineMarkdown(cell, value);
      headerRow.append(cell);
    }
    header.append(headerRow);
    table.append(header);

    const body = document.createElement("tbody");
    let index = startIndex + 2;
    while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
      const values = splitTableRow(lines[index]);
      const row = document.createElement("tr");
      for (let cellIndex = 0; cellIndex < headers.length; cellIndex += 1) {
        const cell = document.createElement("td");
        appendInlineMarkdown(cell, values[cellIndex] ?? "");
        row.append(cell);
      }
      body.append(row);
      index += 1;
    }
    table.append(body);
    parent.append(table);
    return index;
  }

  function renderMarkdown(container, markdown) {
    container.replaceChildren();
    const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
    let index = 0;

    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) {
        index += 1;
        continue;
      }

      if (index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
        index = appendTable(container, lines, index);
        continue;
      }

      const fence = line.match(/^\s*(```|~~~)\s*([\w-]*)\s*$/);
      if (fence) {
        const codeLines = [];
        index += 1;
        while (index < lines.length && !lines[index].trimStart().startsWith(fence[1])) {
          codeLines.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) index += 1;
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        if (fence[2]) code.className = `language-${fence[2].replace(/[^a-zA-Z0-9_-]/g, "")}`;
        code.textContent = codeLines.join("\n");
        pre.append(code);
        container.append(pre);
        continue;
      }

      const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
      if (heading) {
        const element = document.createElement(`h${heading[1].length}`);
        appendInlineMarkdown(element, heading[2]);
        container.append(element);
        index += 1;
        continue;
      }

      if (/^\s{0,3}(?:[-*_]\s*){3,}$/.test(line)) {
        container.append(document.createElement("hr"));
        index += 1;
        continue;
      }

      if (/^\s*>\s?/.test(line)) {
        const quoteLines = [];
        while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
          quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
          index += 1;
        }
        const quote = document.createElement("blockquote");
        appendInlineMarkdown(quote, quoteLines.join(" "));
        container.append(quote);
        continue;
      }

      const listMatch = line.match(/^\s*([-+*]|\d+[.)])\s+/);
      if (listMatch) {
        const ordered = /^\d/.test(listMatch[1]);
        const list = document.createElement(ordered ? "ol" : "ul");
        while (index < lines.length) {
          const itemMatch = lines[index].match(/^\s*([-+*]|\d+[.)])\s+(.*)$/);
          if (!itemMatch || /^\d/.test(itemMatch[1]) !== ordered) break;
          const item = document.createElement("li");
          appendInlineMarkdown(item, itemMatch[2]);
          list.append(item);
          index += 1;
        }
        container.append(list);
        continue;
      }

      const paragraphLines = [line.trim()];
      index += 1;
      while (index < lines.length && lines[index].trim() && !isBlockStart(lines, index)) {
        paragraphLines.push(lines[index].trim());
        index += 1;
      }
      const paragraph = document.createElement("p");
      appendInlineMarkdown(paragraph, paragraphLines.join(" "));
      container.append(paragraph);
    }
  }

  function setStreaming(streaming) {
    isStreaming = streaming;
    sendButton.disabled = streaming || !questionInput.value.trim();
    questionInput.disabled = streaming;
    sendButton.setAttribute("aria-label", streaming ? "Answering" : "Send question");
  }

  function handleServerEvent(eventName, data, answerElement) {
    let payload;
    try {
      payload = JSON.parse(data);
    } catch {
      throw new Error("The server sent an invalid chat response.");
    }

    if (eventName === "thread" && typeof payload.thread_id === "string") {
      threadId = payload.thread_id;
    } else if (eventName === "token" && typeof payload.text === "string") {
      answerElement.dataset.rawMarkdown = (answerElement.dataset.rawMarkdown || "") + payload.text;
      renderMarkdown(answerElement, answerElement.dataset.rawMarkdown);
      conversation.scrollTop = conversation.scrollHeight;
    } else if (eventName === "error") {
      throw new Error(
        typeof payload.detail === "string"
          ? payload.detail
          : "The model could not complete this request.",
      );
    }
  }

  async function readEventStream(response, answerElement) {
    if (!response.body) {
      throw new Error("The browser could not read the chat stream.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    function processFrame(frame) {
      let eventName = "message";
      const dataLines = [];
      for (const line of frame.split(/\r?\n/)) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      if (dataLines.length) {
        handleServerEvent(eventName, dataLines.join("\n"), answerElement);
      }
    }

    try {
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() || "";
        for (const frame of frames) processFrame(frame);
        if (done) break;
      }
      if (buffer.trim()) processFrame(buffer);
    } finally {
      reader.releaseLock();
    }
  }

  async function sendQuestion(event) {
    event.preventDefault();
    const query = questionInput.value.trim();
    if (!query || !accessToken || isStreaming) return;

    if (welcomePanel) welcomePanel.hidden = true;
    chatHeading.classList.add("is-compact");
    if (suggestions) suggestions.hidden = true;

    appendMessage("user", query);
    questionInput.value = "";
    const answer = appendMessage("assistant", "");
    setStreaming(true);
    activeRequest = new AbortController();

    const requestBody = { query };
    if (threadId) requestBody.thread_id = threadId;

    try {
      const response = await fetch("/api/v1/model/stream", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(requestBody),
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        signal: activeRequest.signal,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        if (response.status === 401) {
          signOut();
          throw new Error("Your session has expired. Please sign in again.");
        }
        throw new Error(readableError(payload, `Chat request failed (${response.status}).`));
      }

      if (!response.headers.get("content-type")?.includes("text/event-stream")) {
        throw new Error("The server returned an unexpected chat response.");
      }

      await readEventStream(response, answer);
      if (!answer.dataset.rawMarkdown?.trim()) {
        answer.textContent = "No answer text was returned. Please try again.";
      } else {
        renderMarkdown(answer, answer.dataset.rawMarkdown);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      answer.replaceChildren(document.createTextNode(error instanceof Error
        ? error.message
        : "The chat request failed. Please try again."));
      answer.closest(".message")?.classList.add("message-error");
    } finally {
      activeRequest = null;
      setStreaming(false);
      questionInput.focus();
    }
  }

  function signOut() {
    activeRequest?.abort();
    activeRequest = null;
    accessToken = null;
    threadId = null;
    isStreaming = false;
    chatView.hidden = true;
    authView.hidden = false;
    accountControls.hidden = true;
    authForm.reset();
    conversation.querySelectorAll(".message").forEach((message) => message.remove());
    if (welcomePanel) welcomePanel.hidden = false;
    if (suggestions) suggestions.hidden = false;
    chatHeading.classList.remove("is-compact");
    chatForm.reset();
    questionInput.disabled = false;
    sendButton.disabled = true;
    emailInput.focus();
  }

  authForm.addEventListener("submit", authenticate);
  loginTab.addEventListener("click", () => setMode("login"));
  registerTab.addEventListener("click", () => setMode("register"));
  logoutButton.addEventListener("click", signOut);
  chatForm.addEventListener("submit", sendQuestion);

  questionInput.addEventListener("input", () => {
    sendButton.disabled = isStreaming || !questionInput.value.trim();
  });

  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      chatForm.requestSubmit();
    }
  });

  suggestions?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-question]");
    if (!button) return;
    questionInput.value = button.dataset.question;
    questionInput.dispatchEvent(new Event("input", { bubbles: true }));
    questionInput.focus();
  });

  authView.hidden = false;
  chatView.hidden = true;
});
