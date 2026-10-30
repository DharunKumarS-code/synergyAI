import React, { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const LOGO_URL = "/images/synergy-logo.png";
const STORAGE_KEY = "synergyai_conversations";

const suggestedQuestions = [
  {
    icon: "♧",
    title: "Sustainability",
    question: "What are Synergy Marine Group’s sustainability initiatives?",
  },
  {
    icon: "⚓",
    title: "Our services",
    question: "What services does Synergy Marine Group provide?",
  },
  {
    icon: "♙",
    title: "Crew welfare",
    question: "Tell me about crew welfare and training programmes.",
  },
  {
    icon: "◈",
    title: "ESG and governance",
    question: "How does Synergy integrate ESG into its operations?",
  },
];

function createConversation() {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: "New conversation",
    messages: [],
    updatedAt: Date.now(),
  };
}

function loadConversations() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    if (!saved) {
      return [createConversation()];
    }

    const parsed = JSON.parse(saved);

    if (
      !Array.isArray(parsed) ||
      !parsed.every(
        (item) =>
          item &&
          typeof item.id === "string" &&
          Array.isArray(item.messages)
      )
    ) {
      return [createConversation()];
    }

    return parsed.length ? parsed : [createConversation()];
  } catch {
    return [createConversation()];
  }
}

function createMessage(role, content, sources = []) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    sources,
    createdAt: Date.now(),
  };
}

function getConversationTitle(question) {
  const cleanQuestion = question.trim();

  if (cleanQuestion.length <= 34) {
    return cleanQuestion;
  }

  return `${cleanQuestion.slice(0, 34).trimEnd()}…`;
}


// Render a safe subset of Markdown as React elements. No HTML is injected.
function renderInlineMarkdown(text, keyPrefix) {
  const tokenPattern =
    /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|\*[^*\n]+\*|_[^_\n]+_)/g;
  const tokens = String(text).split(tokenPattern).filter(Boolean);

  return tokens.map((token, index) => {
    const key = `${keyPrefix}-inline-${index}`;

    if (
      (token.startsWith("**") && token.endsWith("**")) ||
      (token.startsWith("__") && token.endsWith("__"))
    ) {
      return <strong key={key}>{token.slice(2, -2)}</strong>;
    }

    if (token.startsWith("`") && token.endsWith("`")) {
      return <code key={key}>{token.slice(1, -1)}</code>;
    }

    // Markdown links: [label](https://example.com)
    const linkMatch = token.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
    if (linkMatch) {
      const [, label, url] = linkMatch;

      if (/^https?:\/\//i.test(url)) {
        return (
          <a
            key={key}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="message-link"
          >
            {label}
          </a>
        );
      }

      return <React.Fragment key={key}>{label}</React.Fragment>;
    }

    if (
      (token.startsWith("*") && token.endsWith("*")) ||
      (token.startsWith("_") && token.endsWith("_"))
    ) {
      return <em key={key}>{token.slice(1, -1)}</em>;
    }

    return <React.Fragment key={key}>{token}</React.Fragment>;
  });
}

function renderFormattedMessage(content) {
  const lines = String(content || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const trimmed = lines[index].trim();
    const blockKey = `block-${blocks.length}`;

    // Fenced code blocks: ```language ... ```
    const fenceMatch = trimmed.match(/^```(\w*)\s*$/);
    if (fenceMatch) {
      const codeLines = [];
      index += 1;

      while (index < lines.length && lines[index].trim() !== "```") {
        codeLines.push(lines[index]);
        index += 1;
      }

      index += 1; // Skip the closing fence, if present.

      blocks.push(
        <pre className="message-code-block" key={blockKey}>
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    if (!trimmed) {
      blocks.push(<div key={blockKey} aria-hidden="true" style={{ height: 7 }} />);
      index += 1;
      continue;
    }

    // Markdown headings: # Heading, ## Heading, or ### Heading.
    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const headingContent = renderInlineMarkdown(headingMatch[2], blockKey);

      if (level === 1) {
        blocks.push(<h3 className="message-heading" key={blockKey}>{headingContent}</h3>);
      } else if (level === 2) {
        blocks.push(<h4 className="message-heading" key={blockKey}>{headingContent}</h4>);
      } else {
        blocks.push(<h5 className="message-heading" key={blockKey}>{headingContent}</h5>);
      }

      index += 1;
      continue;
    }

    // Also style short, standalone section labels ending in a colon.
    if (
      trimmed.endsWith(":") &&
      trimmed.length <= 85 &&
      !/[.!?].+:$/.test(trimmed) &&
      !/^https?:\/\//i.test(trimmed)
    ) {
      blocks.push(
        <h4 className="message-heading" key={blockKey}>
          {renderInlineMarkdown(trimmed.slice(0, -1), blockKey)}
        </h4>
      );
      index += 1;
      continue;
    }

    const bulletPattern = /^(?:[-*•])\s+(.+)$/;
    if (bulletPattern.test(trimmed)) {
      const items = [];

      while (index < lines.length) {
        const itemMatch = lines[index].trim().match(bulletPattern);
        if (!itemMatch) break;
        items.push(itemMatch[1]);
        index += 1;
      }

      blocks.push(
        <ul className="message-list" key={blockKey}>
          {items.map((item, itemIndex) => (
            <li key={`${blockKey}-${itemIndex}`}>
              {renderInlineMarkdown(item, `${blockKey}-${itemIndex}`)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    const numberPattern = /^(\d+)[.)]\s+(.+)$/;
    if (numberPattern.test(trimmed)) {
      const items = [];

      while (index < lines.length) {
        const itemMatch = lines[index].trim().match(numberPattern);
        if (!itemMatch) break;
        items.push(itemMatch[2]);
        index += 1;
      }

      blocks.push(
        <ol className="message-list" key={blockKey}>
          {items.map((item, itemIndex) => (
            <li key={`${blockKey}-${itemIndex}`}>
              {renderInlineMarkdown(item, `${blockKey}-${itemIndex}`)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    blocks.push(<p key={blockKey}>{renderInlineMarkdown(trimmed, blockKey)}</p>);
    index += 1;
  }

  return blocks;
}

function App() {
  const [conversations, setConversations] = useState(
    loadConversations
  );

  const [activeConversationId, setActiveConversationId] =
    useState(null);

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [connectionError, setConnectionError] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState(null);
  const conversationBottomRef = useRef(null);

  const activeId =
    activeConversationId &&
    conversations.some((conversation) => conversation.id === activeConversationId)
      ? activeConversationId
      : conversations[0]?.id;

  const activeConversation = conversations.find(
    (conversation) => conversation.id === activeId
  );

  const messages = activeConversation?.messages || [];

  // Keep the newest message or loading indicator in view.
  useEffect(() => {
    conversationBottomRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, loading, activeId]);

  // Persist conversations in this browser.
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(conversations)
      );
    } catch (error) {
      console.error("Could not save chat history:", error);
    }
  }, [conversations]);

  function updateConversation(conversationId, updater) {
    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...updater(conversation),
              updatedAt: Date.now(),
            }
          : conversation
      )
    );
  }

  function startNewChat() {
    const conversation = createConversation();

    setConversations((previous) => [
      conversation,
      ...previous,
    ]);

    setActiveConversationId(conversation.id);
    setQuestion("");
    setConnectionError(false);
    setSidebarOpen(false);
  }

  function selectConversation(conversationId) {
    setActiveConversationId(conversationId);
    setQuestion("");
    setConnectionError(false);
    setSidebarOpen(false);
  }

  async function sendMessage(text = question) {
    const trimmedQuestion = text.trim();

    if (!trimmedQuestion || loading) {
      return;
    }

    let conversationId = activeId;

    // Create a conversation if none exists.
    if (!conversationId) {
      const newConversation = createConversation();

      conversationId = newConversation.id;

      setConversations((previous) => [
        newConversation,
        ...previous,
      ]);

      setActiveConversationId(conversationId);
    }

    const userMessage = createMessage(
      "user",
      trimmedQuestion
    );

    // Add the user's message immediately.
    updateConversation(conversationId, (conversation) => {
      const isFirstMessage = conversation.messages.length === 0;

      return {
        ...conversation,
        title: isFirstMessage
          ? getConversationTitle(trimmedQuestion)
          : conversation.title,
        messages: [
          ...conversation.messages,
          userMessage,
        ],
      };
    });

    setQuestion("");
    setLoading(true);
    setConnectionError(false);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
        }),
      });

      let data;

      try {
        data = await response.json();
      } catch {
        throw new Error(
          "The server returned an invalid response. Please try again."
        );
      }

      if (!response.ok) {
        throw new Error(
          data.detail ||
            "Unable to get an answer. Please try again."
        );
      }

      const assistantMessage = createMessage(
        "assistant",
        data.answer || "I couldn't generate an answer.",
        Array.isArray(data.sources) ? data.sources : []
      );

      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: [
          ...conversation.messages,
          assistantMessage,
        ],
      }));
    } catch (error) {
      const isConnectionError =
        error instanceof TypeError ||
        error.message === "Failed to fetch";

      setConnectionError(isConnectionError);

      const errorMessage = isConnectionError
        ? "I couldn't connect to the SynergyAI backend. Please check that the FastAPI server is running."
        : error.message ||
          "Something went wrong. Please try again.";

      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: [
          ...conversation.messages,
          createMessage("assistant", errorMessage),
        ],
      }));
    } finally {
      setLoading(false);
    }
  }

  async function copyAnswer(message) {
    if (!message?.content) {
      return;
    }

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(message.content);
      } else {
        // Fallback for browsers where the Clipboard API is unavailable.
        const textArea = document.createElement("textarea");
        textArea.value = message.content;
        textArea.setAttribute("readonly", "");
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";
        document.body.appendChild(textArea);
        textArea.select();
        const copied = document.execCommand("copy");
        document.body.removeChild(textArea);

        if (!copied) {
          throw new Error("Clipboard copy was not available.");
        }
      }

      setCopiedMessageId(message.id);
      window.setTimeout(() => {
        setCopiedMessageId((currentId) =>
          currentId === message.id ? null : currentId
        );
      }, 1800);
    } catch (error) {
      console.error("Could not copy the answer:", error);
      setCopiedMessageId(null);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    sendMessage();
  }

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      sendMessage();
    }
  }

  const sortedConversations = [...conversations].sort(
    (a, b) => b.updatedAt - a.updatedAt
  );

  return (
    <div className="app">
      {sidebarOpen && (
        <button
          type="button"
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}
      >
        <div className="brand">
          <div className="brand-logo-wrap">
            <img
              src={LOGO_URL}
              alt="Synergy Marine Group"
              className="brand-logo"
            />
          </div>

          <div className="brand-text">
            <h2>SynergyAI</h2>
            <p>Synergy Marine Group</p>
          </div>

          <button
            type="button"
            className="sidebar-close"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close sidebar"
          >
            ×
          </button>
        </div>

        <button
          type="button"
          className="new-chat-button"
          onClick={startNewChat}
        >
          <span className="new-chat-icon">＋</span>
          <span>New conversation</span>
        </button>

        <div className="sidebar-section">
          <p className="sidebar-label">WORKSPACE</p>

          <div className="sidebar-item active">
            <span className="sidebar-item-icon">✦</span>
            <span>Synergy Marine AI</span>
            <span className="active-indicator" />
          </div>
        </div>

        <div className="history-section">
          <div className="history-heading">
            <p className="sidebar-label">RECENT CONVERSATIONS</p>
            <span className="history-count">
              {conversations.length}
            </span>
          </div>

          <div className="history-list">
            {sortedConversations.map((conversation) => (
              <button
                type="button"
                key={conversation.id}
                className={`history-item ${
                  conversation.id === activeId
                    ? "history-item-active"
                    : ""
                }`}
                onClick={() =>
                  selectConversation(conversation.id)
                }
                title={conversation.title}
              >
                <span className="history-item-icon">◷</span>

                <span className="history-item-title">
                  {conversation.title}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="footer-brand-mark">
            <img
              src={LOGO_URL}
              alt=""
              aria-hidden="true"
            />
          </div>

          <div className="footer-info">
            <span className="footer-title">SynergyAI</span>
            <span className="footer-caption">
              Website knowledge assistant
            </span>
          </div>

          <span
            className={`status-dot ${
              connectionError ? "status-dot-error" : ""
            }`}
          />
        </div>
      </aside>

      {/* Main application */}
      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="menu-button"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
            >
              ☰
            </button>

            <div>
              <p className="topbar-label">
                SYNERGY MARINE GROUP
              </p>

              <h3>Ocean Intelligence Assistant</h3>
            </div>
          </div>

          <div className="connection-status">
            <span
              className={`status-dot ${
                connectionError ? "status-dot-error" : ""
              }`}
            />

            <span>
              {connectionError
                ? "Connection issue"
                : "RAG Assistant"}
            </span>
          </div>
        </header>

        {/* Chat messages */}
        <section
          className="chat-area"
          aria-label="Conversation"
        >
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-badge">
                <span className="welcome-badge-dot" />
                YOUR AI KNOWLEDGE PARTNER
              </div>

              <div className="welcome-icon">
                <img
                  src={LOGO_URL}
                  alt="Synergy Marine Group"
                  className="welcome-logo"
                />
              </div>

              <h1>
                Hello, I’m
                <br />
                <span>SynergyAI</span>
              </h1>

              <p className="welcome-description">
                Your AI assistant for Synergy Marine Group. Get
                instant, source-linked answers about our services,
                fleet, sustainability initiatives, ESG practices,
                and more.
              </p>

              <div className="suggestions">
                <div className="suggestions-heading">
                  <p className="suggestions-title">
                    EXPLORE SYNERGY
                  </p>

                  <span>What would you like to know?</span>
                </div>

                <div className="suggestion-grid">
                  {suggestedQuestions.map((item) => (
                    <button
                      type="button"
                      className="suggestion-card"
                      key={item.question}
                      onClick={() =>
                        sendMessage(item.question)
                      }
                      disabled={loading}
                    >
                      <span className="suggestion-icon">
                        {item.icon}
                      </span>

                      <span className="suggestion-copy">
                        <strong>{item.title}</strong>
                        <span>{item.question}</span>
                      </span>

                      <span className="suggestion-arrow">
                        ↗
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="welcome-note">
                <span>✦</span>
                Building a sustainable ocean future — answers grounded
                in indexed Synergy Marine Group website content.
              </div>
            </div>
          ) : (
            <div className="messages">
              <div className="conversation-heading">
                <div>
                  <span className="conversation-eyebrow">
                    CURRENT CONVERSATION
                  </span>

                  <h2>
                    {activeConversation?.title ||
                      "Your conversation"}
                  </h2>
                </div>

                <button
                  type="button"
                  className="clear-chat-button"
                  onClick={startNewChat}
                >
                  ＋ New chat
                </button>
              </div>

              {messages.map((message) => (
                <article
                  className={`message ${message.role}`}
                  key={message.id}
                >
                  <div className="message-avatar">
                    {message.role === "assistant" ? (
                      <img
                        src={LOGO_URL}
                        alt="SynergyAI"
                        className="message-logo"
                      />
                    ) : (
                      <span>Y</span>
                    )}
                  </div>

                  <div className="message-content">
                    <div className="message-meta">
                      <p className="message-author">
                        {message.role === "assistant"
                          ? "SynergyAI"
                          : "You"}
                      </p>

                      <span className="message-time">
                        {new Date(
                          message.createdAt
                        ).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                    </div>

                    <div className="message-text">
                      {renderFormattedMessage(message.content)}
                    </div>

                    {message.role === "assistant" && (
                      <div style={{ display: "flex", justifyContent: "flex-start", marginTop: 8, marginBottom: message.sources?.length ? 12 : 0 }}>
                        <button
                          type="button"
                          onClick={() => copyAnswer(message)}
                          aria-label={copiedMessageId === message.id ? "Answer copied" : "Copy answer"}
                          title={copiedMessageId === message.id ? "Copied!" : "Copy answer"}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 7,
                            padding: "7px 11px",
                            border: "1px solid #dbe5f2",
                            borderRadius: 9,
                            background: copiedMessageId === message.id ? "#effaf3" : "#ffffff",
                            color: copiedMessageId === message.id ? "#18794e" : "#536782",
                            fontSize: 12,
                            fontWeight: 650,
                            cursor: "pointer",
                            transition: "background 150ms ease, border-color 150ms ease, color 150ms ease",
                          }}
                        >
                          <span aria-hidden="true">{copiedMessageId === message.id ? "✓" : "▢"}</span>
                          {copiedMessageId === message.id ? "Copied!" : "Copy answer"}
                        </button>
                      </div>
                    )}

                    {message.sources?.length > 0 && (
                      <div className="sources">
                        <div className="sources-heading">
                          <span className="sources-icon">↗</span>
                          <p>Sources</p>
                          <span className="sources-count">
                            {message.sources.length}
                          </span>
                        </div>

                        {message.sources.map((source) => (
                          <a
                            key={source}
                            href={source}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <span className="source-link-icon">
                              ↗
                            </span>

                            <span className="source-url">
                              {source}
                            </span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              ))}

              {loading && (
                <article className="message assistant">
                  <div className="message-avatar">
                    <img
                      src={LOGO_URL}
                      alt="SynergyAI"
                      className="message-logo"
                    />
                  </div>

                  <div className="message-content">
                    <div className="message-meta">
                      <p className="message-author">
                        SynergyAI
                      </p>

                      <span className="message-time">
                        Working
                      </span>
                    </div>

                    <div
                      className="loading-card"
                      role="status"
                      aria-live="polite"
                    >
                      <div className="loading-dots">
                        <span />
                        <span />
                        <span />
                      </div>

                      <div>
                        <p className="loading-title">
                          Finding your answer
                        </p>

                        <p className="loading-description">
                          Searching website knowledge...
                        </p>
                      </div>
                    </div>
                  </div>
                </article>
              )}

              <div
                className="conversation-bottom"
                ref={conversationBottomRef}
                aria-hidden="true"
              />
            </div>
          )}
        </section>

        {/* Message composer */}
        <footer className="composer-area">
          <form
            className="composer"
            onSubmit={handleSubmit}
          >
            <div className="composer-icon">✦</div>

            <input
              type="text"
              value={question}
              onChange={(event) =>
                setQuestion(event.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about Synergy Marine Group..."
              maxLength={1000}
              disabled={loading}
              aria-label="Your question"
              autoComplete="off"
            />

            <span className="composer-shortcut">
              ↵
            </span>

            <button
              type="submit"
              className="send-button"
              disabled={loading || !question.trim()}
              aria-label="Send message"
              title="Send message"
            >
              ➤
            </button>
          </form>

          <p className="disclaimer">
            <span>✦</span>
            SynergyAI uses indexed website content. Verify
            important information against the original source.
          </p>
        </footer>
      </main>
    </div>
  );
}

export default App;

