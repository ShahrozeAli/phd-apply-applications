import { useEffect, useMemo, useState } from "react";
import { api } from "./api";

const NAV = [
  ["profile", "My Profile"],
  ["search", "Search Opportunities"],
  ["recommended", "Recommended PhDs"],
  ["funded", "Fully Funded"],
  ["eligibility", "Eligibility Analysis"],
  ["documents", "Application Documents"],
  ["outreach", "Supervisor Outreach"],
  ["approvals", "Pending Approvals"],
  ["tracker", "Application Tracker"],
  ["deadlines", "Deadlines and Notifications"],
  ["settings", "Settings"],
];

function Badge({ children, tone = "neutral" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

function FundingBadge({ value }) {
  const tone =
    value === "FULLY FUNDED"
      ? "good"
      : value === "CONDITIONALLY FUNDED"
        ? "warn"
        : value === "PARTIALLY FUNDED"
          ? "warn"
          : "neutral";
  return <Badge tone={tone}>{value || "UNVERIFIED"}</Badge>;
}

export default function App() {
  const [page, setPage] = useState("profile");
  const [profile, setProfile] = useState(null);
  const [opps, setOpps] = useState([]);
  const [selected, setSelected] = useState(null);
  const [stats, setStats] = useState(null);
  const [notes, setNotes] = useState([]);
  const [approvals, setApprovals] = useState({ applications: [], emails: [] });
  const [settings, setSettings] = useState(null);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [filters, setFilters] = useState({ country: "", funding: "", eligibility: "" });

  async function refresh() {
    const [p, o, d, n, a, s, r] = await Promise.all([
      api.profile(),
      api.opportunities(),
      api.dashboard(),
      api.notifications(),
      api.approvals(),
      api.settings(),
      api.runs(),
    ]);
    setProfile(p);
    setOpps(o);
    setStats(d);
    setNotes(n);
    setApprovals(a);
    setSettings(s);
    setRuns(r);
  }

  useEffect(() => {
    refresh().catch((err) => setMessage(err.message));
  }, []);

  const filtered = useMemo(() => {
    return opps.filter((item) => {
      if (filters.country && item.country !== filters.country) return false;
      if (filters.funding && item.funding_classification !== filters.funding) return false;
      if (filters.eligibility && item.eligibility_status !== filters.eligibility) return false;
      return true;
    });
  }, [opps, filters]);

  async function runSearch() {
    setBusy(true);
    setMessage("Searching official sources. This respects request delays and may take a minute.");
    try {
      const result = await api.discover();
      await refresh();
      setMessage(
        `Discovery finished. Inspected listings: ${result.found} new: ${result.new}. Errors: ${result.errors?.length || 0}.`
      );
      setPage("recommended");
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function openDetail(id) {
    const row = await api.opportunity(id);
    setSelected(row);
  }

  async function saveProfile(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    const next = structuredClone(profile.profile);
    next.identity.given_name = form.get("given_name");
    next.identity.family_name = form.get("family_name");
    next.identity.email = form.get("email");
    next.identity.nationality = form.get("nationality");
    next.identity.current_country = form.get("current_country");
    next.professional.profession = form.get("profession");
    next.professional.years_experience = Number(form.get("years_experience") || 0);
    next.academic.highest_completed_degree = form.get("highest_completed_degree") || null;
    next.academic.bachelor.degree_title = form.get("bachelor_title") || null;
    next.academic.bachelor.field = form.get("bachelor_field") || null;
    next.academic.bachelor.institution = form.get("bachelor_institution") || null;
    next.academic.bachelor.gpa = form.get("bachelor_gpa") || null;
    next.academic.bachelor.gpa_scale = form.get("bachelor_scale") || null;
    next.academic.masters.status = form.get("masters_status") || "unknown";
    next.academic.masters.degree_title = form.get("masters_title") || null;
    next.academic.masters.field = form.get("masters_field") || null;
    next.academic.masters.institution = form.get("masters_institution") || null;
    next.academic.masters.gpa = form.get("masters_gpa") || null;
    next.academic.english.test_type = form.get("english_test") || null;
    next.academic.english.overall_score = form.get("english_score") || null;
    next.academic.english.medium_of_instruction_waiver = form.get("english_waiver") || null;
    next.preferences.research_interests = (form.get("research_interests") || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    next.academic.masters.thesis_title = form.get("thesis_title") || null;
    next.academic.masters.thesis_abstract = form.get("thesis_abstract") || null;
    const saved = await api.saveProfile(next);
    setProfile(saved);
    setMessage("Profile saved. Academic blanks were left blank rather than assumed.");
  }

  const ident = profile?.profile?.identity || {};
  const ac = profile?.profile?.academic || {};
  const pro = profile?.profile?.professional || {};
  const pref = profile?.profile?.preferences || {};

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <strong>PhD Apply Bot</strong>
          <span>Europe · fully funded · international</span>
        </div>
        {NAV.map(([id, label]) => (
          <button key={id} className={page === id ? "nav active" : "nav"} onClick={() => setPage(id)}>
            {label}
          </button>
        ))}
      </aside>
      <main>
        {message && <div className="flash">{message}</div>}
        {page === "profile" && profile && (
          <section>
            <h1>My Profile</h1>
            <p>
              Completeness: <strong>{profile.completeness_score}%</strong>. Final eligibility and document
              generation stay blocked until the academic fields below are filled.
            </p>
            {profile.missing_fields?.length > 0 && (
              <div className="panel warn-panel">
                <h3>Still needed from you</h3>
                <ul>
                  {profile.missing_fields.map((item) => (
                    <li key={item.path}>{item.label}</li>
                  ))}
                </ul>
              </div>
            )}
            <form className="grid-form" onSubmit={saveProfile}>
              <label>Given name<input name="given_name" defaultValue={ident.given_name || ""} /></label>
              <label>Family name<input name="family_name" defaultValue={ident.family_name || ""} /></label>
              <label>Email<input name="email" defaultValue={ident.email || ""} /></label>
              <label>Nationality<input name="nationality" defaultValue={ident.nationality || ""} /></label>
              <label>Current country<input name="current_country" defaultValue={ident.current_country || ""} /></label>
              <label>Profession<input name="profession" defaultValue={pro.profession || ""} /></label>
              <label>Years of experience<input name="years_experience" defaultValue={pro.years_experience || ""} /></label>
              <label>Highest completed degree<input name="highest_completed_degree" defaultValue={ac.highest_completed_degree || ""} /></label>
              <label>Bachelor title<input name="bachelor_title" defaultValue={ac.bachelor?.degree_title || ""} /></label>
              <label>Bachelor field<input name="bachelor_field" defaultValue={ac.bachelor?.field || ""} /></label>
              <label>Bachelor institution<input name="bachelor_institution" defaultValue={ac.bachelor?.institution || ""} /></label>
              <label>Bachelor GPA<input name="bachelor_gpa" defaultValue={ac.bachelor?.gpa || ""} /></label>
              <label>GPA scale<input name="bachelor_scale" defaultValue={ac.bachelor?.gpa_scale || ""} /></label>
              <label>
                Master's status
                <select name="masters_status" defaultValue={ac.masters?.status || "unknown"}>
                  <option value="unknown">unknown</option>
                  <option value="completed">completed</option>
                  <option value="in progress">in progress</option>
                  <option value="not started">not started</option>
                </select>
              </label>
              <label>Master's title<input name="masters_title" defaultValue={ac.masters?.degree_title || ""} /></label>
              <label>Master's field<input name="masters_field" defaultValue={ac.masters?.field || ""} /></label>
              <label>Master's institution<input name="masters_institution" defaultValue={ac.masters?.institution || ""} /></label>
              <label>Master's GPA<input name="masters_gpa" defaultValue={ac.masters?.gpa || ""} /></label>
              <label>English test<input name="english_test" defaultValue={ac.english?.test_type || ""} placeholder="IELTS / TOEFL / waiver" /></label>
              <label>English score<input name="english_score" defaultValue={ac.english?.overall_score || ""} /></label>
              <label>English waiver notes<input name="english_waiver" defaultValue={ac.english?.medium_of_instruction_waiver || ""} /></label>
              <label className="wide">Research interests (comma separated)<input name="research_interests" defaultValue={(pref.research_interests || []).join(", ")} /></label>
              <label className="wide">Master's thesis title<input name="thesis_title" defaultValue={ac.masters?.thesis_title || ""} /></label>
              <label className="wide">Thesis abstract<textarea name="thesis_abstract" defaultValue={ac.masters?.thesis_abstract || ""} /></label>
              <button type="submit">Save profile</button>
            </form>
          </section>
        )}

        {page === "search" && (
          <section>
            <h1>Search Opportunities</h1>
            <p>
              Discovery uses EURAXESS, AcademicTransfer, and official university pages. Third-party
              aggregators are not treated as funding proof.
            </p>
            <button disabled={busy} onClick={runSearch}>
              {busy ? "Searching…" : "Run discovery now"}
            </button>
            <h3>Recent runs</h3>
            <ul className="plain">
              {runs.map((run) => (
                <li key={run.id}>
                  {run.started_at} · {run.status} · found {run.found_count} · new {run.new_count}
                </li>
              ))}
            </ul>
          </section>
        )}

        {["recommended", "funded", "eligibility", "tracker"].includes(page) && (
          <section>
            <h1>
              {page === "recommended" && "Recommended PhDs"}
              {page === "funded" && "Fully Funded Opportunities"}
              {page === "eligibility" && "Eligibility Analysis"}
              {page === "tracker" && "Application Tracker"}
            </h1>
            {stats && (
              <div className="stats">
                <Stat label="Discovered" value={stats.total_discovered} />
                <Stat label="Fully funded" value={stats.fully_funded_verified} />
                <Stat label="Primary queue" value={stats.primary_queue} />
                <Stat label="Deadlines 30d" value={stats.upcoming_deadlines} />
              </div>
            )}
            <div className="filters">
              <input
                placeholder="Country"
                value={filters.country}
                onChange={(e) => setFilters({ ...filters, country: e.target.value })}
              />
              <select value={filters.funding} onChange={(e) => setFilters({ ...filters, funding: e.target.value })}>
                <option value="">All funding</option>
                <option>FULLY FUNDED</option>
                <option>CONDITIONALLY FUNDED</option>
                <option>PARTIALLY FUNDED</option>
                <option>UNVERIFIED</option>
              </select>
              <select
                value={filters.eligibility}
                onChange={(e) => setFilters({ ...filters, eligibility: e.target.value })}
              >
                <option value="">All eligibility</option>
                <option>ELIGIBLE</option>
                <option>LIKELY ELIGIBLE</option>
                <option>NEEDS VERIFICATION</option>
                <option>NOT ELIGIBLE</option>
              </select>
            </div>
            <OpportunityList
              items={filtered.filter((item) => {
                if (page === "funded") return item.funding_classification === "FULLY FUNDED";
                if (page === "recommended") return item.queued || item.match_score >= 40;
                return true;
              })}
              onOpen={openDetail}
              onDecide={async (id, decision) => {
                await api.decide(id, decision);
                await refresh();
              }}
            />
          </section>
        )}

        {page === "documents" && (
          <section>
            <h1>Application Documents</h1>
            <p>Packages are written only from your stored facts. Incomplete academic data blocks generation.</p>
            <OpportunityList
              items={opps.filter((item) => item.queued || item.user_decision === "APPROVE")}
              onOpen={openDetail}
              extraAction={async (id) => {
                const result = await api.prepare(id);
                setMessage(result.blocked ? result.reason : `Package ready: ${result.folder}`);
                await refresh();
              }}
              extraLabel="Prepare package"
            />
          </section>
        )}

        {page === "outreach" && (
          <section>
            <h1>Supervisor Outreach</h1>
            <p>Drafts stay unsent until you enable a separate, narrow email workflow.</p>
            {approvals.emails.map((email) => (
              <article key={email.id} className="card">
                <h3>{email.subject}</h3>
                <p>
                  {email.supervisor_name} · {email.supervisor_email || "email not extracted from an official page"}
                </p>
                <pre>{email.body}</pre>
              </article>
            ))}
            {approvals.emails.length === 0 && <p>No drafted emails yet.</p>}
          </section>
        )}

        {page === "approvals" && (
          <section>
            <h1>Pending Approvals</h1>
            <h3>Applications</h3>
            {approvals.applications.map((item) => (
              <article key={item.id} className="card">
                <p>Application #{item.id} · {item.status}</p>
                <p>{item.package_folder}</p>
                <button onClick={() => api.approveApp(item.id, true).then(refresh)}>Approve (do not submit)</button>
                <button className="ghost" onClick={() => api.approveApp(item.id, false).then(refresh)}>
                  Reject
                </button>
              </article>
            ))}
            <h3>Emails</h3>
            {approvals.emails.map((item) => (
              <article key={item.id} className="card">
                <p>{item.subject}</p>
                <button onClick={() => api.approveEmail(item.id, true).then(refresh)}>Approve draft (do not send)</button>
              </article>
            ))}
          </section>
        )}

        {page === "deadlines" && (
          <section>
            <h1>Deadlines and Notifications</h1>
            <ul className="plain">
              {notes.map((n) => (
                <li key={n.id}>
                  <strong>{n.title}</strong>
                  <div>{n.body}</div>
                  <small>{n.created_at}</small>
                </li>
              ))}
            </ul>
          </section>
        )}

        {page === "settings" && settings && (
          <section>
            <h1>Settings</h1>
            <ul className="plain">
              <li>LLM provider: {settings.llm_provider}</li>
              <li>Daily discovery hour: {settings.daily_discovery_hour}:00</li>
              <li>Auto-submit applications: {String(settings.auto_submit_applications)} (hard-disabled)</li>
              <li>Auto-send emails: {String(settings.auto_send_emails)} (hard-disabled)</li>
              <li>Database: {settings.database_backend}</li>
            </ul>
            <p>API keys belong in `.env`. Application logins are never stored in this MVP.</p>
          </section>
        )}
      </main>

      {selected && (
        <div className="drawer">
          <button className="ghost" onClick={() => setSelected(null)}>
            Close
          </button>
          <h2>{selected.position_title}</h2>
          <p>
            {selected.university} · {selected.city}, {selected.country}
          </p>
          <p>
            <FundingBadge value={selected.funding_classification} />{" "}
            <Badge>{selected.eligibility_status}</Badge> <Badge>Score {selected.match_score}</Badge>
          </p>
          <p>{selected.eligibility_reason}</p>
          <p>
            Salary/stipend: {selected.salary_or_stipend || "not extracted"} · Duration:{" "}
            {selected.funding_duration || "not extracted"} · Tuition: {selected.tuition_coverage}
          </p>
          <p>{selected.notes}</p>
          <p>Supervisor: {selected.supervisor || "not extracted"}</p>
          <p>Required documents: {selected.required_documents || "not extracted"}</p>
          <p>Deadline: {selected.application_deadline || "unknown"}</p>
          <a className="button" href={selected.official_vacancy_url} target="_blank" rel="noreferrer">
            Open official vacancy
          </a>
          <a className="button" href={selected.official_application_url} target="_blank" rel="noreferrer">
            Open official application page
          </a>
          <h3>Verified claims</h3>
          <ul>
            {(selected.claims || []).map((c, i) => (
              <li key={i}>
                <strong>{c.claim_type}</strong>: {c.claim_value} {c.is_inference ? "(inference)" : "(from listing)"}
                <div>
                  <a href={c.source_url} target="_blank" rel="noreferrer">
                    source
                  </a>
                </div>
              </li>
            ))}
          </ul>
          <h3>Manual checklist</h3>
          <ol>
            {(selected.checklist || []).map((c, i) => (
              <li key={i}>{c.step}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function OpportunityList({ items, onOpen, onDecide, extraAction, extraLabel }) {
  if (!items.length) return <p>No opportunities in this view yet. Run discovery from Search Opportunities.</p>;
  return (
    <div className="cards">
      {items.map((item) => (
        <article key={item.id} className="card">
          <div className="card-head">
            <h3>{item.position_title}</h3>
            <span>{item.match_score}</span>
          </div>
          <p>
            {item.university} · {item.country}
          </p>
          <p>
            <FundingBadge value={item.funding_classification} /> <Badge>{item.eligibility_status}</Badge>
          </p>
          <p>Deadline: {item.application_deadline ? item.application_deadline.slice(0, 10) : "unknown"}</p>
          <div className="actions">
            <button onClick={() => onOpen(item.id)}>Details</button>
            <a href={item.official_vacancy_url} target="_blank" rel="noreferrer">
              Official page
            </a>
            {onDecide && (
              <>
                <button onClick={() => onDecide(item.id, "APPROVE")}>Approve</button>
                <button className="ghost" onClick={() => onDecide(item.id, "SAVE")}>
                  Save
                </button>
                <button className="ghost" onClick={() => onDecide(item.id, "REJECT")}>
                  Reject
                </button>
              </>
            )}
            {extraAction && <button onClick={() => extraAction(item.id)}>{extraLabel}</button>}
          </div>
        </article>
      ))}
    </div>
  );
}
