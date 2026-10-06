import { DragEvent, useEffect, useState } from "react";
import { api, Application, EmailCompose, FollowUpDraft } from "../api";
import { loadSmtpSettings } from "../settings";

const COLUMNS = ["draft", "queued", "sent", "failed"] as const;

export default function KanbanPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [dragId, setDragId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [activeApp, setActiveApp] = useState<Application | null>(null);
  const [compose, setCompose] = useState<EmailCompose | null>(null);
  const [sending, setSending] = useState(false);
  const [sendMsg, setSendMsg] = useState("");
  const [attachCv, setAttachCv] = useState(true);
  const [attachCoverLetter, setAttachCoverLetter] = useState(true);
  const [dueFollowUps, setDueFollowUps] = useState<Application[]>([]);
  const [followUp, setFollowUp] = useState<FollowUpDraft | null>(null);
  const [copied, setCopied] = useState("");

  async function reload() {
    const [allApps, due] = await Promise.all([api.applications(), api.dueFollowUps()]);
    setApps(allApps);
    setDueFollowUps(due);
  }

  useEffect(() => {
    reload().catch((e) => setError(String(e.message || e)));
  }, []);

  async function move(id: string, status: string) {
    const prev = apps;
    setApps((list) => list.map((a) => (a.id === id ? { ...a, status } : a)));
    try {
      await api.updateApplication(id, { status, override_notes: "kanban drag" });
    } catch (e) {
      setApps(prev);
      setError(String((e as Error).message || e));
    }
  }

  async function openFollowUp(app: Application) {
    setActiveApp(app);
    setCompose(null);
    setFollowUp(null);
    setSendMsg("");
    try {
      setFollowUp(await api.followUpDraft(app.id));
    } catch (e) {
      setSendMsg(String((e as Error).message || e));
    }
  }

  async function copyText(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(`${label} copied`);
    } catch {
      setCopied("Copy failed");
    }
  }

  async function openComposer(app: Application) {
    setActiveApp(app);
    setCompose(null);
    setSendMsg("");
    try {
      setCompose(await api.composeEmail(app.id));
    } catch (e) {
      setSendMsg(String((e as Error).message || e));
    }
  }

  async function sendEmail() {
    if (!activeApp || !compose) return;
    setSending(true);
    setSendMsg("");
    try {
      const result = await api.sendEmail(activeApp.id, {
        to: compose.to,
        subject: compose.subject,
        body: compose.body,
        smtp: loadSmtpSettings(),
        attach_cv: attachCv,
        attach_cover_letter: attachCoverLetter,
      });
      setSendMsg(result.detail);
      await reload();
    } catch (e) {
      setSendMsg(String((e as Error).message || e));
    } finally {
      setSending(false);
    }
  }

  function onDrop(status: string) {
    return (e: DragEvent) => {
      e.preventDefault();
      if (dragId) void move(dragId, status);
      setDragId(null);
    };
  }

  const filteredApps = apps.filter((app) => {
    const q = query.trim().toLowerCase();
    const matchesQuery = !q || `${app.id} ${app.draft_body} ${app.opportunity_title || ""} ${app.company_name || ""} ${app.source || ""}`.toLowerCase().includes(q);
    const matchesStatus = !status || app.status === status;
    return matchesQuery && matchesStatus;
  });
  const completedApps = apps.filter((app) => app.status === "sent");

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Applications</h1>
          <p className="page-sub">See applications you did, their original opportunity source, cover letters, and follow-ups.</p>
        </div>
        <button className="btn" type="button" onClick={() => void reload()}>Refresh</button>
      </header>
      {error && <p className="alert danger">{error}</p>}
      <div className="filter-bar">
        <input
          aria-label="Search applications"
          placeholder="Search title, company, source, or draft"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select aria-label="Application status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {COLUMNS.map((col) => <option key={col} value={col}>{col}</option>)}
        </select>
      </div>
      <div className="metrics-grid page-metrics">
        {COLUMNS.map((col) => (
          <div className="metric" key={col}>
            <span>{col}</span>
            <strong className="mono">{apps.filter((app) => app.status === col).length}</strong>
          </div>
        ))}
        <div className="metric">
          <span>follow ups due</span>
          <strong className="mono">{dueFollowUps.length}</strong>
        </div>
        <div className="metric">
          <span>done applications</span>
          <strong className="mono">{completedApps.length}</strong>
        </div>
      </div>
      {dueFollowUps.length > 0 && (
        <div className="tile span-12 followup-strip">
          <div>
            <strong>{dueFollowUps.length} follow-up{dueFollowUps.length === 1 ? "" : "s"} due</strong>
            <p className="muted-text">Open a draft, copy the follow-up, and send it manually from your mailbox or composer.</p>
          </div>
          <button className="btn" type="button" onClick={() => void openFollowUp(dueFollowUps[0])}>
            Open first follow-up
          </button>
        </div>
      )}
      <div className="kanban">
        {COLUMNS.map((col) => (
          <div
            key={col}
            className="kanban-col"
            onDragOver={(e) => e.preventDefault()}
            onDrop={onDrop(col)}
          >
            <h3>{col}</h3>
            {filteredApps.filter((a) => a.status === col).map((a) => (
              <div
                key={a.id}
                className={`kanban-card ${dragId === a.id ? "dragging" : ""}`}
                draggable
                onDragStart={() => setDragId(a.id)}
                onDragEnd={() => setDragId(null)}
              >
                <div className="kanban-card-head">
                  <span className="mono">{a.id.slice(0, 8)}</span>
                  <span className={`badge ${a.status === "sent" ? "success" : a.status === "failed" ? "danger" : "muted"}`}>{a.status}</span>
                </div>
                <strong className="kanban-title">{a.opportunity_title || "Untitled opportunity"}</strong>
                <div className="kanban-meta">
                  <span>{a.company_name || "Unknown company"}</span>
                  <span className="mono">{a.source || "unknown source"}</span>
                </div>
                <div className="kanban-card-body">
                  {a.draft_body.slice(0, 160)}
                </div>
                <div className="kanban-actions">
                  <button className="btn compact" type="button" onClick={() => void openComposer(a)}>Email</button>
                  <button className="btn compact" type="button" onClick={() => void openFollowUp(a)}>Follow-up</button>
                  <button className="btn compact" type="button" onClick={() => api.downloadCoverLetter(a.id)}>ATS PDF</button>
                  {a.source_url && (
                    <a className="btn compact" href={a.source_url} target="_blank" rel="noreferrer">Source</a>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
      {activeApp && (
        <div className="drawer" role="dialog" aria-label="Email composer">
          <div className="drawer-panel">
            <div className="tile-head">
              <div>
                <h3>{followUp ? "Follow-up draft" : "Email application"}</h3>
                <p className="muted-text mono">{activeApp.id.slice(0, 8)}</p>
                <p className="muted-text">{activeApp.opportunity_title || "Untitled opportunity"} · {activeApp.source || "unknown source"}</p>
              </div>
              <button className="btn compact" type="button" onClick={() => setActiveApp(null)}>Close</button>
            </div>
            {!compose && !followUp && !sendMsg && <div className="skeleton" style={{ height: 120 }} />}
            {sendMsg && <p className="alert success mono">{sendMsg}</p>}
            {copied && <p className="alert success mono">{copied}</p>}
            {followUp && (
              <div className="composer-grid">
                <div className="field">
                  <label htmlFor="follow-up-draft">Follow-up draft</label>
                  <textarea
                    id="follow-up-draft"
                    rows={14}
                    value={followUp.draft}
                    onChange={(e) => setFollowUp({ ...followUp, draft: e.target.value })}
                  />
                </div>
                <div className="detail-list">
                  <div><span>Due</span><strong>{followUp.due_at ? new Date(followUp.due_at).toLocaleString() : "Not scheduled"}</strong></div>
                  <div><span>Auto-send</span><strong>{followUp.auto_send ? "enabled" : "disabled"}</strong></div>
                </div>
                <div className="action-row">
                  <button className="btn primary" type="button" onClick={() => void copyText(followUp.draft, "Follow-up")}>
                    Copy follow-up
                  </button>
                </div>
              </div>
            )}
            {compose && (
              <div className="composer-grid">
                <div className="field">
                  <label htmlFor="email-to">To</label>
                  <input
                    id="email-to"
                    type="email"
                    value={compose.to}
                    onChange={(e) => setCompose({ ...compose, to: e.target.value })}
                    placeholder="recruiter@company.com"
                  />
                </div>
                <div className="field">
                  <label htmlFor="email-subject">Subject</label>
                  <input
                    id="email-subject"
                    value={compose.subject}
                    onChange={(e) => setCompose({ ...compose, subject: e.target.value })}
                  />
                </div>
                <div className="field">
                  <label htmlFor="email-body">Body</label>
                  <textarea
                    id="email-body"
                    rows={12}
                    value={compose.body}
                    onChange={(e) => setCompose({ ...compose, body: e.target.value })}
                  />
                </div>
                <div className="attachment-options">
                  <label className="toggle-row">
                    <input type="checkbox" checked={attachCv} onChange={(e) => setAttachCv(e.target.checked)} />
                    <span>Attach CV</span>
                  </label>
                  <label className="toggle-row">
                    <input type="checkbox" checked={attachCoverLetter} onChange={(e) => setAttachCoverLetter(e.target.checked)} />
                    <span>Attach cover letter PDF</span>
                  </label>
                </div>
                <div className="action-row">
                  <button className="btn" type="button" onClick={() => api.downloadCoverLetter(activeApp.id)}>
                    Download ATS PDF
                  </button>
                  <button className="btn primary" type="button" disabled={sending || !compose.to} onClick={() => void sendEmail()}>
                    {sending ? "Sending..." : "Send email"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
