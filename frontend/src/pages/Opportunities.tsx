import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Candidate, Opportunity, OpportunityType } from "../api";

function ScoreRing({ score }: { score: number }) {
  const r = 36;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.min(100, Math.max(0, score)) / 100) * c;
  return (
    <svg className="score-ring" viewBox="0 0 88 88" aria-label={`Score ${score}`}>
      <circle cx="44" cy="44" r={r} fill="none" stroke="#d9e0ea" strokeWidth="8" />
      <circle
        cx="44"
        cy="44"
        r={r}
        fill="none"
        stroke="url(#g)"
        strokeWidth="8"
        strokeDasharray={c}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 44 44)"
      />
      <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#059669" />
        </linearGradient>
      </defs>
      <text x="44" y="48" textAnchor="middle" fill="#172033" fontFamily="IBM Plex Mono" fontSize="16">
        {Math.round(score)}
      </text>
    </svg>
  );
}

export function OpportunitiesPage() {
  const [rows, setRows] = useState<Opportunity[] | null>(null);
  const [types, setTypes] = useState<OpportunityType[]>([]);
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [sort, setSort] = useState("score_desc");
  const [error, setError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [webQuery, setWebQuery] = useState("");
  const [webLocation, setWebLocation] = useState("");
  const [webCandidateId, setWebCandidateId] = useState("");
  const [searchingWeb, setSearchingWeb] = useState(false);
  const [webMsg, setWebMsg] = useState("");

  useEffect(() => {
    Promise.all([api.opportunities(status || undefined), api.opportunityTypes(), api.candidates()])
      .then(([ops, typeRows, candidateRows]) => {
        setRows(ops);
        setTypes(typeRows);
        setCandidates(candidateRows);
        if (candidateRows[0] && !webCandidateId) setWebCandidateId(candidateRows[0].id);
      })
      .catch((e) => setError(String(e.message || e)));
  }, [status]);

  async function runWebSearch() {
    if (!webQuery.trim()) return;
    setSearchingWeb(true);
    setWebMsg("");
    setError(null);
    try {
      const results = await api.webSearchOpportunities({
        query: webQuery,
        locations: webLocation ? webLocation.split(",").map((item) => item.trim()).filter(Boolean) : [],
        candidate_id: webCandidateId || undefined,
        limit: 60,
      });
      setRows(results);
      setWebMsg(`${results.length} opportunities imported from public web sources.`);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setSearchingWeb(false);
    }
  }

  const filtered = useMemo(() => {
    const items = (rows || []).filter((o) => {
      const q = query.trim().toLowerCase();
      const matchesQuery = !q || `${o.title} ${o.company_name || ""} ${o.location || ""} ${o.source}`.toLowerCase().includes(q);
      const matchesType = !type || o.opportunity_type_code === type;
      const matchesScore = (o.match_score || 0) >= minScore;
      const matchesRemote = !remoteOnly || o.remote;
      return matchesQuery && matchesType && matchesScore && matchesRemote;
    });
    return [...items].sort((a, b) => {
      if (sort === "score_asc") return (a.match_score || 0) - (b.match_score || 0);
      if (sort === "deadline") return String(a.deadline || "9999-12-31").localeCompare(String(b.deadline || "9999-12-31"));
      if (sort === "newest") return String(b.collected_at).localeCompare(String(a.collected_at));
      return (b.match_score || 0) - (a.match_score || 0);
    });
  }, [minScore, query, remoteOnly, rows, sort, type]);

  function exportCsv() {
    const headers = ["Title", "Company", "Type", "Score", "Remote", "Location", "Deadline", "Source", "Source URL"];
    const lines = filtered.map((o) => [
      o.title,
      o.company_name || "",
      o.opportunity_type_code || "",
      String(o.match_score ?? ""),
      o.remote ? "yes" : "no",
      o.location || "",
      o.deadline || "",
      o.source,
      o.source_url || "",
    ]);
    const csv = [headers, ...lines]
      .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "hanicar-opportunities.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Opportunities</h1>
          <p className="page-sub">Ranked matches with explainable reasons and CV gaps.</p>
        </div>
        <button className="btn" type="button" disabled={filtered.length === 0} onClick={exportCsv}>Export CSV</button>
      </header>
      {error && <p className="alert danger">{error}</p>}
      <div className="filter-bar">
        <input
          aria-label="Filter opportunities"
          placeholder="Filter by title, company, or location"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="matched">Matched</option>
          <option value="new">New</option>
          <option value="suppressed">Suppressed</option>
          <option value="archived">Archived</option>
        </select>
        <select aria-label="Type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {types.map((t) => <option key={t.code} value={t.code}>{t.code}</option>)}
        </select>
        <select aria-label="Sort opportunities" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="score_desc">Best score first</option>
          <option value="score_asc">Lowest score first</option>
          <option value="deadline">Deadline first</option>
          <option value="newest">Newest first</option>
        </select>
      </div>
      <div className="toolbar-row">
        <label className="range-field">
          <span>Minimum score</span>
          <input type="range" min={0} max={100} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
          <strong className="mono">{minScore}</strong>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />
          <span>Remote only</span>
        </label>
      </div>
      <div className="web-radar">
        <div>
          <span className="eyebrow">Web opportunity radar</span>
          <h3>Search more public sources</h3>
          <p className="muted-text">Imports matching roles from TanitJobs, Remotive, RemoteOK, Arbeitnow, Jobicy, The Muse, and We Work Remotely, then scores them when a candidate is selected.</p>
        </div>
        <div className="radar-controls">
          <input aria-label="Web search query" placeholder="frontend react remote, data engineer, cybersecurity intern..." value={webQuery} onChange={(e) => setWebQuery(e.target.value)} />
          <input aria-label="Locations" placeholder="Remote, Tunis, France" value={webLocation} onChange={(e) => setWebLocation(e.target.value)} />
          <select aria-label="Candidate for scoring" value={webCandidateId} onChange={(e) => setWebCandidateId(e.target.value)}>
            <option value="">No candidate scoring</option>
            {candidates.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className="btn primary" type="button" disabled={searchingWeb || !webQuery.trim()} onClick={() => void runWebSearch()}>
            {searchingWeb ? "Searching..." : "Search web"}
          </button>
        </div>
        {webMsg && <p className="alert success mono">{webMsg}</p>}
      </div>
      {!rows && <div className="skeleton" style={{ height: 120 }} />}
      {rows && rows.length === 0 && <div className="empty">No opportunities yet - run SEARCH NOW.</div>}
      {rows && rows.length > 0 && filtered.length === 0 && <div className="empty">No opportunities match those filters.</div>}
      {rows && filtered.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Company</th>
                <th>Type</th>
                <th>Score</th>
                <th>Remote</th>
                <th>Deadline</th>
                <th>Source</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.id}>
                  <td><Link to={`/opportunities/${o.id}`}>{o.title}</Link></td>
                  <td>{o.company_name || "--"}</td>
                  <td className="mono">{o.opportunity_type_code || "--"}</td>
                  <td className="mono">{o.match_score ?? "--"}</td>
                  <td>{o.remote ? <span className="badge success">yes</span> : <span className="badge muted">no</span>}</td>
                  <td className="mono">{o.deadline || "--"}</td>
                  <td className="mono">{o.source}</td>
                  <td><span className={`badge ${o.status === "matched" ? "success" : "muted"}`}>{o.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function OpportunityDetailPage() {
  const { id } = useParams();
  const [opp, setOpp] = useState<Opportunity | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [candidateId, setCandidateId] = useState("");
  const [msg, setMsg] = useState("");
  const [draftId, setDraftId] = useState("");
  const [manualOverride, setManualOverride] = useState(false);

  useEffect(() => {
    if (!id) return;
    api.opportunity(id).then(setOpp);
    api.candidates().then((c) => {
      setCandidates(c);
      if (c[0]) setCandidateId(c[0].id);
    });
  }, [id]);

  if (!opp) return <div className="skeleton" style={{ height: 200 }} />;

  return (
    <div>
      <h1 className="page-title">{opp.title}</h1>
      <p className="page-sub">{opp.company_name || "Unknown company"} / {opp.source}</p>
      <div className="bento">
        <div className="tile span-4 score-panel">
          <ScoreRing score={opp.match_score ?? 0} />
          <div className="mono">match score</div>
        </div>
        <div className="tile span-8">
          <h3>Why</h3>
          <ul>
            {(opp.match_reasons || []).map((r, i) => (
              <li key={i} style={{ animationDelay: `${i * 60}ms` }}>{r}</li>
            ))}
          </ul>
          <h3>CV gaps (evidenced only)</h3>
          {(opp.skill_gaps || []).length === 0 ? (
            <p className="empty" style={{ padding: "0.5rem 0" }}>No gaps detected from known skill lexicon.</p>
          ) : (
            <ul>{opp.skill_gaps.map((g) => <li key={g} className="mono">{g}</li>)}</ul>
          )}
        </div>
        <div className="tile span-12">
          <h3>Description</h3>
          <p className="description-box">{opp.description}</p>
          {opp.source_url && (
            <p><a href={opp.source_url} target="_blank" rel="noreferrer">Open source</a></p>
          )}
          <div className="detail-list compact-list">
            <div><span>Source</span><strong>{opp.source}</strong></div>
            <div><span>Source URL</span><strong>{opp.source_url ? <a href={opp.source_url} target="_blank" rel="noreferrer">Open opportunity</a> : "Not available"}</strong></div>
          </div>
          <div className="field" style={{ maxWidth: 320 }}>
            <label>Draft application as</label>
            <select value={candidateId} onChange={(e) => setCandidateId(e.target.value)}>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <label className="toggle-row">
            <input type="checkbox" checked={manualOverride} onChange={(e) => setManualOverride(e.target.checked)} />
            <span>Manual recontact override</span>
          </label>
          <button
            className="btn primary"
            type="button"
            disabled={!candidateId}
            onClick={async () => {
              const app = await api.createApplication({
                opportunity_id: opp.id,
                candidate_id: candidateId,
                manual_recontact_override: manualOverride,
              });
              setDraftId(app.id);
              setMsg(`Draft created (${app.id.slice(0, 8)}) - never auto-sent.`);
            }}
          >
            Create draft (never auto-send)
          </button>
          <button className="btn" type="button" disabled={!draftId} onClick={() => api.downloadCoverLetter(draftId)}>
            ATS-friendly cover letter PDF
          </button>
          {msg && <p className="alert success mono">{msg}</p>}
        </div>
      </div>
    </div>
  );
}

export function SuppressedPage() {
  const [rows, setRows] = useState<Opportunity[] | null>(null);

  useEffect(() => {
    api.suppressed().then(setRows);
  }, []);

  return (
    <div>
      <h1 className="page-title">Suppressed</h1>
      <p className="page-sub">Every exclusion has a reason you can audit.</p>
      {!rows && <div className="skeleton" style={{ height: 100 }} />}
      {rows && rows.length === 0 && <div className="empty">No suppressed opportunities.</div>}
      {rows && rows.map((o) => (
        <div key={o.id} className="tile" style={{ marginBottom: "0.75rem" }}>
          <strong>{o.title}</strong>
          <div className="mono muted-text">{o.company_name}</div>
          <ul>
            {(o.exclusion_reasons || []).map((r, i) => (
              <li key={i}><span className="badge warn">{r.code}</span> {r.detail}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
