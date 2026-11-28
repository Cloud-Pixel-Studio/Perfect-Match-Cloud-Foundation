"use client";

import { Building2, GraduationCap, KeyRound, Layers3, Search, ShieldCheck, UserRound, UserRoundPlus, UsersRound } from "lucide-react";
import Image from "next/image";
import { useState, type FormEvent } from "react";
import { BrandMark } from "./brand-mark";
import { ThemeToggle } from "./theme-toggle";

type Screen = "people" | "company" | "platform";
const screens = [
  { id: "people", label: "People & training", Icon: UsersRound },
  { id: "company", label: "Company settings", Icon: Building2 },
  { id: "platform", label: "SaaS operations", Icon: Layers3 },
] as const;
type Person = { id: string; name: string; title: string; unit: string; status: "Active" | "Archived"; photo?: string };
type Course = { id: string; title: string };
type Enrollment = { personId: string; courseId: string; dueOn: string; completed: boolean };
const initialPeople: Person[] = [
  { id: "EMP-101", name: "Lucía Rivera", title: "Quality coordinator", unit: "Quality", status: "Active" },
  { id: "EMP-102", name: "Marcos Peña", title: "Receiving supervisor", unit: "Operations", status: "Active" },
  { id: "EMP-103", name: "Elena Cruz", title: "Inspection technician", unit: "Operations", status: "Active" },
];
const initialCourses: Course[] = [
  { id: "COURSE-01", title: "Controlled documentation" },
  { id: "COURSE-02", title: "Supplier lot traceability" },
  { id: "COURSE-03", title: "Internal audit fundamentals" },
];
const initialEnrollments: Enrollment[] = [
  { personId: "EMP-101", courseId: "COURSE-01", dueOn: "2026-11-04", completed: true },
  { personId: "EMP-101", courseId: "COURSE-03", dueOn: "2026-12-04", completed: false },
  { personId: "EMP-102", courseId: "COURSE-02", dueOn: "2026-11-21", completed: false },
  { personId: "EMP-103", courseId: "COURSE-02", dueOn: "2026-12-06", completed: false },
];
const previewDate = "2026-11-27";
const units = ["Quality", "Operations", "Administration"];
const displayDate = (date: string) => new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(date + "T00:00:00Z"));

function PersonAvatar({ person }: { person: Person }) {
  return <span className="cc-avatar">
    {person.photo
      ? <Image src={person.photo} width={64} height={64} alt={person.name ? `Photo of ${person.name}` : "Employee photo preview"} unoptimized />
      : <span aria-hidden="true">{person.name.split(/\s+/).slice(0, 2).map(name => name[0]).join("").toUpperCase() || "—"}</span>}
  </span>;
}

async function localPhoto(file: File) {
  if (file.size > 2_000_000 || !["image/jpeg", "image/png"].includes(file.type)) throw new Error("Choose a PNG or JPG up to 2 MB.");
  const bytes = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  const signature = file.type === "image/png" ? [137, 80, 78, 71, 13, 10, 26, 10] : [255, 216, 255];
  if (!signature.every((byte, index) => bytes[index] === byte)) throw new Error("Choose a valid PNG or JPG.");
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === "string" ? resolve(reader.result) : reject(new Error("The photo could not be read."));
    reader.onerror = () => reject(new Error("The photo could not be read."));
    reader.readAsDataURL(file);
  });
}

function PersonEditor({ person, onSave, onCancel }: { person: Person; onSave: (person: Person) => void; onCancel: () => void }) {
  const [photo, setPhoto] = useState(person.photo);
  const [issue, setIssue] = useState("");
  const [reading, setReading] = useState(false);
  const isNew = !person.id;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const name = String(fields.get("name") ?? "").trim();
    const title = String(fields.get("title") ?? "").trim();
    const unit = String(fields.get("unit") ?? "");
    if (!name || !title || !units.includes(unit)) {
      setIssue("Enter a name, a job title and a department.");
      return;
    }
    onSave({ ...person, id: person.id || crypto.randomUUID(), name, title, unit, photo });
  }
  return <form className="cc-card cc-form" onSubmit={submit} aria-label={isNew ? "Add employee" : "Edit employee"}>
    <h3>{isNew ? "New employee" : "Edit employee"}</h3>
    <div className="cc-form-grid">
      <label>Full name<input name="name" defaultValue={person.name} maxLength={90} required /></label>
      <label>Job title<input name="title" defaultValue={person.title} maxLength={90} required /></label>
      <label>Department<select name="unit" defaultValue={person.unit}>{units.map(unit => <option key={unit}>{unit}</option>)}</select></label>
      <label>Employee photo<input type="file" accept="image/png,image/jpeg" onChange={async event => {
        const file = event.target.files?.[0];
        if (!file) return;
        setIssue(""); setReading(true);
        try { setPhoto(await localPhoto(file)); }
        catch (cause) { setIssue(cause instanceof Error ? cause.message : "The photo could not be read."); }
        finally { setReading(false); }
      }} disabled={reading} /></label>
    </div>
    {photo && <div className="cc-person-photo"><PersonAvatar person={{ ...person, photo }} />
      <button className="cc-secondary" type="button" onClick={() => setPhoto(undefined)} disabled={reading}>Remove photo</button>
    </div>}
    {issue && <p role="alert">{issue}</p>}
    <div className="cc-actions">
      <button type="submit" className="cc-primary" disabled={reading}>Save sample employee</button>
      <button type="button" className="cc-secondary" onClick={onCancel}>Cancel</button>
    </div>
  </form>;
}

function PeoplePreview() {
  const [people, setPeople] = useState(initialPeople);
  const [courses, setCourses] = useState(initialCourses);
  const [enrollments, setEnrollments] = useState(initialEnrollments);
  const [selected, setSelected] = useState(initialPeople[0].id);
  const [filter, setFilter] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [draft, setDraft] = useState<Person | null>(null);
  const [courseForm, showCourseForm] = useState(false);
  const [notice, setNotice] = useState("");
  const current = people.find(person => person.id === selected);
  const matching = people.filter(person => (includeArchived || person.status === "Active")
    && `${person.name} ${person.title} ${person.unit}`.toLowerCase().includes(filter.trim().toLowerCase()));
  const activeIDs = new Set(people.filter(person => person.status === "Active").map(person => person.id));
  const openEnrollments = enrollments.filter(item => activeIDs.has(item.personId) && !item.completed);
  const assigned = enrollments.filter(item => item.personId === selected);
  const available = courses.filter(course => !assigned.some(item => item.courseId === course.id));

  function addCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = String(new FormData(event.currentTarget).get("title")).trim();
    if (!title || courses.some(course => course.title.toLowerCase() === title.toLowerCase())) {
      setNotice("Enter a new course title.");
      return;
    }
    setCourses(previous => [...previous, { title, id: crypto.randomUUID() }]);
    showCourseForm(false);
    setNotice("Sample course added.");
  }
  function assign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!current || current.status !== "Active") return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const courseId = String(data.get("course"));
    const dueOn = String(data.get("due"));
    if (!available.some(course => course.id === courseId) || !/^\d{4}-\d\d-\d\d$/.test(dueOn)) return;
    setEnrollments(previous => [...previous, { personId: current.id, courseId, dueOn, completed: false }]);
    form.reset();
    setNotice("Sample training assigned.");
  }
  return <section className="cc-preview-content" aria-labelledby="people-preview-heading">
    <div className="cc-page-heading"><div><h2 id="people-preview-heading">People & training</h2><p>See who is trained, what is due, and where to follow up.</p></div>
      <div className="cc-actions">
        <button className="cc-secondary" aria-expanded={courseForm} type="button" onClick={() => showCourseForm(!courseForm)}><GraduationCap size={18} aria-hidden="true" /> New course</button>
        <button className="cc-primary" type="button" onClick={() => setDraft({ id: "", name: "", title: "", unit: units[0], status: "Active" })}><UserRoundPlus size={18} aria-hidden="true" /> Add employee</button>
      </div>
    </div>
    <dl className="cc-metrics">
      <div><dt>Active employees</dt><dd>{activeIDs.size}</dd></div>
      <div><dt>Open assignments</dt><dd>{openEnrollments.length}</dd></div>
      <div><dt>Overdue training</dt><dd className="cc-overdue">{openEnrollments.filter(item => item.dueOn < previewDate).length}</dd></div>
    </dl>
    {notice && <p className="cc-notice" role="status">{notice}</p>}
    {courseForm && <form className="cc-card cc-form" onSubmit={addCourse} aria-label="New course">
      <h3>New course</h3>
      <label>Course title<input name="title" required maxLength={120} /></label>
      <button className="cc-primary" type="submit">Save sample course</button>
    </form>}
    {draft && <PersonEditor key={draft.id || "new"} person={draft} onCancel={() => setDraft(null)} onSave={person => {
      setPeople(previous => draft.id ? previous.map(item => item.id === person.id ? person : item) : [...previous, person]);
      setSelected(person.id);
      setDraft(null);
      setNotice("Sample employee saved.");
    }} />}
    <div className="cc-split">
      <section className="cc-card cc-register" aria-labelledby="employees-heading">
        <h3 id="employees-heading">Employee directory</h3>
        <label className="cc-search"><Search size={17} aria-hidden="true" /><span className="sr-only">Search employees</span>
          <input type="search" value={filter} onChange={event => setFilter(event.target.value)} placeholder="Search name, team or title" />
        </label>
        <label className="cc-check"><input type="checkbox" checked={includeArchived} onChange={event => setIncludeArchived(event.target.checked)} /> Show archived</label>
        {matching.length ? <ul className="cc-person-list">{matching.map(person => <li key={person.id}>
          <button className="cc-pick" aria-pressed={person.id === selected} type="button" onClick={() => setSelected(person.id)}>
            <PersonAvatar person={person} /><span><strong>{person.name}</strong><small>{person.title}</small></span>
          </button>
        </li>)}</ul> : <p>No employees match the selected filters.</p>}
      </section>
      {current && <section className="cc-card" aria-labelledby="employee-profile-heading">
        <header className="cc-profile-header">
          <PersonAvatar person={current} />
          <div><span className="cc-chip">{current.status}</span><h3 id="employee-profile-heading">{current.name}</h3><p>{current.title} · {current.unit}</p></div>
          <button type="button" className="cc-secondary" onClick={() => setDraft(current)}>Edit profile</button>
        </header>
        <section className="cc-profile-training" aria-label="Assigned training">
          <h4>Assigned training</h4>
          {assigned.length ? <ul className="cc-training-list">{assigned.map(item => {
            const status = item.completed ? "Completed" : item.dueOn < previewDate ? "Overdue" : "Assigned";
            const title = courses.find(course => course.id === item.courseId)?.title;
            return <li key={item.courseId}>
              <div><strong>{title}</strong><small>Due {displayDate(item.dueOn)}</small></div>
              <span className="cc-chip" data-status={status}>{status}</span>
              {!item.completed && current.status === "Active" && <button className="cc-secondary" type="button"
                aria-label={`Record completion for ${title}`} onClick={() => {
                setEnrollments(previous => previous.map(entry => entry === item ? { ...entry, completed: true } : entry));
                setNotice("Sample completion recorded.");
              }}>Record completion</button>}
            </li>;
          })}</ul> : <p>No courses are assigned to this employee.</p>}
          {current.status === "Active" && available.length > 0 && <form className="cc-assignment" onSubmit={assign} aria-label="Assign training">
            <label>Course<select name="course" required defaultValue=""><option value="" disabled>Choose a course</option>
              {available.map(course => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label>
            <label>Due date<input type="date" name="due" required /></label>
            <button className="cc-primary" type="submit">Assign course</button>
          </form>}
        </section>
        <button type="button" className="cc-secondary" onClick={() => {
          const status = current.status === "Active" ? "Archived" : "Active";
          setPeople(previous => previous.map(person => person.id === current.id ? { ...person, status } : person));
          setNotice(status === "Archived" ? "Sample employee archived. Training history remains visible." : "Sample employee restored.");
        }}>{current.status === "Active" ? "Archive employee" : "Restore employee"}</button>
      </section>}
    </div>
  </section>;
}

function CompanyPreview() {
  const [name, setName] = useState("Northstar Components");
  const [accent, setAccent] = useState("teal");
  const [timezone, setTimezone] = useState("America/New_York");
  const [logo, setLogo] = useState<string>();
  const [fileIssue, setFileIssue] = useState("");
  return <section className="cc-preview-content" aria-labelledby="company-preview-heading">
    <div className="cc-page-heading"><div><h2 id="company-preview-heading">Company settings</h2><p>Set your company’s identity and defaults for its quality workspace.</p></div></div>
    <div className="cc-split cc-settings-split">
      <section className="cc-card cc-form" aria-label="Workspace appearance">
        <h3>Workspace appearance</h3>
        <label>Company display name<input maxLength={90} value={name} onChange={event => setName(event.target.value)} /></label>
        <label>Accent palette<select value={accent} onChange={event => setAccent(event.target.value)}>
          <option value="teal">Perfect Match teal</option><option value="blue">Slate blue</option><option value="plum">Plum</option>
        </select></label>
        <label>Company time zone<select value={timezone} onChange={event => setTimezone(event.target.value)}>
          <option>America/New_York</option><option>America/Puerto_Rico</option><option>America/Mexico_City</option><option>UTC</option>
        </select></label>
        <label>Company logo<input type="file" accept="image/png,image/jpeg" onChange={async event => {
          const file = event.target.files?.[0];
          if (!file) return;
          setFileIssue("");
          try { setLogo(await localPhoto(file)); }
          catch { setFileIssue("Choose a valid PNG or JPG up to 2 MB."); }
        }} /></label>
        {fileIssue && <p role="alert">{fileIssue}</p>}
        {logo && <button type="button" className="cc-secondary" onClick={() => setLogo(undefined)}>Remove preview logo</button>}
      </section>
      <section className="cc-card cc-brand-preview" data-accent={accent} aria-label="Company appearance preview">
        {logo ? <span className="cc-avatar"><Image src={logo} width={64} height={64} alt="Company logo preview" unoptimized /></span>
          : <span className="cc-icon"><Building2 aria-hidden="true" size={21} /></span>}
        <div><small>Workspace preview</small><h3>{name.trim() || "Company name"}</h3><p>{timezone}</p></div>
      </section>
    </div>
    <div className="cc-link-grid">
      <section className="cc-card"><Building2 aria-hidden="true" /><h3>Structure</h3><p>Sites, departments, operating language and local dates.</p></section>
      <section className="cc-card"><KeyRound aria-hidden="true" /><h3>People and access</h3><p>Invitations, seat assignments, unit responsibilities and role templates.</p></section>
      <section className="cc-card"><ShieldCheck aria-hidden="true" /><h3>QMS defaults</h3><p>Document templates, approval responsibilities and reminders by department.</p></section>
    </div>
  </section>;
}

const tenants = [
  { name: "Northstar Components", status: "Active", plan: "Basic", seats: "3 / 3", addon: "ISO 9001", health: "Operational" },
  { name: "Meridian Fabrication", status: "Provisioning", plan: "Basic", seats: "1 / 3", addon: "ISO 9001", health: "Provisioning queued" },
  { name: "Pacific Materials", status: "Suspended", plan: "Basic", seats: "2 / 3", addon: "ISO 9001", health: "Service paused" },
] as const;

function PlatformPreview() {
  const [filter, setFilter] = useState("All");
  const [selected, setSelected] = useState<string>(tenants[0].name);
  const visible = tenants.filter(tenant => filter === "All" || tenant.status === filter);
  const current = visible.find(tenant => tenant.name === selected) ?? visible[0];
  return <section className="cc-preview-content" aria-labelledby="ops-preview-heading">
    <div className="cc-page-heading"><div><h2 id="ops-preview-heading">SaaS operations</h2><p>Manage subscription lifecycle and service health across companies.</p></div><span className="cc-chip"><ShieldCheck size={16} aria-hidden="true" /> Platform operator</span></div>
    <dl className="cc-metrics">
      <div><dt>Active companies</dt><dd>{tenants.filter(tenant => tenant.status === "Active").length}</dd></div>
      <div><dt>Provisioning</dt><dd>{tenants.filter(tenant => tenant.status === "Provisioning").length}</dd></div>
      <div><dt>Suspended</dt><dd>{tenants.filter(tenant => tenant.status === "Suspended").length}</dd></div>
    </dl>
    <div className="cc-split">
      <section className="cc-card" aria-labelledby="tenant-register-heading">
        <h3 id="tenant-register-heading">Companies</h3>
        <label className="cc-filter">Company status<select value={filter} onChange={event => setFilter(event.target.value)}>
          {["All", "Active", "Provisioning", "Suspended"].map(status => <option key={status}>{status}</option>)}</select></label>
        <ul className="cc-person-list">{visible.map(tenant => <li key={tenant.name}><button type="button" className="cc-pick"
          aria-pressed={current?.name === tenant.name} onClick={() => setSelected(tenant.name)}>
          <Building2 size={20} aria-hidden="true" /><span><strong>{tenant.name}</strong><small>{tenant.status}</small></span>
        </button></li>)}</ul>
      </section>
      {current && <section className="cc-card" aria-label="Company subscription preview">
        <header className="cc-profile-header"><span className="cc-icon"><Building2 size={22} aria-hidden="true" /></span>
          <div><h3>{current.name}</h3><p>{current.health}</p></div></header>
        <dl className="cc-facts">
          <div><dt>Plan</dt><dd>{current.plan}</dd></div><div><dt>Seats used</dt><dd>{current.seats}</dd></div>
          <div><dt>ISO addon</dt><dd>{current.addon}</dd></div><div><dt>Lifecycle</dt><dd>{current.status}</dd></div>
        </dl>
      </section>}
    </div>
    <div className="cc-link-grid">
      <section className="cc-card"><h3>Billing and entitlements</h3><p>Plans, invoices, addon activation and seat limits.</p></section>
      <section className="cc-card"><h3>Service health</h3><p>Incidents, deployments, backups and restoration evidence.</p></section>
      <section className="cc-card"><h3>Platform audit</h3><p>Operator actions by company, with timestamp and reason.</p></section>
    </div>
  </section>;
}

export function ControlCenterPreview() {
  const [screen, setScreen] = useState<Screen>("people");
  return <main className="cc-prototype">
    <header className="cc-prototype-header">
      <div className="cc-brand"><BrandMark /><span><strong>Perfect Match QMS</strong><small>Control centers</small></span></div>
      <ThemeToggle />
    </header>
    <div className="cc-prototype-layout">
      <aside className="cc-rail">
        <span className="cc-overline">Design review</span>
        <nav aria-label="Control center previews">{screens.map(({ id, label, Icon }) => <button key={id} type="button" aria-pressed={screen === id} onClick={() => setScreen(id)}>
          <Icon aria-hidden="true" size={19} /> {label}
        </button>)}</nav>
        <p><UserRound size={16} aria-hidden="true" /> Sample records. Changes stay on this page until reload.</p>
      </aside>
      <div className="cc-screen">
        <div hidden={screen !== "people"}><PeoplePreview /></div>
        <div hidden={screen !== "company"}><CompanyPreview /></div>
        <div hidden={screen !== "platform"}><PlatformPreview /></div>
      </div>
    </div>
  </main>;
}
