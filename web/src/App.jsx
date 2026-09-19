import { useEffect, useRef, useState } from "react";

async function streamChat(history, onEvent) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: history }),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

function applyEvent(message, event) {
  switch (event.type) {
    case "text":
      return { ...message, content: message.content + event.text };
    case "tool_call":
      return {
        ...message,
        toolCalls: [
          ...message.toolCalls,
          { name: event.name, arguments: event.arguments, output: null },
        ],
      };
    case "tool_result": {
      const toolCalls = message.toolCalls.slice();
      for (let i = toolCalls.length - 1; i >= 0; i -= 1) {
        if (toolCalls[i].name === event.name && toolCalls[i].output === null) {
          toolCalls[i] = { ...toolCalls[i], output: event.output };
          break;
        }
      }
      return { ...message, toolCalls };
    }
    case "usage":
      return {
        ...message,
        usage: { input: event.input_tokens, output: event.output_tokens },
      };
    case "error":
      return { ...message, error: event.message };
    default:
      return message;
  }
}

function toolDetail(argument) {
  if (!argument) return "";
  return argument.command || argument.path || JSON.stringify(argument);
}

function ToolCall({ call }) {
  return (
    <details className="tool">
      <summary>
        <span className="tool-name">▶ {call.name}</span>
        <span className="tool-arg">{toolDetail(call.arguments)}</span>
      </summary>
      <pre>{call.output ?? "running…"}</pre>
    </details>
  );
}

function AssistantMessage({ message, busy }) {
  const empty = !message.content && message.toolCalls.length === 0;
  return (
    <div className="row assistant">
      <div className="bubble">
        {message.toolCalls.map((call, i) => (
          <ToolCall key={i} call={call} />
        ))}
        {message.content && <div className="text">{message.content}</div>}
        {busy && empty && <div className="thinking">thinking…</div>}
        {message.error && <div className="error">{message.error}</div>}
        {message.usage && (
          <div className="usage">
            {message.usage.input} in / {message.usage.output} out
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState(null);
  const bottom = useRef(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => setInfo(null));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const history = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user", content: text },
    ];
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", toolCalls: [], usage: null, error: null },
    ]);
    setInput("");
    setBusy(true);
    try {
      await streamChat(history, (event) => {
        setMessages((prev) => {
          const next = prev.slice();
          next[next.length - 1] = applyEvent(next[next.length - 1], event);
          return next;
        });
      });
    } catch (error) {
      setMessages((prev) => {
        const next = prev.slice();
        next[next.length - 1] = {
          ...next[next.length - 1],
          error: String(error.message || error),
        };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  const model = info?.model ? `${info.model}` : "no provider";

  return (
    <div className="app">
      <header>
        <div className="brand">
          <h1>pyagent</h1>
          <span className="sub">probabilistic model · deterministic harness</span>
        </div>
        <div className="status" title={info?.provider || "no API key in the server env"}>
          {model}
        </div>
      </header>

      <main>
        {messages.length === 0 && (
          <div className="empty">
            <p>Ask it to do something in this repo.</p>
            <div className="examples">
              {["list the files here", "explain how the agent loop works", "run the tests"].map(
                (example) => (
                  <button key={example} onClick={() => setInput(example)}>
                    {example}
                  </button>
                ),
              )}
            </div>
          </div>
        )}
        {messages.map((message, i) =>
          message.role === "user" ? (
            <div className="row user" key={i}>
              <div className="bubble">{message.content}</div>
            </div>
          ) : (
            <AssistantMessage
              key={i}
              message={message}
              busy={busy && i === messages.length - 1}
            />
          ),
        )}
        <div ref={bottom} />
      </main>

      <footer>
        <textarea
          value={input}
          placeholder="Ask pyagent…  (Enter to send, Shift+Enter for a newline)"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
        />
        <div className="actions">
          <button className="ghost" onClick={() => setMessages([])} disabled={busy}>
            Clear
          </button>
          <button className="send" onClick={send} disabled={busy || !input.trim()}>
            {busy ? "…" : "Send"}
          </button>
        </div>
      </footer>
    </div>
  );
}
