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
          <p className="eyebrow">Application command suite</p>
          <h1 className="hero-brand">Hanicar Jobs</h1>
          <p className="hero-line">{t("landing.headline")}</p>
          <p className="hero-sub">
            Hunt opportunities across Tunisia and remote sources, read the full offer before drafting,
            prepare ATS-friendly email packages, pace outbound sends, and track every company you already contacted.
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
            <span><strong>SMTP</strong> paced sender</span>
            <span><strong>Guarded</strong> duplicate company checks</span>
          </div>
        </div>
      </section>
      <section className="home-workbench" aria-label="Quick start">
        <div className="home-card primary-card">
          <span className="mono">Start here</span>
          <h2>Set up your application engine</h2>
          <p>Complete your profile contacts, upload CV assets, test Gmail SMTP, then run a scored search.</p>
          <div className="home-steps">
            <Link to="/profiles"><span>1</span> Candidate, CV, phone, LinkedIn, GitHub</Link>
            <Link to="/settings"><span>2</span> Gmail app password</Link>
            <Link to="/opportunities"><span>3</span> Search TanitJobs and remote boards</Link>
            <Link to="/applications"><span>4</span> Prepare queue, then human-verify each send</Link>
          </div>
        </div>
        <Link className="home-card" to="/opportunities">
          <span className="mono">Review</span>
          <h3>Ranked opportunities</h3>
          <p>Filter by score, remote status, type, and import from public sources including TanitJobs.</p>
        </Link>
        <Link className="home-card" to="/applications">
          <span className="mono">Apply</span>
          <h3>Automated but controlled</h3>
          <p>Find apply emails, prepare a review queue, and send only after you check each package.</p>
        </Link>
        <Link className="home-card" to="/sources">
          <span className="mono">Monitor</span>
          <h3>Source health</h3>
          <p>Check source success rates, errors, recent run state, and imported-board reliability.</p>
        </Link>
      </section>
      <section className="home-command" aria-label="How to use Hanicar Jobs">
        <div className="command-copy">
          <span className="mono">How it works</span>
          <h2>One reliable loop from search to follow-up.</h2>
          <p>
            Start with evidence in your profile. Import opportunities. Open a role, create a draft,
            let the LLM read the full offer, then verify each package yourself before anything leaves your mailbox.
          </p>
        </div>
        <div className="command-rail">
          <div><strong>Profile</strong><span>Email, phone, LinkedIn, GitHub, CV text, and attachments.</span></div>
          <div><strong>Search</strong><span>TanitJobs, public remote boards, scored matches, and CSV export.</span></div>
          <div><strong>Prepare</strong><span>ATS-friendly drafts with no extra links beyond your contact links.</span></div>
          <div><strong>Send</strong><span>Human verification on every package. No unattended auto-send.</span></div>
          <div><strong>Track</strong><span>Statuses, dates, notes, contacts, follow-ups, interviews, and outcomes.</span></div>
        </div>
      </section>
      <section className="home-intel" aria-label="Workspace capabilities">
        <div>
          <span className="mono">What gets tracked</span>
          <h2>Every opportunity keeps its evidence trail.</h2>
          <p>
            Hanicar Jobs links each application back to the original title, company, board source,
            source URL, match reasons, CV gaps, email contact, follow-up due date, and send log so you can audit what happened later.
          </p>
        </div>
        <div className="home-intel-grid">
          <div>
            <strong>ATS cover letters</strong>
            <p>Plain-text structure, clean wrapping, role title, company, and only your approved contact links.</p>
          </div>
          <div>
            <strong>Application history</strong>
            <p>Track draft, prepared, queued, sent, applied, failed, and follow-up states without losing context.</p>
          </div>
          <div>
            <strong>Duplicate protection</strong>
            <p>Previously contacted companies are skipped unless you deliberately enable a manual override.</p>
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
