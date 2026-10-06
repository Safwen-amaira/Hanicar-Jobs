import { useEffect, useState } from "react";
import { api, SearchProfile, SearchRun } from "../api";

export default function HuntPage() {
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [profileId, setProfileId] = useState("");
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<SearchRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.searchProfiles().then((p) => {
      setProfiles(p);
      if (p[0]) setProfileId(p[0].id);
    });
  }, []);

  async function start() {
    if (!profileId) return;
    setRunning(true);
    setError(null);
    setRun(null);
    try {
      const result = await api.runSearch(profileId);
      setRun(result);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Run Search</h1>
          <p className="page-sub">Collect, resolve, exclude, and match opportunities with an auditable run log.</p>
        </div>
      </header>
      <div className="bento">
        <div className="tile span-4">
          <div className="tile-head"><h3>Controls</h3></div>
          <div className="field">
            <label htmlFor="profile">Search profile</label>
            <select id="profile" value={profileId} onChange={(e) => setProfileId(e.target.value)}>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <button className="btn primary" type="button" disabled={!profileId || running} onClick={start}>
            {running ? "Hunting…" : "SEARCH NOW"}
          </button>
          {error && <p style={{ color: "var(--hj-danger)" }}>{error}</p>}
        </div>
        <div className="tile span-8">
          <div className="tile-head">
            <h3>Run summary</h3>
            <span className={`badge ${run?.status === "completed" ? "success" : running ? "warn" : "muted"}`}>
              {running ? "running" : run?.status || "idle"}
            </span>
          </div>
          {!run && !running && <div className="empty">Choose a profile and run a search to see source activity.</div>}
          {running && <div className="skeleton" style={{ height: 96 }} />}
          {run?.stats && (
            <div className="metrics-grid">
              {Object.entries(run.stats).map(([key, value]) => (
                <div className="metric" key={key}>
                  <span>{key.replaceAll("_", " ")}</span>
                  <strong className="mono">{String(value)}</strong>
                </div>
              ))}
            </div>
          )}
          {run && (
            <p className="mono muted-text">
              Run {run.id.slice(0, 8)} for profile {run.profile_id.slice(0, 8)}
            </p>
          )}
        </div>
        <div className="tile span-12">
          <div className="tile-head"><h3>Event log</h3></div>
          {!run && <div className="empty">No events yet.</div>}
          {run && (
            <div className="timeline">
              {(run.events || []).map((e, i) => (
                <div className="timeline-item" key={i}>
                  <span className="badge muted">{String(e.type || "event")}</span>
                  <strong>{String(e.title || e.message || e.source || "Pipeline event")}</strong>
                  <p className="mono muted-text">
                    {e.company ? `${String(e.company)} · ` : ""}
                    {e.score != null ? `score ${String(e.score)} · ` : ""}
                    {Array.isArray(e.reasons) ? e.reasons.join(", ") : ""}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="tile span-12">
          <div className="tile-head"><h3>Profiles</h3></div>
          {profiles.length === 0 ? (
            <div className="empty">Create a candidate and search profile before running the pipeline.</div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Keywords</th>
                    <th>Locations</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {profiles.map((p) => (
                    <tr key={p.id}>
                      <td>{p.name}</td>
                      <td className="mono">{p.keywords.join(", ") || "--"}</td>
                      <td className="mono">{p.locations.join(", ") || "--"}</td>
                      <td><span className={`badge ${p.active ? "success" : "muted"}`}>{p.active ? "active" : "inactive"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
