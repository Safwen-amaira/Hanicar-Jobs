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
          ? `✓ ${result.created} draft(s) created, ${result.queued ?? 0} queued for review. ${result.note}`
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
      <header className="page-head">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">{t("tagline")} Automate with a free LLM, then verify every send.</p>
        </div>
        <div className="cta-row">
          <Link className="btn" to="/profiles">Setup profile</Link>
          <Link className="btn" to="/applications/review">
            Review queue{reviewQueue ? ` (${reviewQueue})` : ""}
          </Link>
          <Link className="btn primary" to="/hunt">Run search</Link>
        </div>
      </header>

      {error && <div className="alert danger">{error}</div>}

      <div className="bento">
        {/* Stats row */}
        <div className="tile stat-card span-4">
          <span>Matched</span>
          <strong className="mono">{matched ?? "--"}</strong>
        </div>
        <div className="tile stat-card span-4">
          <span>Suppressed</span>
          <strong className="mono">{suppressed ?? "--"}</strong>
        </div>
        <div className="tile stat-card span-4">
          <span>Sources</span>
          <strong className="mono">{sources?.length ?? "--"}</strong>
        </div>
        <div className="tile stat-card span-4">
          <span>Drafts</span>
          <strong className="mono">{drafts ?? "--"}</strong>
        </div>
        <div className="tile stat-card span-4">
          <span>Review queue</span>
          <strong className="mono">{reviewQueue ?? "--"}</strong>
        </div>
        <div className="tile stat-card span-4">
          <span>Sent</span>
          <strong className="mono">{sent ?? "--"}</strong>
        </div>
        <div className="tile stat-card span-4">
          <span>Candidates</span>
          <strong className="mono">{candidates?.length ?? "--"}</strong>
        </div>

        {/* LLM status card */}
        <div className="tile span-12 llm-status-card">
          <div className="tile-head">
            <h3>Free LLM · Human-in-the-loop</h3>
            <span className={`badge ${isLive ? "success" : "warn"}`}>
              {isLive
                ? `live · ${health?.llm_provider ?? llmStatus?.provider ?? "auto"}`
                : "template fallback"}
            </span>
          </div>

          {/* Chain display */}
          {chain.length > 0 && (
            <div className="llm-chain" style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", margin: "0.5rem 0" }}>
              {chain.map((p, i) => {
                const isActive = activeProviders.includes(p);
                return (
                  <span key={p} style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                    <span className={`badge ${p === "mock" ? "muted" : p === "ollama" ? "muted" : isActive ? "success" : "warn"}`}>
                      {p}
                    </span>
                    {i < chain.length - 1 && <span className="muted-text">→</span>}
                  </span>
                );
              })}
            </div>
          )}

          <p style={{ margin: "0.25rem 0" }}>{health?.llm_hint || llmStatus?.hint || "Loading LLM status…"}</p>
          <p className="muted-text">
            Model {health?.llm_model || llmStatus?.model || "--"} · auto-draft{" "}
            {health?.auto_draft_enabled ? "on" : "off"} · auto-send never.{" "}
            Review &amp; Send is the only delivery step.
          </p>

          {/* Free provider setup links when not live */}
          {!isLive && (
            <div style={{ marginTop: "0.75rem" }}>
              <p style={{ marginBottom: "0.5rem", fontWeight: 600 }}>Enable a free real LLM in under 2 minutes:</p>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {FREE_PROVIDERS.map((p) => (
                  <a
                    key={p.name}
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn"
                    style={{ fontSize: "0.8rem" }}
                  >
                    {p.label} →
                  </a>
                ))}
              </div>
              <p className="muted-text" style={{ marginTop: "0.5rem" }}>
                After getting a free key, set it in <code>.env</code> (e.g. <code>HJ_GROQ_API_KEY=gsk_…</code>) and restart the backend.
                <br />Pollinations (anonymous, no key) is always available as a last resort.
              </p>
            </div>
          )}
        </div>

        {/* Auto-queue trigger */}
        <div className="tile span-4">
          <div className="tile-head"><h3>Quick Actions</h3></div>
          <div className="action-stack">
            <button
              className="btn primary"
              type="button"
              disabled={queueing || !candidates?.length}
              onClick={() => void triggerAutoQueue()}
              style={{ width: "100%", marginBottom: "0.5rem" }}
            >
              {queueing ? "Queueing drafts…" : "⚡ Auto-draft top matches"}
            </button>
            {queueMsg && (
              <p className={`alert ${queueMsg.startsWith("Error") ? "danger" : "success"}`} style={{ fontSize: "0.85rem" }}>
                {queueMsg}
              </p>
            )}
            <Link className="workflow-link" to="/applications/review">
              <strong>Review &amp; Send queue</strong>
              <span>Check recipient, body, attachments — then send one by one.</span>
            </Link>
            <Link className="workflow-link" to="/settings">
              <strong>Configure Gmail SMTP</strong>
              <span>Save and test your Google app password.</span>
            </Link>
            <Link className="workflow-link" to="/profiles">
              <strong>Complete candidate profile</strong>
              <span>Add CV text, skills, and the CV file used for emails.</span>
            </Link>
          </div>
        </div>

        {/* Latest opportunities */}
        <div className="tile span-8">
          <div className="tile-head">
            <h3>Latest opportunities</h3>
            <Link to="/opportunities">View all</Link>
          </div>
          {!ops && <div className="skeleton" style={{ height: 80 }} />}
          {ops && ops.length === 0 && <div className="empty">{t("empty")}</div>}
          {ops && ops.slice(0, 6).map((o) => (
            <Link key={o.id} className="list-row" to={`/opportunities/${o.id}`}>
              <span>{o.title}</span>
              <div className="mono">
                {o.company_name || "--"} / score {o.match_score ?? "--"}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
