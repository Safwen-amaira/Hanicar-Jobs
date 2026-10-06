import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import HuntMap from "../cinematic/HuntMap";

export default function LandingPage() {
  const { t } = useTranslation();
  return (
    <>
      <header className="landing-nav">
        <Link className="landing-mark" to="/">
          <span>HJ</span>
          <strong>Hanicar Jobs</strong>
        </Link>
        <nav aria-label="Home navigation">
          <Link to="/profiles">Profiles</Link>
          <Link to="/opportunities">Opportunities</Link>
          <Link to="/applications">Applications</Link>
          <Link className="btn compact primary" to="/dashboard">Open app</Link>
        </nav>
      </header>
      <section className="hero">
        <HuntMap />
        <div className="hero-content home-hero-content">
          <p className="eyebrow">Opportunity workspace</p>
          <h1 className="hero-brand">Hanicar Jobs</h1>
          <p className="hero-line">{t("landing.headline")}</p>
          <p className="hero-sub">
            Build a candidate profile, run explainable searches, create ATS-friendly cover letters,
            track every application you did, and keep the original opportunity source attached to the record.
          </p>
          <div className="cta-row">
            <Link className="btn primary" to="/dashboard">
              {t("landing.cta")}
            </Link>
            <Link className="btn" to="/profiles">
              Add profile and CV
            </Link>
            <Link className="btn" to="/settings">Configure Gmail</Link>
          </div>
          <div className="hero-proof" aria-label="Workflow readiness">
            <span><strong>CV</strong> evidence-based matches</span>
            <span><strong>ATS</strong> plain-text PDFs</span>
            <span><strong>SMTP</strong> app-password sending</span>
            <span><strong>Manual</strong> review before email</span>
          </div>
        </div>
      </section>
      <section className="home-workbench" aria-label="Quick start">
        <div className="home-card primary-card">
          <span className="mono">Start here</span>
          <h2>Set up your application engine</h2>
          <p>Complete the profile, upload a CV file, test Gmail SMTP, then run your first search.</p>
          <div className="home-steps">
            <Link to="/profiles"><span>1</span> Candidate and CV</Link>
            <Link to="/settings"><span>2</span> Gmail app password</Link>
            <Link to="/hunt"><span>3</span> Run search</Link>
          </div>
        </div>
        <Link className="home-card" to="/opportunities">
          <span className="mono">Review</span>
          <h3>Ranked opportunities</h3>
          <p>Filter by score, remote status, type, and export the shortlist as CSV.</p>
        </Link>
        <Link className="home-card" to="/applications">
          <span className="mono">Apply</span>
          <h3>Applications done</h3>
          <p>See drafts and sent applications with their company, source, cover letter, and follow-up state.</p>
        </Link>
        <Link className="home-card" to="/sources">
          <span className="mono">Monitor</span>
          <h3>Source health</h3>
          <p>Check source success rates, errors, and recent run state.</p>
        </Link>
      </section>
      <section className="home-intel" aria-label="Workspace capabilities">
        <div>
          <span className="mono">What gets tracked</span>
          <h2>Every opportunity keeps its evidence trail.</h2>
          <p>
            Hanicar Jobs links each application back to the original title, company, board source,
            source URL, match reasons, CV gaps, and follow-up due date so you can audit what you did later.
          </p>
        </div>
        <div className="home-intel-grid">
          <div>
            <strong>ATS cover letters</strong>
            <p>Plain-text PDF structure, clean wrapping, candidate contact details, role title, company, and source.</p>
          </div>
          <div>
            <strong>Application history</strong>
            <p>Track draft, queued, sent, and failed applications without losing the opportunity context.</p>
          </div>
          <div>
            <strong>Manual control</strong>
            <p>Email sending stays explicit, with CV and cover letter attachments toggled before delivery.</p>
          </div>
        </div>
      </section>
      <footer className="landing-footer">
        <span>(c) 2026 Safwen Amaira = Born as root</span>
        <span>Hanicar Jobs keeps the original opportunity source visible from hunt to follow-up.</span>
      </footer>
    </>
  );
}
