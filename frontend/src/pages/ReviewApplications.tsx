import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Application, EmailCompose, LlmStatus } from "../api";
import { loadSmtpSettings } from "../settings";

function statusClass(status: string) {
  if (["sent", "applied", "offer"].includes(status)) return "success";
  if (["rejected", "failed", "withdrawn"].includes(status)) return "danger";
  if (["prepared", "queued", "interviewing"].includes(status)) return "warn";
  return "muted";
}

const CHECKS = [
  { id: "recipient", label: "Recipient is the real apply or recruiter address" },
  { id: "subject", label: "Subject names the role and company accurately" },
  { id: "body", label: "Body is truthful and has no invented credentials" },
  { id: "attachments", label: "CV and cover letter attachments are correct files" },
] as const;

export default function ReviewApplicationsPage() {
  const [params, setParams] = useSearchParams();
  const [apps, setApps] = useState<Application[]>([]);
  const [selectedId, setSelectedId] = useState(params.get("id") || "");
  const [compose, setCompose] = useState<EmailCompose | null>(null);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [attachCv, setAttachCv] = useState(true);
  const [attachCoverLetter, setAttachCoverLetter] = useState(true);
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
  const [aiInstructions, setAiInstructions] = useState("");
  const [showRegenerate, setShowRegenerate] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [prepareMsg, setPrepareMsg] = useState("");

  async function reload() {
    const rows = await api.applications();
    setApps(rows);
    const queueIds = rows
      .filter((app) => ["draft", "prepared", "queued"].includes(app.status))
      .map((app) => app.id);
    const requested = params.get("id") || selectedId;
    const next = queueIds.includes(requested) ? requested : queueIds[0] || "";
    if (next !== selectedId) setSelectedId(next);
  }

  useEffect(() => {
    reload().catch((e) => setError(String(e.message || e)));
    api.llmStatus()
      .then(setLlmStatus)
      .catch(() => null);
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setCompose(null);
      return;
    }
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set("id", selectedId);
      return next;
    }, { replace: true });
    setLoading(true);
    setMsg("");
    setError("");
    setChecks({});
    setConfirmed(false);
    setShowRegenerate(false);
    api.composeEmail(selectedId)
      .then(setCompose)
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [selectedId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "j") selectOffset(1);
      if (e.key === "k") selectOffset(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const selected = useMemo(() => apps.find((app) => app.id === selectedId), [apps, selectedId]);
  const queue = apps.filter((app) => ["draft", "prepared", "queued"].includes(app.status));
  const readyCount = queue.filter((app) => app.contact_email).length;
  const allChecked = CHECKS.every((item) => checks[item.id]);
  const canSend = Boolean(
    compose?.to && compose.subject && compose.body.trim() && allChecked && confirmed && !sending
  );

  function selectOffset(delta: number) {
    if (!queue.length) return;
    const index = Math.max(0, queue.findIndex((app) => app.id === selectedId));
    const next = queue[(index + delta + queue.length) % queue.length];
    setSelectedId(next.id);
  }

  async function verifyAndSend() {
    if (!selected || !compose || !canSend) return;
    setSending(true);
    setMsg("");
    setError("");
    try {
      const result = await api.sendEmail(selected.id, {
        to: compose.to,
        subject: compose.subject,
        body: compose.body,
        smtp: loadSmtpSettings(),
        attach_cv: attachCv,
        attach_cover_letter: attachCoverLetter,
        human_verified: true,
      });
      setMsg(result.detail);
      await reload();
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setSending(false);
    }
  }

  async function regenerateDraft() {
    if (!selected) return;
    setRegenerating(true);
    setMsg("");
    setError("");
    try {
      await api.regenerateApplication(selected.id, {
        instructions: aiInstructions || "Polish the draft for ATS and human readability.",
        tone: "concise",
        include_email_subject: true,
      });
      setMsg("✓ Draft regenerated with the LLM. Reloading compose view…");
      setLoading(true);
      const fresh = await api.composeEmail(selected.id);
      setCompose(fresh);
      setChecks({});
      setConfirmed(false);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setRegenerating(false);
      setLoading(false);
    }
  }

  async function skipCurrent() {
    if (!selected) return;
    await api.updateApplication(selected.id, {
      status: "draft",
      override_notes: "human deferred from review queue",
    });
    await reload();
  }

  async function prepareBatch() {
    setPreparing(true);
    setPrepareMsg("");
    try {
      const result = await api.prepareBatch({
        max_to_prepare: 10,
        statuses: ["draft"],
        persist_contacts: true,
        polish_with_llm: !!llmStatus?.live,
      });
      await reload();
      setPrepareMsg(
        `Prepared ${result.attempted}: ${result.queued} queued, ${result.needs_review} need check, ${result.skipped} skipped.`
      );
    } catch (e) {
      setPrepareMsg(`Error: ${String((e as Error).message || e)}`);
    } finally {
      setPreparing(false);
    }
  }

  const isLive = llmStatus?.live;

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Review &amp; Send</h1>
          <p className="page-sub">
            Automation prepares packages. Delivery happens only after you verify this checklist.
          </p>
        </div>
        <div className="cta-row">
          <span className="kbd-hint">j / k — next or previous</span>
          <button
            className="btn"
            type="button"
            disabled={preparing}
            onClick={() => void prepareBatch()}
          >
            {preparing ? "Preparing…" : "Prepare batch"}
          </button>
          <button className="btn" type="button" onClick={() => void reload()}>Refresh</button>
        </div>
      </header>

      {/* LLM status banner */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "0.6rem 1rem",
        marginBottom: "1rem",
        background: isLive ? "rgba(74, 222, 128, 0.08)" : "rgba(251, 191, 36, 0.08)",
        borderRadius: "0.5rem",
        border: `1px solid ${isLive ? "rgba(74, 222, 128, 0.2)" : "rgba(251, 191, 36, 0.2)"}`,
        fontSize: "0.85rem",
      }}>
        <span className={`badge ${isLive ? "success" : "warn"}`}>
          {isLive ? `🤖 LLM live · ${llmStatus?.provider}` : "📝 template fallback"}
        </span>
        <span style={{ color: "var(--hj-muted)" }}>
          {isLive
            ? `${llmStatus?.model} · drafts use real AI`
            : "No live LLM key set — drafts use templates. Set HJ_GROQ_API_KEY or HJ_OPENROUTER_API_KEY in .env"}
        </span>
        {!isLive && (
          <a href="https://openrouter.ai" target="_blank" rel="noopener noreferrer" className="btn" style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", marginLeft: "auto" }}>
            Get free key →
          </a>
        )}
      </div>

      {prepareMsg && <p className={`alert ${prepareMsg.startsWith("Error") ? "danger" : "success"}`}>{prepareMsg}</p>}

      <div className="review-progress">
        <div>
          <strong>{queue.length}</strong>
          <span>waiting for you</span>
        </div>
        <div>
          <strong>{readyCount}</strong>
          <span>have a recipient</span>
        </div>
        <div>
          <strong>{Math.max(queue.findIndex((app) => app.id === selectedId) + 1, queue.length ? 1 : 0)}</strong>
          <span>of {queue.length || 0} in queue</span>
        </div>
      </div>

      {error && <p className="alert danger">{error}</p>}
      {msg && <p className="alert success mono">{msg}</p>}

      <div className="review-layout">
        <aside className="review-queue">
          <div className="tile-head">
            <h3>Human queue</h3>
            <span className="badge muted">{queue.length}</span>
          </div>
          {queue.length === 0 && (
            <div className="empty">
              Nothing to verify.{" "}
              <button className="btn" type="button" onClick={() => void prepareBatch()} disabled={preparing}>
                {preparing ? "Preparing…" : "Prepare drafts"}
              </button>
            </div>
          )}
          {queue.map((app) => (
            <button
              key={app.id}
              className={`review-item ${selectedId === app.id ? "active" : ""}`}
              type="button"
              onClick={() => setSelectedId(app.id)}
            >
              <strong>{app.opportunity_title || "Untitled opportunity"}</strong>
              <span>{app.company_name || "Unknown company"}</span>
              <small>
                <span className={`badge ${statusClass(app.status)}`}>{app.status}</span>
                {app.contact_email ? " recipient found" : " needs recipient"}
              </small>
            </button>
          ))}
        </aside>

        <section className="review-package">
          {!selected && (
            <div className="empty">Select an application to review.</div>
          )}
          {selected && loading && <div className="skeleton" style={{ height: 220 }} />}
          {selected && compose && !loading && (
            <>
              <div className="review-header">
                <div>
                  <span className="eyebrow">Human verification required</span>
                  <h2>{selected.opportunity_title || "Untitled opportunity"}</h2>
                  <p>{selected.company_name || "Unknown company"} · {selected.source || "unknown source"}</p>
                </div>
                <span className={`badge ${compose.ready ? "success" : "warn"}`}>
                  {compose.ready ? "automation ready" : "needs your check"}
                </span>
              </div>

              <div className="review-fields">
                <label>
                  <span>To</span>
                  <input
                    type="email"
                    value={compose.to}
                    onChange={(e) => setCompose({ ...compose, to: e.target.value })}
                  />
                </label>
                <label>
                  <span>Subject</span>
                  <input
                    value={compose.subject}
                    onChange={(e) => setCompose({ ...compose, subject: e.target.value })}
                  />
                </label>
                <label className="full">
                  <span>Email / cover letter text</span>
                  <textarea
                    rows={14}
                    value={compose.body}
                    onChange={(e) => setCompose({ ...compose, body: e.target.value })}
                  />
                </label>
              </div>

              {/* AI regenerate panel */}
              <div style={{
                background: "rgba(var(--hj-accent-rgb, 99, 102, 241), 0.06)",
                border: "1px solid rgba(99, 102, 241, 0.2)",
                borderRadius: "0.5rem",
                padding: "0.75rem 1rem",
                marginBottom: "1rem",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <strong style={{ fontSize: "0.9rem" }}>
                    🤖 Regenerate with {isLive ? llmStatus?.provider : "template"} LLM
                  </strong>
                  <button
                    className="btn"
                    type="button"
                    style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                    onClick={() => setShowRegenerate((v) => !v)}
                  >
                    {showRegenerate ? "Hide" : "Customize"}
                  </button>
                </div>
                {showRegenerate && (
                  <div style={{ marginTop: "0.5rem" }}>
                    <textarea
                      rows={2}
                      placeholder="Optional: extra instructions e.g. 'make it more formal' or 'emphasise Python experience'"
                      value={aiInstructions}
                      onChange={(e) => setAiInstructions(e.target.value)}
                      style={{ width: "100%", marginBottom: "0.5rem" }}
                    />
                  </div>
                )}
                <button
                  className="btn"
                  type="button"
                  disabled={regenerating}
                  onClick={() => void regenerateDraft()}
                  style={{ marginTop: "0.5rem" }}
                >
                  {regenerating ? "Regenerating…" : `✨ Regenerate draft${isLive ? " with real LLM" : ""}`}
                </button>
                {!isLive && (
                  <span className="muted-text" style={{ fontSize: "0.8rem", marginLeft: "0.5rem" }}>
                    (Set HJ_GROQ_API_KEY or HJ_OPENROUTER_API_KEY for real AI)
                  </span>
                )}
              </div>

              <div className="review-split">
                <div className="review-box">
                  <strong>Attachments</strong>
                  <label className="toggle-row">
                    <input type="checkbox" checked={attachCv} onChange={(e) => setAttachCv(e.target.checked)} />
                    <span>Attach CV</span>
                  </label>
                  <label className="toggle-row">
                    <input
                      type="checkbox"
                      checked={attachCoverLetter}
                      onChange={(e) => setAttachCoverLetter(e.target.checked)}
                    />
                    <span>Attach cover letter</span>
                  </label>
                  {compose.suggested_attachments.map((item) => (
                    <p key={`${item.kind}-${item.filename}`} className="mono">
                      {item.kind}: {item.filename}
                    </p>
                  ))}
                </div>
                <div className="review-box">
                  <strong>Automation checks</strong>
                  {compose.warnings.length === 0 ? (
                    <p className="badge success">No blocking warnings</p>
                  ) : (
                    compose.warnings.map((warning) => (
                      <p key={warning} className="alert warn">{warning}</p>
                    ))
                  )}
                  <p className="muted-text">
                    Only email, phone, LinkedIn, and GitHub links should appear in the signature.
                  </p>
                </div>
              </div>

              {/* Human verification checklist */}
              <div className="verify-card">
                <strong>Your verification — human gates this send</strong>
                {CHECKS.map((item) => (
                  <label key={item.id} className="toggle-row">
                    <input
                      type="checkbox"
                      checked={Boolean(checks[item.id])}
                      onChange={(e) =>
                        setChecks((current) => ({ ...current, [item.id]: e.target.checked }))
                      }
                    />
                    <span>{item.label}</span>
                  </label>
                ))}
                <label className="toggle-row confirm-row">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  <span>I reviewed this package and take responsibility for sending it.</span>
                </label>
              </div>

              <div className="action-row wrap review-actions">
                <button className="btn" type="button" onClick={() => selectOffset(-1)}>Previous</button>
                <button className="btn" type="button" onClick={() => selectOffset(1)}>Next</button>
                <button className="btn" type="button" onClick={() => void skipCurrent()}>Defer</button>
                <button className="btn" type="button" onClick={() => api.downloadCoverLetter(selected.id)}>
                  Preview cover letter PDF
                </button>
                <button className="btn" type="button" onClick={() => api.downloadCvPdf(selected.id)}>
                  Preview CV PDF
                </button>
                <button
                  className="btn primary"
                  type="button"
                  disabled={!canSend}
                  onClick={() => void verifyAndSend()}
                >
                  {sending ? "Sending…" : "✓ Verify and send this one"}
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
