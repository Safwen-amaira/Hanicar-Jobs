import { FormEvent, useState } from "react";
import { api, SmtpSettings } from "../api";
import { loadSmtpSettings, saveSmtpSettings } from "../settings";

export default function SettingsPage() {
  const [settings, setSettings] = useState(loadSmtpSettings);
  const [msg, setMsg] = useState("");
  const [testing, setTesting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  function update<K extends keyof typeof settings>(key: K, value: (typeof settings)[K]) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    saveSmtpSettings(settings);
    setMsg("SMTP settings saved on this device.");
  }

  async function onTest() {
    setTesting(true);
    setMsg("");
    try {
      const result = await api.testSmtp(settings);
      setMsg(result.detail);
    } catch (e) {
      setMsg(String((e as Error).message || e));
    } finally {
      setTesting(false);
    }
  }

  function exportSettings() {
    const safeSettings = { ...settings, password: "" };
    const blob = new Blob([JSON.stringify(safeSettings, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "hanicar-mail-settings.json";
    link.click();
    URL.revokeObjectURL(url);
    setMsg("Settings exported without the app password.");
  }

  async function importSettings(file: File | null) {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as Partial<SmtpSettings>;
      setSettings((prev) => ({
        ...prev,
        ...parsed,
        port: Number(parsed.port || prev.port),
        use_tls: parsed.use_tls ?? prev.use_tls,
      }));
      setMsg("Settings imported. Review and save them on this device.");
    } catch {
      setMsg("Could not import that settings file.");
    }
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-sub">Mail delivery defaults for explicit, user-triggered application emails.</p>
        </div>
      </header>
      {msg && <p className="alert success mono">{msg}</p>}
      <form className="bento" onSubmit={onSubmit}>
        <div className="tile span-4">
          <div className="tile-head"><h3>Gmail readiness</h3></div>
          <div className="checklist">
            <div className={settings.username.includes("@") ? "check done" : "check"}>Gmail address added</div>
            <div className={settings.password.length >= 12 ? "check done" : "check"}>Google app password added</div>
            <div className={settings.from_email.includes("@") ? "check done" : "check"}>Sender address configured</div>
          </div>
          <p className="field-hint">
            Use a Google app password, not your regular Google account password. Settings are stored in this browser.
          </p>
          <button className="btn" type="button" onClick={onTest} disabled={testing}>
            {testing ? "Testing..." : "Test SMTP login"}
          </button>
        </div>
        <div className="tile span-4">
          <div className="tile-head"><h3>SMTP server</h3></div>
          <div className="field">
            <label htmlFor="smtp-host">Host</label>
            <input id="smtp-host" value={settings.host} onChange={(e) => update("host", e.target.value)} autoComplete="off" />
          </div>
          <div className="field">
            <label htmlFor="smtp-port">Port</label>
            <input id="smtp-port" type="number" min={1} max={65535} value={settings.port} onChange={(e) => update("port", Number(e.target.value))} />
          </div>
          <label className="toggle-row">
            <input type="checkbox" checked={settings.use_tls} onChange={(e) => update("use_tls", e.target.checked)} />
            <span>Use STARTTLS</span>
          </label>
        </div>
        <div className="tile span-4">
          <div className="tile-head"><h3>Account</h3></div>
          <div className="field">
            <label htmlFor="smtp-user">Gmail address</label>
            <input id="smtp-user" type="email" value={settings.username} onChange={(e) => update("username", e.target.value)} autoComplete="username" />
          </div>
          <div className="field">
            <label htmlFor="smtp-pass">Google app password</label>
            <div className="inline-control">
              <input
                id="smtp-pass"
                type={showPassword ? "text" : "password"}
                value={settings.password}
                onChange={(e) => update("password", e.target.value)}
                autoComplete="current-password"
              />
              <button className="btn compact" type="button" onClick={() => setShowPassword((v) => !v)}>
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>
          <div className="field">
            <label htmlFor="from-email">From email</label>
            <input id="from-email" type="email" value={settings.from_email} onChange={(e) => update("from_email", e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="from-name">From name</label>
            <input id="from-name" value={settings.from_name} onChange={(e) => update("from_name", e.target.value)} />
          </div>
          <button className="btn primary" type="submit">Save settings</button>
        </div>
        <div className="tile span-12">
          <div className="tile-head"><h3>Backup and transfer</h3></div>
          <div className="split-actions">
            <div>
              <strong>Move settings between browsers</strong>
              <p className="muted-text">Export keeps the Google app password blank, so re-enter it after importing.</p>
            </div>
            <div className="action-row">
              <button className="btn" type="button" onClick={exportSettings}>Export settings</button>
              <label className="btn" htmlFor="settings-import">
                Import settings
                <input
                  id="settings-import"
                  type="file"
                  accept="application/json,.json"
                  onChange={(e) => void importSettings(e.target.files?.[0] || null)}
                  hidden
                />
              </label>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
