import React, { useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { setLocale } from "../i18n";
import { api } from "../api";

interface NavItem {
  to: string;
  key: string;
  icon: string;
}

interface NavGroup {
  label: string;
  links: NavItem[];
}

const groups: NavGroup[] = [
  {
    label: "Hunt",
    links: [
      { to: "/", key: "nav.home", icon: "🏠" },
      { to: "/dashboard", key: "nav.dashboard", icon: "📊" },
      { to: "/profiles", key: "nav.profiles", icon: "🎯" },
      { to: "/hunt", key: "nav.hunt", icon: "🚀" },
      { to: "/opportunities", key: "nav.opportunities", icon: "💼" },
      { to: "/suppressed", key: "nav.suppressed", icon: "🚫" },
    ],
  },
  {
    label: "Apply",
    links: [
      { to: "/applications", key: "nav.kanban", icon: "📋" },
      { to: "/applications/review", key: "nav.review", icon: "📝" },
    ],
  },
  {
    label: "Ops",
    links: [
      { to: "/sources", key: "nav.sources", icon: "🔌" },
      { to: "/settings", key: "nav.settings", icon: "⚙️" },
      { to: "/about", key: "nav.about", icon: "ℹ️" },
    ],
  },
];

const allLinks = groups.flatMap((group) => group.links);

export function Shell({ children }: { children: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [filterQuery, setFilterQuery] = useState("");
  const [navSearch, setNavSearch] = useState("");
  const [reviewCount, setReviewCount] = useState(0);
  const [navOpen, setNavOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    api.applications()
      .then((rows) => setReviewCount(rows.filter((app) => ["draft", "prepared", "queued"].includes(app.status)).length))
      .catch(() => setReviewCount(0));
  }, []);

  const paletteFiltered = useMemo(
    () => allLinks.filter((item) => t(item.key).toLowerCase().includes(filterQuery.toLowerCase())),
    [filterQuery, t]
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${navOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-header" style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <span className="brand-icon" style={{ fontSize: "1.4rem" }}>🏹</span>
            <div className="brand-title">
              <span className="brand-name">Hanicar Jobs</span>
              <span className="brand-version" style={{ fontSize: "0.7rem", marginLeft: "0.4rem", opacity: 0.6, background: "rgba(255,255,255,0.1)", padding: "2px 6px", borderRadius: "4px" }}>v2.0</span>
            </div>
          </div>
          <div className="brand-tag">{t("tagline")}</div>
        </div>

        <div className="sidebar-search" style={{ marginBottom: "1rem" }}>
          <input
            type="text"
            className="sidebar-search-input"
            placeholder="🔍 Filter menu..."
            value={navSearch}
            onChange={(e) => setNavSearch(e.target.value)}
            style={{
              width: "100%",
              padding: "0.45rem 0.75rem",
              fontSize: "0.82rem",
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "6px",
              color: "#fff",
              outline: "none",
            }}
          />
        </div>

        <nav className="nav">
          {groups.map((group) => {
            const visibleLinks = group.links.filter((item) =>
              t(item.key).toLowerCase().includes(navSearch.toLowerCase())
            );
            if (visibleLinks.length === 0) return null;
            return (
              <div key={group.label} className="nav-group" style={{ marginBottom: "0.85rem" }}>
                <span className="nav-label" style={{ fontSize: "0.7rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--hj-gold, #d97706)", display: "block", marginBottom: "0.4rem", opacity: 0.85 }}>
                  {group.label}
                </span>
                {visibleLinks.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === "/"}
                    onClick={() => setNavOpen(false)}
                    className={({ isActive }) => (isActive ? "active" : "")}
                    style={{ display: "flex", alignItems: "center", gap: "0.6rem", padding: "0.5rem 0.65rem", borderRadius: "6px", textDecoration: "none", transition: "all 0.15s ease" }}
                  >
                    <span className="nav-item-icon" style={{ fontSize: "1rem" }}>{item.icon}</span>
                    <span className="nav-item-text" style={{ flex: 1 }}>{t(item.key)}</span>
                    {item.to === "/applications/review" && reviewCount > 0 && (
                      <span className="nav-count-badge" style={{ background: "linear-gradient(135deg, #d97706, #b45309)", color: "#fff", fontSize: "0.75rem", fontWeight: 700, padding: "2px 7px", borderRadius: "10px", boxShadow: "0 2px 4px rgba(217,119,6,0.3)" }}>
                        {reviewCount}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>

        <div className="sidebar-footer" style={{ marginTop: "auto", paddingTop: "1rem", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
          <button
            className="sidebar-cmd-hint"
            onClick={() => setPaletteOpen(true)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              width: "100%",
              padding: "0.4rem 0.65rem",
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "6px",
              color: "var(--hj-sidebar-muted, #94a3b8)",
              fontSize: "0.78rem",
              cursor: "pointer",
            }}
          >
            <span>Jump to...</span>
            <kbd style={{ background: "rgba(255,255,255,0.1)", padding: "1px 5px", borderRadius: "4px", fontSize: "0.7rem", color: "#fff" }}>⌘K</kbd>
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar-actions">
          <button className="btn compact nav-toggle" type="button" onClick={() => setNavOpen((v) => !v)}>
            {navOpen ? "✕ Close" : "☰ Menu"}
          </button>
          <button className="cmd-chip" type="button" onClick={() => setPaletteOpen(true)} aria-label="Open command palette">
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
        <p className="footer-note">© 2026 Safwen Amaira — Born as root · Don't search. Hunt.</p>
      </main>

      {paletteOpen && (
        <div className="palette" role="dialog" aria-label="Command palette">
          <div className="palette-box">
            <input
              autoFocus
              placeholder="Jump to..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
            />
            <ul>
              {paletteFiltered.map((item) => (
                <li key={item.to}>
                  <button
                    type="button"
                    onClick={() => {
                      navigate(item.to);
                      setPaletteOpen(false);
                      setFilterQuery("");
                    }}
                  >
                    <span style={{ marginRight: "8px" }}>{item.icon}</span>
                    {t(item.key)}
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
