import { useEffect, useState } from "react";
import { api } from "../api";

export default function AboutPage() {
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.meta().then(setMeta);
  }, []);

  return (
    <div>
      <h1 className="page-title">About</h1>
      <p className="page-sub">Don't search. Hunt.</p>
      <div className="tile">
        <p>
          <strong>Hanicar Jobs</strong> is an open-source opportunity hunter for PFE,
          internships, graduate roles, and jobs.
        </p>
        <p>
          Copyright (c) 2026 Safwen Amaira = Born as root.
        </p>
        <p>
          Derived from the PFE Hunter concept by Safwen Amaira / Born as root.
          See <code>NOTICE</code> for attribution.
        </p>
        <p>AI is optional. Scraped content is treated as untrusted. Drafts never auto-send.</p>
        {meta && (
          <pre className="mono" style={{ fontSize: "0.85rem" }}>
            {JSON.stringify(meta, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
