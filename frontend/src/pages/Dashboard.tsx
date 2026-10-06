import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, Application, Candidate, Health, LlmStatus, Opportunity, SourceHealth } from "../api";

const FREE_PROVIDERS = [
  { name: "groq", label: "Groq (free)", url: "https://console.groq.com", envKey: "HJ_GROQ_API_KEY", model: "llama-3.3-70b-versatile" },
  { name: "openrouter", label: "OpenRouter (free models)", url: "https://openrouter.ai", envKey: "HJ_OPENROUTER_API_KEY", model: "meta-llama/llama-3.2-3b-instruct:free" },
  { name: "gemini", label: "Gemini (free tier)", url: "https://aistudio.google.com", envKey: "HJ_GEMINI_API_KEY", model: "gemini-2.0-flash" },
];

export default function DashboardPage() {
  const { t } = useTranslation();
  const [ops, setOps] = useState<Opportunity[] | null>(null);
  const [sources, setSources] = useState<SourceHealth[] | null>(null);
  const [apps, setApps] = useState<Application[] | null>(null);
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queueing, setQueueing] = useState(false);
  const [queueMsg, setQueueMsg] = useState("");

  useEffect(() => {
    Promise.all([
      api.opportunities(),
      api.sources(),
      api.applications(),
      api.candidates(),
      api.health(),
      api.llmStatus().catch(() => null),
    ])
      .then(([o, s, a, c, h, ls]) => {
        setOps(o);
        setSources(s);
        setApps(a);
        setCandidates(c);
        setHealth(h);
        setLlmStatus(ls);
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  const matched = ops?.filter((o) => o.status === "matched").length;
  const suppressed = ops?.filter((o) => o.status === "suppressed").length;
  const drafts = apps?.filter((a) => a.status === "draft").length;
  const reviewQueue = apps?.filter((a) => ["draft", "prepared", "queued"].includes(a.status)).length;
  const sent = apps?.filter((a) => a.status === "sent").length;

  async function triggerAutoQueue() {
    const first = candidates?.[0];
    if (!first) { setQueueMsg("Create a candidate first."); return; }
    setQueueing(true);
    setQueueMsg("");
    try {
      const result = await api.autoQueue({
        candidate_id: first.id,
        min_score: 55,
        max_to_draft: 6,
        polish_with_llm: true,
      });
      const [fresh] = await Promise.all([api.applications()]);
      setApps(fresh);
      setQueueMsg(
        result.created > 0
          ? `✓ ${result.created} draft(s) created and queued for your review. ${result.note}`
          : `Nothing new to queue. ${result.note}`
      );
    } catch (e) {
      setQueueMsg(`Error: ${String((e as Error).message || e)}`);
    } finally {
      setQueueing(false);
    }
  }

  const isLive = health?.llm_live || llmStatus?.live;
  const chain = llmStatus?.chain ?? [];
  const activeProviders = chain.filter((p) => !["mock", "ollama"].includes(p));

  return (
    <div>
      <header className="page-head" style={{ marginBottom: "1.5rem" }}>
        <div>
          <h1 className="page-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span>Dashboard</span>
            <span style={{ fontSize: "0.85rem", padding: "2px 8px", borderRadius: "12px", background: "rgba(217,119,6,0.15)", color: "var(--hj-gold, #d97706)", border: "1px solid rgba(217,119,6,0.3)" }}>
              Human-in-the-Loop AI
            </span>
          </h1>
          <p className="page-sub">{t("tagline")} Automate drafting with free AI, verify every email before sending.</p>
        </div>
        <div className="cta-row">
          <Link className="btn" to="/profiles">👤 Setup Profile</Link>
          <Link className="btn primary" to="/applications/review">
            📝 Review Queue{reviewQueue ? ` (${reviewQueue})` : ""}
          </Link>
          <Link className="btn" to="/hunt">🚀 Run Search</Link>
        </div>
      </header>

      {error && <div className="alert danger" style={{ marginBottom: "1rem" }}>{error}</div>}

      <div className="bento">
        {/* Key Metrics Cards */}
        <div className="tile stat-card span-3">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--hj-muted, #94a3b8)", fontSize: "0.85rem" }}>Matched Jobs</span>
            <span style={{ fontSize: "1.3rem" }}>🎯</span>
          </div>
          <strong className="mono" style={{ fontSize: "1.8rem", marginTop: "0.4rem", display: "block" }}>{matched ?? "--"}</strong>
        </div>

        <div className="tile stat-card span-3">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--hj-muted, #94a3b8)", fontSize: "0.85rem" }}>Review Queue</span>
            <span style={{ fontSize: "1.3rem" }}>📝</span>
          </div>
          <strong className="mono" style={{ fontSize: "1.8rem", marginTop: "0.4rem", display: "block", color: reviewQueue ? "var(--hj-gold, #d97706)" : "inherit" }}>
            {reviewQueue ?? "--"}
          </strong>
        </div>

        <div className="tile stat-card span-3">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--hj-muted, #94a3b8)", fontSize: "0.85rem" }}>Drafts Prepared</span>
            <span style={{ fontSize: "1.3rem" }}>📄</span>
          </div>
          <strong className="mono" style={{ fontSize: "1.8rem", marginTop: "0.4rem", display: "block" }}>{drafts ?? "--"}</strong>
        </div>

        <div className="tile stat-card span-3">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--hj-muted, #94a3b8)", fontSize: "0.85rem" }}>Emails Sent</span>
            <span style={{ fontSize: "1.3rem" }}>✉️</span>
          </div>
          <strong className="mono" style={{ fontSize: "1.8rem", marginTop: "0.4rem", display: "block", color: "#10b981" }}>{sent ?? "--"}</strong>
        </div>

        {/* Secondary Metrics Row */}
        <div className="tile stat-card span-4">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--hj-muted, #94a3b8)", fontSize: "0.85rem" }}>Sources Active</span>
            <span style={{ fontSize: "1.1rem" }}>🔌</span>
          </div>
          <strong className="mono" style={{ fontSize: "1.3rem", marginTop: "0.2rem", display: "block" }}>{sources?.length ?? "--"}</strong>
        </div>

        <div className="tile stat-card span-4">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--hj-muted, #94a3b8)", fontSize: "0.85rem" }}>Suppressed Jobs</span>
            <span style={{ fontSize: "1.1rem" }}>🚫</span>
          </div>
          <strong className="mono" style={{ fontSize: "1.3rem", marginTop: "0.2rem", display: "block" }}>{suppressed ?? "--"}</strong>
        </div>

        <div className="tile stat-card span-4">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "var(--hj-muted, #94a3b8)", fontSize: "0.85rem" }}>Candidates</span>
            <span style={{ fontSize: "1.1rem" }}>👤</span>
          </div>
          <strong className="mono" style={{ fontSize: "1.3rem", marginTop: "0.2rem", display: "block" }}>{candidates?.length ?? "--"}</strong>
        </div>

        {/* LLM Status Card */}
        <div className="tile span-8 llm-status-card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
          <div>
            <div className="tile-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", margin: 0 }}>
                <span>🤖 Free LLM Provider</span>
              </h3>
              <span className={`badge ${isLive ? "success" : "warn"}`} style={{ padding: "3px 10px", borderRadius: "12px", fontWeight: 600 }}>
                {isLive ? `Live · ${health?.llm_provider ?? llmStatus?.provider ?? "auto"}` : "Fallback mode"}
              </span>
            </div>

            {chain.length > 0 && (
              <div className="llm-chain" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "0.5rem 0 1rem 0" }}>
                {chain.map((p, i) => {
                  const isActive = activeProviders.includes(p);
                  return (
                    <span key={p} style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                      <span className={`badge ${p === "mock" ? "muted" : p === "ollama" ? "muted" : isActive ? "success" : "warn"}`} style={{ fontSize: "0.8rem" }}>
                        {p}
                      </span>
                      {i < chain.length - 1 && <span className="muted-text" style={{ fontSize: "0.8rem" }}>→</span>}
                    </span>
                  );
                })}
              </div>
            )}

            <p style={{ margin: "0.4rem 0", fontSize: "0.92rem", color: "var(--hj-text-main, #e2e8f0)" }}>
              {health?.llm_hint || llmStatus?.hint || "Checking LLM provider status..."}
            </p>
            <p className="muted-text" style={{ fontSize: "0.82rem", margin: "0.25rem 0" }}>
              Model: <code style={{ background: "rgba(255,255,255,0.08)", padding: "1px 6px", borderRadius: "4px" }}>{health?.llm_model || llmStatus?.model || "--"}</code> · Auto-drafting is{" "}
              <strong>{health?.auto_draft_enabled ? "enabled" : "disabled"}</strong>. Auto-sending is <strong>strictly disabled</strong> (human verification required).
            </p>
          </div>

          {!isLive && (
            <div style={{ marginTop: "1rem", paddingTop: "0.75rem", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
              <p style={{ marginBottom: "0.5rem", fontWeight: 600, fontSize: "0.85rem" }}>🚀 Connect a free LLM provider key in seconds:</p>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {FREE_PROVIDERS.map((p) => (
                  <a
                    key={p.name}
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn"
                    style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
                  >
                    {p.label} →
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Quick Actions Panel */}
        <div className="tile span-4">
          <div className="tile-head" style={{ marginBottom: "0.85rem" }}>
            <h3 style={{ margin: 0 }}>⚡ Quick Actions</h3>
          </div>
          <div className="action-stack" style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
            <button
              className="btn primary"
              type="button"
              disabled={queueing || !candidates?.length}
              onClick={() => void triggerAutoQueue()}
              style={{ width: "100%", padding: "0.65rem", fontWeight: 600, display: "flex", justifyContent: "center", alignItems: "center", gap: "0.4rem" }}
            >
              {queueing ? "⚡ Drafting..." : "⚡ Auto-draft top matches"}
            </button>
            {queueMsg && (
              <p className={`alert ${queueMsg.startsWith("Error") ? "danger" : "success"}`} style={{ fontSize: "0.82rem", margin: 0, padding: "0.5rem" }}>
                {queueMsg}
              </p>
            )}
            <Link className="workflow-link" to="/applications/review" style={{ textDecoration: "none", padding: "0.65rem", background: "rgba(255,255,255,0.03)", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.06)", transition: "all 0.15s ease" }}>
              <strong style={{ display: "block", color: "#fff", fontSize: "0.88rem" }}>📝 Review &amp; Send Queue</strong>
              <span style={{ fontSize: "0.78rem", color: "var(--hj-muted, #94a3b8)" }}>Verify recipient, email body, and attachments before sending.</span>
            </Link>
            <Link className="workflow-link" to="/settings" style={{ textDecoration: "none", padding: "0.65rem", background: "rgba(255,255,255,0.03)", borderRadius: "6px", border: "1px solid rgba(255,255,255,0.06)", transition: "all 0.15s ease" }}>
              <strong style={{ display: "block", color: "#fff", fontSize: "0.88rem" }}>⚙️ Configure SMTP &amp; Keys</strong>
              <span style={{ fontSize: "0.78rem", color: "var(--hj-muted, #94a3b8)" }}>Manage email server settings and AI provider keys.</span>
            </Link>
          </div>
        </div>

        {/* Opportunities List */}
        <div className="tile span-12">
          <div className="tile-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h3 style={{ margin: 0 }}>💼 Recent Opportunities</h3>
            <Link to="/opportunities" style={{ fontSize: "0.85rem", color: "var(--hj-gold, #d97706)", textDecoration: "none", fontWeight: 600 }}>
              View all opportunities →
            </Link>
          </div>
          {!ops && <div className="skeleton" style={{ height: 80 }} />}
          {ops && ops.length === 0 && <div className="empty">{t("empty")}</div>}
          {ops && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
              {ops.slice(0, 5).map((o) => (
                <Link
                  key={o.id}
                  className="list-row"
                  to={`/opportunities/${o.id}`}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "0.65rem 0.85rem",
                    background: "rgba(255,255,255,0.03)",
                    borderRadius: "6px",
                    textDecoration: "none",
                    transition: "background 0.15s ease",
                  }}
                >
                  <div style={{ display: "flex", flexDirection: "column" }}>
                    <span style={{ fontWeight: 600, color: "#fff", fontSize: "0.92rem" }}>{o.title}</span>
                    <span style={{ fontSize: "0.78rem", color: "var(--hj-muted, #94a3b8)" }}>{o.company_name || "Company unlisted"}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span className="mono" style={{ fontSize: "0.82rem", background: "rgba(217,119,6,0.15)", color: "var(--hj-gold, #d97706)", padding: "2px 8px", borderRadius: "10px", fontWeight: 600 }}>
                      Score: {o.match_score ?? "--"}
                    </span>
                    <span style={{ fontSize: "0.82rem", color: "var(--hj-muted, #94a3b8)" }}>→</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
