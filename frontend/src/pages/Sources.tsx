import { useEffect, useState } from "react";
import { api, SourceHealth } from "../api";

export default function SourcesPage() {
  const [rows, setRows] = useState<SourceHealth[] | null>(null);

  useEffect(() => {
    api.sources().then(setRows);
  }, []);

  return (
    <div>
      <h1 className="page-title">Source health</h1>
      <p className="page-sub">Success rate, last run, errors - real data only.</p>
      {!rows && <div className="skeleton" style={{ height: 100 }} />}
      {rows && rows.length === 0 && <div className="empty">No sources registered.</div>}
      {rows && (
        <table className="table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Success rate</th>
              <th>Success</th>
              <th>Errors</th>
              <th>Last run</th>
              <th>Last error</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.source_name}>
                <td className="mono">{r.source_name}</td>
                <td className="mono">{(r.success_rate * 100).toFixed(0)}%</td>
                <td className="mono">{r.success_count}</td>
                <td className="mono">{r.error_count}</td>
                <td className="mono">{r.last_run || "-"}</td>
                <td>{r.last_error || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
