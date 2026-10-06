import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, Candidate, OpportunityType, SearchProfile } from "../api";

export default function ProfilesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [types, setTypes] = useState<OpportunityType[]>([]);
  const [profiles, setProfiles] = useState<SearchProfile[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [msg, setMsg] = useState("");
  const [cv, setCv] = useState("");
  const [skills, setSkills] = useState("python, security, docker");
  const [cvFileName, setCvFileName] = useState("");
  const [coverLetterFileName, setCoverLetterFileName] = useState("");
  const [profilePrefs, setProfilePrefs] = useState<Record<string, unknown>>({});
  const [phone, setPhone] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [github, setGithub] = useState("");
  const [loadingProfile, setLoadingProfile] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [locale, setLocale] = useState("en");

  const [spName, setSpName] = useState("Cloud Security Hunt");
  const [keywords, setKeywords] = useState("cloud, security, cybersecurity");
  const [locations, setLocations] = useState("Tunisia, France, Remote");
  const [typeCodes, setTypeCodes] = useState<string[]>(["PFE_STAGE", "PFE", "JUNIOR", "REMOTE_ONLY"]);

  async function reload() {
    const [c, t, p] = await Promise.all([
      api.candidates(),
      api.opportunityTypes(),
      api.searchProfiles(),
    ]);
    setCandidates(c);
    setTypes(t);
    setProfiles(p);
    if (!selected && c[0]) setSelected(c[0].id);
  }

  useEffect(() => {
    reload().catch((e) => setMsg(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoadingProfile(true);
    api.profile(selected)
      .then((profile) => {
        setCv(profile.cv_text || "");
        setSkills((profile.skills || []).join(", "));
        setProfilePrefs(profile.preferences || {});
        setPhone(String(profile.preferences?.phone || ""));
        setLinkedin(String(profile.preferences?.linkedin || ""));
        setGithub(String(profile.preferences?.github || ""));
        const attachment = profile.preferences?.cv_attachment as { filename?: string } | undefined;
        const coverLetterAttachment = profile.preferences?.cover_letter_attachment as { filename?: string } | undefined;
        setCvFileName(attachment?.filename || "");
        setCoverLetterFileName(coverLetterAttachment?.filename || "");
      })
      .catch((e) => setMsg(String(e.message || e)))
      .finally(() => setLoadingProfile(false));
  }, [selected]);

  const readiness = useMemo(() => {
    const checks = [
      { label: "Candidate", done: Boolean(selected) },
      { label: "Skills", done: skills.split(",").some((s) => s.trim()) },
      { label: "CV text", done: cv.trim().length > 80 },
      { label: "CV file", done: Boolean(cvFileName) },
      { label: "Cover letter PDF", done: Boolean(coverLetterFileName) },
      { label: "Search profile", done: profiles.some((p) => p.candidate_id === selected) },
    ];
    return { checks, complete: checks.filter((item) => item.done).length };
  }, [coverLetterFileName, cv, cvFileName, profiles, selected, skills]);

  async function onCreateCandidate(e: FormEvent) {
    e.preventDefault();
    const c = await api.createCandidate({ name, email, locale });
    setSelected(c.id);
    setMsg(`Candidate created: ${c.name}`);
    await reload();
  }

  async function onSaveProfile(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    await api.updateProfile(selected, {
      cv_text: cv,
      skills: skills.split(",").map((s) => s.trim()).filter(Boolean),
      preferences: { ...profilePrefs, phone, linkedin, github },
    });
    setMsg("CV profile saved");
  }

  async function onCvFile(file: File | null) {
    if (!file || !selected) return;
    if (file.size > 8 * 1024 * 1024) {
      setMsg("CV file is too large. Upload a PDF/DOC/DOCX under 8 MB.");
      return;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
    const data_base64 = dataUrl.split(",")[1] || "";
    const profile = await api.updateCvAttachment(selected, {
      filename: file.name,
      content_type: file.type || "application/pdf",
      data_base64,
    });
    setCvFileName(file.name);
    setProfilePrefs(profile.preferences || {});
    setMsg(`CV attached: ${file.name}`);
  }

  async function onCoverLetterFile(file: File | null) {
    if (!file || !selected) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setMsg("Cover letter must be a PDF.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setMsg("Cover letter is too large. Upload a PDF under 8 MB.");
      return;
    }
    const dataUrl = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
    const data_base64 = dataUrl.split(",")[1] || "";
    const profile = await api.updateCoverLetterAttachment(selected, {
      filename: file.name,
      content_type: "application/pdf",
      data_base64,
    });
    setCoverLetterFileName(file.name);
    setProfilePrefs(profile.preferences || {});
    setMsg(`Cover letter attached: ${file.name}`);
  }

  async function onCreateSearch(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    await api.createSearchProfile({
      candidate_id: selected,
      name: spName,
      keywords: keywords.split(",").map((s) => s.trim()).filter(Boolean),
      locations: locations.split(",").map((s) => s.trim()).filter(Boolean),
      opportunity_type_codes: typeCodes,
    });
    setMsg("Search profile created");
    await reload();
  }

  function toggleType(code: string) {
    setTypeCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }

  return (
    <div>
      <header className="page-head">
        <div>
          <h1 className="page-title">Profiles</h1>
          <p className="page-sub">Candidates, CV evidence, and configurable opportunity types.</p>
        </div>
      </header>
      {msg && <p className="alert success mono">{msg}</p>}
      <div className="bento">
        <div className="tile span-4">
          <div className="tile-head"><h3>Setup progress</h3></div>
          <div className="readiness-meter" aria-label={`${readiness.complete} of ${readiness.checks.length} profile setup steps complete`}>
            <span style={{ width: `${(readiness.complete / readiness.checks.length) * 100}%` }} />
          </div>
          <div className="checklist">
            {readiness.checks.map((item) => (
              <div key={item.label} className={item.done ? "check done" : "check"}>{item.label}</div>
            ))}
          </div>
        </div>

        <form className="tile span-4" onSubmit={onCreateCandidate}>
          <div className="tile-head"><h3>New candidate</h3></div>
          <div className="field">
            <label htmlFor="name">Name</label>
            <input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="locale">Locale</label>
            <select id="locale" value={locale} onChange={(e) => setLocale(e.target.value)}>
              <option value="en">EN</option>
              <option value="fr">FR</option>
              <option value="ar">AR</option>
            </select>
          </div>
          <button className="btn primary" type="submit">Create</button>
        </form>

        <form className="tile span-4" onSubmit={onSaveProfile}>
          <div className="tile-head"><h3>CV evidence</h3></div>
          <div className="field">
            <label htmlFor="cand">Candidate</label>
            <select id="cand" value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">Select...</option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.email})</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="skills">Skills (comma-separated)</label>
            <input id="skills" value={skills} onChange={(e) => setSkills(e.target.value)} disabled={loadingProfile} />
          </div>
          <div className="field">
            <label htmlFor="cv">CV text</label>
            <textarea id="cv" rows={7} value={cv} onChange={(e) => setCv(e.target.value)} disabled={loadingProfile} />
          </div>
          <div className="field">
            <label htmlFor="phone">Phone for cover letters</label>
            <input id="phone" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={loadingProfile} placeholder="+216 ..." />
          </div>
          <div className="field">
            <label htmlFor="linkedin">LinkedIn URL</label>
            <input id="linkedin" value={linkedin} onChange={(e) => setLinkedin(e.target.value)} disabled={loadingProfile} placeholder="https://www.linkedin.com/in/..." />
          </div>
          <div className="field">
            <label htmlFor="github">GitHub URL</label>
            <input id="github" value={github} onChange={(e) => setGithub(e.target.value)} disabled={loadingProfile} placeholder="https://github.com/..." />
          </div>
          <div className="field">
            <label htmlFor="cvfile">CV attachment for emails</label>
            <label className="file-drop" htmlFor="cvfile">
              <strong>{cvFileName || "Upload CV"}</strong>
              <span>PDF, DOC, or DOCX under 8 MB</span>
              <input
                id="cvfile"
                type="file"
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                disabled={!selected}
                onChange={(e) => void onCvFile(e.target.files?.[0] || null)}
              />
            </label>
            {cvFileName && <span className="field-hint">{cvFileName}</span>}
          </div>
          <div className="field">
            <label htmlFor="coverletterfile">Cover letter PDF for emails</label>
            <label className="file-drop" htmlFor="coverletterfile">
              <strong>{coverLetterFileName || "Upload cover letter"}</strong>
              <span>PDF under 8 MB. It will be attached with your CV.</span>
              <input
                id="coverletterfile"
                type="file"
                accept=".pdf,application/pdf"
                disabled={!selected}
                onChange={(e) => void onCoverLetterFile(e.target.files?.[0] || null)}
              />
            </label>
            {coverLetterFileName && <span className="field-hint">{coverLetterFileName}</span>}
          </div>
          <button className="btn" type="submit" disabled={!selected}>Save profile</button>
        </form>

        <form className="tile span-12" onSubmit={onCreateSearch}>
          <div className="tile-head"><h3>Search profile</h3></div>
          <div className="field">
            <label htmlFor="spname">Name</label>
            <input id="spname" value={spName} onChange={(e) => setSpName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="kw">Keywords</label>
            <input id="kw" value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="loc">Locations</label>
            <input id="loc" value={locations} onChange={(e) => setLocations(e.target.value)} />
          </div>
          <div className="field">
            <label>Opportunity types</label>
            <div className="chip-grid">
              {types.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="chip-button"
                  aria-pressed={typeCodes.includes(t.code)}
                  onClick={() => toggleType(t.code)}
                >
                  {t.code}
                </button>
              ))}
            </div>
          </div>
          <button className="btn primary" type="submit" disabled={!selected}>Create search profile</button>
        </form>

        <div className="tile span-12">
          <div className="tile-head"><h3>Existing search profiles</h3></div>
          {profiles.length === 0 ? (
            <div className="empty">No profiles yet.</div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Keywords</th>
                    <th>Types</th>
                    <th>Active</th>
                  </tr>
                </thead>
                <tbody>
                  {profiles.map((p) => (
                    <tr key={p.id}>
                      <td>{p.name}</td>
                      <td className="mono">{p.keywords.join(", ")}</td>
                      <td className="mono">{p.opportunity_type_codes.join(", ")}</td>
                      <td><span className={`badge ${p.active ? "success" : "muted"}`}>{p.active ? "yes" : "no"}</span></td>
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
