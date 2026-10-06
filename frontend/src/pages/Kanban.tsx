import { DragEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Application, BatchPreviewItem, EmailCompose, FollowUpDraft } from "../api";
import { loadSmtpSettings } from "../settings";

const STATUSES = ["draft", "prepared", "queued", "sent", "applied", "interviewing", "offer", "rejected", "withdrawn", "failed"] as const;
const BOARD_STATUSES = ["draft", "prepared", "queued", "applied", "interviewing", "offer"] as const;

function toLocalInput(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function fromLocalInput(value: string) {
  return value ? new Date(value).toISOString() : undefined;
}

function statusClass(status: string) {
  if (["sent", "applied", "offer"].includes(status)) return "success";
  if (["rejected", "failed", "withdrawn"].includes(status)) return "danger";
  if (["interviewing", "queued", "prepared"].includes(status)) return "warn";
  return "muted";
}

export default function KanbanPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [dragId, setDragId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [view, setView] = useState<"board" | "list">("board");
  const [activeApp, setActiveApp] = useState<Application | null>(null);
  const [compose, setCompose] = useState<EmailCompose | null>(null);
  const [followUp, setFollowUp] = useState<FollowUpDraft | null>(null);
  const [sending, setSending] = useState(false);
  const [working, setWorking] = useState(false);
  const [sendMsg, setSendMsg] = useState("");
  const [attachCv, setAttachCv] = useState(true);
  const [attachCoverLetter, setAttachCoverLetter] = useState(true);
  const [dueFollowUps, setDueFollowUps] = useState<Application[]>([]);
  const [copied, setCopied] = useState("");
  const [aiInstructions, setAiInstructions] = useState("");
  const [tone, setTone] = useState("concise");
  const [batchMax, setBatchMax] = useState(5);
  const [batchDelay, setBatchDelay] = useState(12);
  const [batchWorking, setBatchWorking] = useState(false);
  const [batchMsg, setBatchMsg] = useState("");
  const [batchRows, setBatchRows] = useState<BatchPreviewItem[]>([]);
  const [manualOverride, setManualOverride] = useState(false);

  async function reload() {
    const [allApps, due] = await Promise.all([api.applications(), api.dueFollowUps()]);
    setApps(allApps);
    setDueFollowUps(due);
    if (activeApp) {
      setActiveApp(allApps.find((app) => app.id === activeApp.id) || activeApp);
    }
  }

  useEffect(() => {
    reload().catch((e) => setError(String(e.message || e)));
  }, []);

  async function patchApp(id: string, body: Parameters<typeof api.updateApplication>[1]) {
    const previous = apps;
    setError(null);
    try {
      const updated = await api.updateApplication(id, body);
      setApps((list) => list.map((app) => (app.id === id ? updated : app)));
      if (activeApp?.id === id) setActiveApp(updated);
    } catch (e) {
      setApps(previous);
      setError(String((e as Error).message || e));
    }
  }

  async function move(id: string, nextStatus: string) {
    setApps((list) => list.map((app) => (app.id === id ? { ...app, status: nextStatus } : app)));
    await patchApp(id, { status: nextStatus, override_notes: "tracker status change" });
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
    setFollowUp(null);
    setSendMsg("");
    try {
      setCompose(await api.composeEmail(app.id));
    } catch (e) {
      setSendMsg(String((e as Error).message || e));
    }
  }

  async function regenerateDraft() {
    if (!activeApp) return;
    setWorking(true);
    setSendMsg("");
    try {
      const updated = await api.regenerateApplication(activeApp.id, {
        instructions: aiInstructions,
        tone,
        include_email_subject: true,
      });
      setActiveApp(updated);
      setApps((list) => list.map((app) => (app.id === updated.id ? updated : app)));
      setCompose(await api.composeEmail(updated.id));
      setSendMsg("Draft refreshed with the configured LLM provider.");
    } catch (e) {
      setSendMsg(String((e as Error).message || e));
    } finally {
      setWorking(false);
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
        manual_recontact_override: manualOverride,
        human_verified: true,
      });
      setSendMsg(result.detail);
      await reload();
    } catch (e) {
      setSendMsg(String((e as Error).message || e));
    } finally {
      setSending(false);
    }
  }

  async function discoverContact() {
    if (!activeApp) return;
    setWorking(true);
    setSendMsg("");
    try {
      const found = await api.discoverContact(activeApp.id);
      const updated = await api.updateApplication(activeApp.id, { contact_email: found.selected_email || activeApp.contact_email });
      setActiveApp(updated);
      setApps((list) => list.map((app) => (app.id === updated.id ? updated : app)));
      setSendMsg(found.selected_email ? `Contact found: ${found.selected_email}` : "No email found. Apply URL may still be available on the source page.");
    } catch (e) {
      setSendMsg(String((e as Error).message || e));
    } finally {
      setWorking(false);
    }
  }

  async function previewBatch() {
    setBatchWorking(true);
    setBatchMsg("");
    setError(null);
    try {
      const result = await api.batchSend({
        max_to_send: batchMax,
        delay_seconds: batchDelay,
        statuses: ["draft", "prepared", "queued"],
        smtp: loadSmtpSettings(),
        attach_cv: attachCv,
        attach_cover_letter: attachCoverLetter,
        dry_run: true,
        manual_recontact_override: manualOverride,
      });
      setBatchRows(result.results);
      setBatchMsg(`Preview: ${result.attempted} checked, ${result.results.filter((row) => row.ready).length} ready for human review, ${result.skipped} skipped.`);
    } catch (e) {
      setBatchMsg(String((e as Error).message || e));
    } finally {
      setBatchWorking(false);
    }
  }

  async function prepareReviewQueue() {
    setBatchWorking(true);
    setBatchMsg("");
    setError(null);
    try {
      const result = await api.prepareBatch({
        max_to_prepare: batchMax,
        statuses: ["draft", "prepared", "queued"],
        persist_contacts: true,
      });
      setBatchRows(result.results);
      setBatchMsg(`Prepared ${result.queued} for review, ${result.needs_review} need a human fix, ${result.skipped} skipped.`);
      await reload();
    } catch (e) {
      setBatchMsg(String((e as Error).message || e));
    } finally {
      setBatchWorking(false);
    }
  }

  function onDrop(nextStatus: string) {
    return (e: DragEvent) => {
      e.preventDefault();
      if (dragId) void move(dragId, nextStatus);
      setDragId(null);
    };
  }

  const filteredApps = useMemo(() => {
    return apps.filter((app) => {
      const q = query.trim().toLowerCase();
      const haystack = `${app.id} ${app.draft_body} ${app.opportunity_title || ""} ${app.company_name || ""} ${app.source || ""} ${app.notes || ""}`.toLowerCase();
      return (!q || haystack.includes(q)) && (!status || app.status === status);
    });
  }, [apps, query, status]);

  const metrics = {
    active: apps.filter((app) => !["rejected", "withdrawn", "failed"].includes(app.status)).length,
    review: apps.filter((app) => ["draft", "prepared", "queued"].includes(app.status)).length,
    interviews: apps.filter((app) => app.status === "interviewing").length,
    due: dueFollowUps.length,
  };

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Applications CRM</h1>
          <p className="page-sub">Prepare packages automatically, then verify each send yourself.</p>
        </div>
        <div className="cta-row">
          <button className="btn" type="button" onClick={() => void reload()}>Refresh</button>
          <Link className="btn primary" to="/applications/review">Review & Send</Link>
          <div className="segmented" aria-label="Application view">
            <button className="segment" type="button" aria-pressed={view === "board"} onClick={() => setView("board")}>Board</button>
            <button className="segment" type="button" aria-pressed={view === "list"} onClick={() => setView("list")}>List</button>
          </div>
        </div>
      </header>
      {error && <p className="alert danger">{error}</p>}
      <div className="tracker-hero">
        <div>
          <span className="eyebrow">Pipeline command center</span>
          <h2>From matched role to recruiter-ready package.</h2>
          <p>Prepare a paced review queue, then send only the packages you have personally checked.</p>
        </div>
        <div className="metrics-grid tracker-metrics">
          <div className="metric"><span>active</span><strong className="mono">{metrics.active}</strong></div>
          <div className="metric"><span>to review</span><strong className="mono">{metrics.review}</strong></div>
          <div className="metric"><span>interviews</span><strong className="mono">{metrics.interviews}</strong></div>
          <div className="metric"><span>due</span><strong className="mono">{metrics.due}</strong></div>
        </div>
      </div>
      <div className="auto-sender-panel">
        <div>
          <span className="eyebrow">Human-in-the-loop automation</span>
          <h3>Prepare a review queue. Never auto-send.</h3>
          <p>Automation finds apply emails, skips duplicate companies, and marks ready packages as queued. Sending stays on Review & Send.</p>
        </div>
        <div className="sender-controls">
          <label className="mini-field">
            <span>Max to prepare</span>
            <input type="number" min={1} max={50} value={batchMax} onChange={(e) => setBatchMax(Number(e.target.value))} />
          </label>
          <label className="mini-field">
            <span>Pacing hint (sec)</span>
            <input type="number" min={0} max={3600} value={batchDelay} onChange={(e) => setBatchDelay(Number(e.target.value))} />
          </label>
          <label className="toggle-row"><input type="checkbox" checked={manualOverride} onChange={(e) => setManualOverride(e.target.checked)} /><span>Allow recontact override in preview</span></label>
          <button className="btn" type="button" disabled={batchWorking} onClick={() => void previewBatch()}>{batchWorking ? "Working..." : "Preview"}</button>
          <button className="btn primary" type="button" disabled={batchWorking} onClick={() => void prepareReviewQueue()}>{batchWorking ? "Working..." : "Prepare review queue"}</button>
          <Link className="btn" to="/applications/review">Open review</Link>
        </div>
        {batchMsg && <p className="alert success mono">{batchMsg}</p>}
        {batchRows.length > 0 && (
          <div className="table-wrap batch-preview">
            <table className="table">
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Company</th>
                  <th>To</th>
                  <th>Status</th>
                  <th>Check</th>
                </tr>
              </thead>
              <tbody>
                {batchRows.map((row) => (
                  <tr key={row.application_id}>
                    <td>{row.opportunity_title || row.application_id.slice(0, 8)}</td>
                    <td>{row.company_name || "--"}</td>
                    <td className="mono">{row.to || "--"}</td>
                    <td><span className={`badge ${row.ready ? "success" : "warn"}`}>{row.status}</span></td>
                    <td>{row.ready ? "Ready for you" : row.detail || "Needs a human fix"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="filter-bar tracker-filter">
        <input aria-label="Search applications" placeholder="Search title, company, notes, source, or draft" value={query} onChange={(e) => setQuery(e.target.value)} />
        <select aria-label="Application status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((col) => <option key={col} value={col}>{col}</option>)}
        </select>
      </div>
      {dueFollowUps.length > 0 && (
        <div className="tile span-12 followup-strip">
          <div>
            <strong>{dueFollowUps.length} follow-up{dueFollowUps.length === 1 ? "" : "s"} due</strong>
            <p className="muted-text">Open a draft, copy the follow-up, and send it manually from your mailbox or composer.</p>
          </div>
          <button className="btn" type="button" onClick={() => void openFollowUp(dueFollowUps[0])}>Open first follow-up</button>
        </div>
      )}
      {view === "board" ? (
        <div className="kanban luxe-board">
          {BOARD_STATUSES.map((col) => (
            <div key={col} className="kanban-col" onDragOver={(e) => e.preventDefault()} onDrop={onDrop(col)}>
              <h3>{col}</h3>
              {filteredApps.filter((a) => a.status === col).map((a) => (
                <ApplicationCard
                  key={a.id}
                  app={a}
                  dragId={dragId}
                  onDragStart={() => setDragId(a.id)}
                  onDragEnd={() => setDragId(null)}
                  onOpen={() => setActiveApp(a)}
                  onEmail={() => void openComposer(a)}
                  onFollowUp={() => void openFollowUp(a)}
                />
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Company</th>
                <th>Status</th>
                <th>Applied</th>
                <th>Next action</th>
                <th>Contact</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {filteredApps.map((app) => (
                <tr key={app.id}>
                  <td><button className="link-button" type="button" onClick={() => setActiveApp(app)}>{app.opportunity_title || "Untitled opportunity"}</button></td>
                  <td>{app.company_name || "Unknown"}</td>
                  <td><span className={`badge ${statusClass(app.status)}`}>{app.status}</span></td>
                  <td className="mono">{app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "--"}</td>
                  <td className="mono">{app.next_action_at ? new Date(app.next_action_at).toLocaleString() : "--"}</td>
                  <td>{app.contact_email || app.contact_name || "--"}</td>
                  <td className="mono">{app.source || "--"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {activeApp && (
        <div className="drawer" role="dialog" aria-label="Application workspace">
          <div className="drawer-panel wide">
            <div className="tile-head">
              <div>
                <h3>{activeApp.opportunity_title || "Untitled opportunity"}</h3>
                <p className="muted-text">{activeApp.company_name || "Unknown company"} · {activeApp.source || "unknown source"}</p>
              </div>
              <button className="btn compact" type="button" onClick={() => setActiveApp(null)}>Close</button>
            </div>
            {sendMsg && <p className={`alert ${sendMsg.toLowerCase().includes("failed") ? "danger" : "success"} mono`}>{sendMsg}</p>}
            {copied && <p className="alert success mono">{copied}</p>}
            <div className="workspace-grid">
              <div>
                <div className="field">
                  <label>Status</label>
                  <select value={activeApp.status} onChange={(e) => void patchApp(activeApp.id, { status: e.target.value, override_notes: "status edited" })}>
                    {STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>Contact name</label>
                  <input value={activeApp.contact_name || ""} onChange={(e) => setActiveApp({ ...activeApp, contact_name: e.target.value })} onBlur={() => void patchApp(activeApp.id, { contact_name: activeApp.contact_name })} />
                </div>
                <div className="field">
                  <label>Contact email</label>
                  <input type="email" value={activeApp.contact_email || ""} onChange={(e) => setActiveApp({ ...activeApp, contact_email: e.target.value })} onBlur={() => void patchApp(activeApp.id, { contact_email: activeApp.contact_email })} />
                </div>
                <div className="date-grid">
                  <div className="field">
                    <label>Applied</label>
                    <input type="datetime-local" value={toLocalInput(activeApp.applied_at)} onChange={(e) => void patchApp(activeApp.id, { applied_at: fromLocalInput(e.target.value) })} />
                  </div>
                  <div className="field">
                    <label>Interview</label>
                    <input type="datetime-local" value={toLocalInput(activeApp.interview_at)} onChange={(e) => void patchApp(activeApp.id, { interview_at: fromLocalInput(e.target.value) })} />
                  </div>
                  <div className="field">
                    <label>Decision</label>
                    <input type="datetime-local" value={toLocalInput(activeApp.decision_at)} onChange={(e) => void patchApp(activeApp.id, { decision_at: fromLocalInput(e.target.value) })} />
                  </div>
                  <div className="field">
                    <label>Next action</label>
                    <input type="datetime-local" value={toLocalInput(activeApp.next_action_at)} onChange={(e) => void patchApp(activeApp.id, { next_action_at: fromLocalInput(e.target.value), follow_up_due_at: fromLocalInput(e.target.value) })} />
                  </div>
                </div>
                <div className="field">
                  <label>Notes</label>
                  <textarea rows={5} value={activeApp.notes || ""} onChange={(e) => setActiveApp({ ...activeApp, notes: e.target.value })} onBlur={() => void patchApp(activeApp.id, { notes: activeApp.notes })} />
                </div>
                <div className="action-row wrap">
                  <button className="btn" type="button" onClick={() => api.downloadCvPdf(activeApp.id)}>ATS CV PDF</button>
                  <button className="btn" type="button" onClick={() => api.downloadCoverLetter(activeApp.id)}>Cover letter PDF</button>
                  {activeApp.source_url && <a className="btn" href={activeApp.source_url} target="_blank" rel="noreferrer">Source</a>}
                </div>
              </div>
              <div>
                <div className="ai-panel">
                  <div className="tile-head">
                    <h3>LLM draft studio</h3>
                    <select aria-label="Draft tone" value={tone} onChange={(e) => setTone(e.target.value)}>
                      <option value="concise">Concise</option>
                      <option value="executive">Executive</option>
                      <option value="warm">Warm</option>
                      <option value="technical">Technical</option>
                    </select>
                  </div>
                  <textarea rows={3} placeholder="Extra instructions for this rewrite" value={aiInstructions} onChange={(e) => setAiInstructions(e.target.value)} />
                  <div className="action-row wrap">
                    <button className="btn primary" type="button" disabled={working} onClick={() => void regenerateDraft()}>{working ? "Rewriting..." : "Rewrite with LLM"}</button>
                    <button className="btn" type="button" onClick={() => void openComposer(activeApp)}>Open email</button>
                    <button className="btn" type="button" disabled={working} onClick={() => void discoverContact()}>Find apply email</button>
                    <button className="btn" type="button" onClick={() => void openFollowUp(activeApp)}>Follow-up</button>
                  </div>
                </div>
                {followUp && (
                  <div className="field">
                    <label>Follow-up draft</label>
                    <textarea rows={8} value={followUp.draft} onChange={(e) => setFollowUp({ ...followUp, draft: e.target.value })} />
                    <button className="btn" type="button" onClick={() => void copyText(followUp.draft, "Follow-up")}>Copy follow-up</button>
                  </div>
                )}
                {compose && (
                  <div className="composer-grid">
                    <div className="field">
                      <label>To</label>
                      <input type="email" value={compose.to || activeApp.contact_email || ""} onChange={(e) => setCompose({ ...compose, to: e.target.value })} placeholder="recruiter@company.com" />
                    </div>
                    <div className="field">
                      <label>Subject</label>
                      <input value={compose.subject} onChange={(e) => setCompose({ ...compose, subject: e.target.value })} />
                    </div>
                    <div className="field">
                      <label>Email body</label>
                      <textarea rows={12} value={compose.body} onChange={(e) => setCompose({ ...compose, body: e.target.value })} />
                    </div>
                    <div className="attachment-options">
                      <label className="toggle-row"><input type="checkbox" checked={attachCv} onChange={(e) => setAttachCv(e.target.checked)} /><span>Attach CV</span></label>
                      <label className="toggle-row"><input type="checkbox" checked={attachCoverLetter} onChange={(e) => setAttachCoverLetter(e.target.checked)} /><span>Attach cover letter</span></label>
                      <label className="toggle-row"><input type="checkbox" checked={manualOverride} onChange={(e) => setManualOverride(e.target.checked)} /><span>Manual recontact override</span></label>
                    </div>
                    <div className="action-row wrap">
                      <button className="btn" type="button" onClick={() => void copyText(`${compose.subject}\n\n${compose.body}`, "Email")}>Copy email</button>
                      <button className="btn primary" type="button" disabled={sending || !compose.to} onClick={() => void sendEmail()}>{sending ? "Sending..." : "Send email"}</button>
                    </div>
                  </div>
                )}
                {!compose && !followUp && <pre className="draft-preview">{activeApp.draft_body}</pre>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ApplicationCard({
  app,
  dragId,
  onDragStart,
  onDragEnd,
  onOpen,
  onEmail,
  onFollowUp,
}: {
  app: Application;
  dragId: string | null;
  onDragStart: () => void;
  onDragEnd: () => void;
  onOpen: () => void;
  onEmail: () => void;
  onFollowUp: () => void;
}) {
  return (
    <div className={`kanban-card ${dragId === app.id ? "dragging" : ""}`} draggable onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div className="kanban-card-head">
        <span className="mono">{app.id.slice(0, 8)}</span>
        <span className={`badge ${statusClass(app.status)}`}>{app.status}</span>
      </div>
      <button className="kanban-title link-button" type="button" onClick={onOpen}>{app.opportunity_title || "Untitled opportunity"}</button>
      <div className="kanban-meta">
        <span>{app.company_name || "Unknown company"}</span>
        <span className="mono">{app.next_action_at ? new Date(app.next_action_at).toLocaleDateString() : app.source || "unknown source"}</span>
      </div>
      <div className="kanban-card-body">{(app.notes || app.draft_body).slice(0, 150)}</div>
      <div className="kanban-actions">
        <button className="btn compact" type="button" onClick={onOpen}>Open</button>
        <button className="btn compact" type="button" onClick={onEmail}>Email</button>
        <button className="btn compact" type="button" onClick={onFollowUp}>Follow-up</button>
      </div>
    </div>
  );
}
