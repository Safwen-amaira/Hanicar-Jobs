import { useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { setLocale } from "../i18n";
import { api } from "../api";

const groups = [
  {
    label: "Hunt",
    links: [
      ["/", "nav.home"],
      ["/dashboard", "nav.dashboard"],
      ["/profiles", "nav.profiles"],
      ["/hunt", "nav.hunt"],
      ["/opportunities", "nav.opportunities"],
      ["/suppressed", "nav.suppressed"],
    ],
  },
  {
    label: "Apply",
    links: [
      ["/applications", "nav.kanban"],
      ["/applications/review", "nav.review"],
    ],
  },
  {
    label: "Ops",
    links: [
      ["/sources", "nav.sources"],
      ["/settings", "nav.settings"],
      ["/about", "nav.about"],
    ],
  },
] as const;

const links = groups.flatMap((group) => group.links);

export function Shell({ children }: { children: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [reviewCount, setReviewCount] = useState(0);
  const [navOpen, setNavOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    api.applications()
      .then((rows) => setReviewCount(rows.filter((app) => ["draft", "prepared", "queued"].includes(app.status)).length))
      .catch(() => setReviewCount(0));
  }, []);

  const filtered = useMemo(
    () => links.filter(([, key]) => t(key).toLowerCase().includes(q.toLowerCase())),
    [q, t]
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-name">Hanicar Jobs</div>
          <div className="brand-tag">{t("tagline")}</div>
        </div>
        <nav className="nav">
          {groups.map((group) => (
            <div key={group.label} className="nav-group">
              <span className="nav-label">{group.label}</span>
              {group.links.map(([to, key]) => (
                <NavLink key={to} to={to} end={to === "/"} onClick={() => setNavOpen(false)}>
                  <span>{t(key)}</span>
                  {to === "/applications/review" && reviewCount > 0 && <span className="nav-count">{reviewCount}</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <main className="main">
        <div className="topbar-actions">
          <button className="btn compact nav-toggle" type="button" onClick={() => setNavOpen((v) => !v)}>
            Menu
          </button>
          <button className="cmd-chip" type="button" onClick={() => setOpen(true)} aria-label="Open command palette">
            <span>Jump to a page</span>
            <kbd>Ctrl K</kbd>
          </button>
          <div className="segmented" aria-label="Language">
          {(["en", "fr", "ar"] as const).map((lng) => (
            <button
              key={lng}
              className="segment"
              type="button"
              aria-pressed={i18n.language === lng}
              onClick={() => setLocale(lng)}
            >
              {lng.toUpperCase()}
            </button>
          ))}
          </div>
        </div>
        {children}
        <p className="footer-note">(c) 2026 Safwen Amaira = Born as root · Don't search. Hunt.</p>
      </main>
      {open && (
        <div className="palette" role="dialog" aria-label="Command palette">
          <div className="palette-box">
            <input
              autoFocus
              placeholder="Jump to..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <ul>
              {filtered.map(([to, key]) => (
                <li key={to}>
                  <button
                    type="button"
                    onClick={() => {
                      navigate(to);
                      setOpen(false);
                      setQ("");
                    }}
                  >
                    {t(key)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
