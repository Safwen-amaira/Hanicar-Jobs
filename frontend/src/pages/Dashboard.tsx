import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, Application, Candidate, Opportunity, SourceHealth } from "../api";

export default function DashboardPage() {
  const { t } = useTranslation();
  const [ops, setOps] = useState<Opportunity[] | null>(null);
  const [sources, setSources] = useState<SourceHealth[] | null>(null);
  const [apps, setApps] = useState<Application[] | null>(null);
  const [candidates, setCandidates] = useState<Candidate[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.opportunities(), api.sources(), api.applications(), api.candidates(), api.health()])
      .then(([o, s, a, c]) => {
        setOps(o);
        setSources(s);
        setApps(a);
        setCandidates(c);
      })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  const matched = ops?.filter((o) => o.status === "matched").length;
  const suppressed = ops?.filter((o) => o.status === "suppressed").length;
  const drafts = apps?.filter((a) => a.status === "draft").length;
  const sent = apps?.filter((a) => a.status === "sent").length;

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">{t("tagline")} Explainable opportunity pipeline.</p>
        </div>
        <div className="cta-row">
          <Link className="btn" to="/profiles">Setup profile</Link>
          <Link className="btn primary" to="/hunt">Run search</Link>
        </div>
      </header>
      {error && <div className="alert danger">{error}</div>}
      <div className="bento">
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
          <span>Sent</span>
          <strong className="mono">{sent ?? "--"}</strong>
        </div>
        <div className="tile stat-card span-4">
          <span>Candidates</span>
          <strong className="mono">{candidates?.length ?? "--"}</strong>
        </div>
        <div className="tile span-8">
          <div className="tile-head">
            <h3>Latest opportunities</h3>
            <Link to="/opportunities">View all</Link>
          </div>
          {!ops && <div className="skeleton" style={{ height: 80 }} />}
          {ops && ops.length === 0 && <div className="empty">{t("empty")}</div>}
          {ops && ops.slice(0, 5).map((o) => (
            <Link key={o.id} className="list-row" to={`/opportunities/${o.id}`}>
              <span>{o.title}</span>
              <div className="mono">
                {o.company_name || "--"} / score {o.match_score ?? "--"}
              </div>
            </Link>
          ))}
        </div>
        <div className="tile span-4">
          <div className="tile-head">
            <h3>Next actions</h3>
          </div>
          <div className="action-stack">
            <Link className="workflow-link" to="/profiles">
              <strong>Complete candidate profile</strong>
              <span>Add CV text, skills, and the CV file used for emails.</span>
            </Link>
            <Link className="workflow-link" to="/settings">
              <strong>Configure Gmail SMTP</strong>
              <span>Save and test your Google app password.</span>
            </Link>
            <Link className="workflow-link" to="/applications">
              <strong>Review applications</strong>
              <span>Open drafts, compose email, and send manually.</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
