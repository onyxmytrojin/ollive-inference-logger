import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";

function formatLatency(ms) {
  if (ms == null) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`;
}

export default function MessageBubble({
  message,
  precedingUserMessageId,
  isLastAssistant,
  onRegenerate,
  regenerating,
}) {
  const [copied, setCopied] = useState(false);
  const [inspectOpen, setInspectOpen] = useState(false);
  const [inference, setInference] = useState(null);
  const [inferenceError, setInferenceError] = useState(null);
  const [loadingInference, setLoadingInference] = useState(false);

  const isAssistant = message.role === "assistant";

  async function handleCopy() {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function toggleInspect() {
    const next = !inspectOpen;
    setInspectOpen(next);
    if (next && !inference && !loadingInference && precedingUserMessageId) {
      setLoadingInference(true);
      setInferenceError(null);
      try {
        setInference(await api.getMessageInference(precedingUserMessageId));
      } catch (err) {
        setInferenceError(err.message);
      } finally {
        setLoadingInference(false);
      }
    }
  }

  return (
    <div className={`message ${message.role}`}>
      <div className="bubble-stack">
        <div className="bubble">
          {isAssistant ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          ) : (
            message.content
          )}
        </div>

        <div className="bubble-actions">
          <button className="bubble-action-btn" onClick={handleCopy} title="Copy message">
            {copied ? "Copied" : "Copy"}
          </button>
          {isAssistant && precedingUserMessageId && (
            <button className="bubble-action-btn" onClick={toggleInspect} title="Inspect inference">
              {inspectOpen ? "Hide details" : "Inspect"}
            </button>
          )}
          {isAssistant && isLastAssistant && onRegenerate && (
            <button
              className="bubble-action-btn"
              onClick={onRegenerate}
              disabled={regenerating}
              title="Regenerate response"
            >
              {regenerating ? "Regenerating…" : "Regenerate"}
            </button>
          )}
        </div>

        {inspectOpen && (
          <div className="inspect-panel">
            {loadingInference && <div className="inspect-row muted">Loading…</div>}
            {inferenceError && <div className="inspect-row error">{inferenceError}</div>}
            {inference && (
              <>
                <div className="inspect-row">
                  <span>Model</span>
                  <span>{inference.model}</span>
                </div>
                <div className="inspect-row">
                  <span>Provider</span>
                  <span>{inference.provider}</span>
                </div>
                <div className="inspect-row">
                  <span>Status</span>
                  <span className={`status-pill ${inference.status}`}>{inference.status}</span>
                </div>
                <div className="inspect-row">
                  <span>Latency</span>
                  <span>{formatLatency(inference.latency_ms)}</span>
                </div>
                <div className="inspect-row">
                  <span>Tokens (prompt / completion / total)</span>
                  <span>
                    {inference.prompt_tokens ?? "—"} / {inference.completion_tokens ?? "—"} /{" "}
                    {inference.total_tokens ?? "—"}
                  </span>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
