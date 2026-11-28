"use client";

import { Building2, Plus, UserRound, UsersRound } from "lucide-react";
import Image from "next/image";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { employeePhotoUploadLimit } from "../lib/identity-path";

type Employee = {
  id: string; tenant_id: string; unit_id: string; full_name: string; job_title: string;
  status: "active" | "archived"; row_version: number; has_portrait?: boolean;
};
type Unit = { id: string; tenant_id: string; name: string; code: string; status: "active" | "archived" };
type Page = { items: Employee[]; has_more: boolean };
type Loaded = { key: string; page?: Page; units?: Unit[]; error?: string };
const pageSize = 30;
const api = "/api/identity";
const formatStatus = (employee: Employee) => employee.status === "active" ? "Active" : "Archived";

async function scopedRequest(url: string, tenantId: string, signal: AbortSignal, init?: RequestInit) {
  const result = await fetch(api + url, { credentials: "include", cache: "no-store", ...init, signal });
  if (!result.ok || result.headers.get("X-Tenant-ID") !== tenantId) throw result.status;
  return result;
}

async function fetchUnits(tenantId: string, signal: AbortSignal): Promise<Unit[]> {
  const units: Unit[] = [];
  for (let offset = 0; offset <= 1_000_000; offset += 100) {
    const response = await scopedRequest(`/organization/units?limit=100&offset=${offset}`, tenantId, signal);
    const page = await response.json() as Unit[];
    if (!Array.isArray(page) || page.some(unit => unit.tenant_id !== tenantId)) throw new Error("Invalid units");
    units.push(...page);
    if (page.length < 100) return units;
  }
  throw new Error("Unit listing exceeds capacity");
}

function EmployeePortrait({ path, name }: { path: string; name: string }) {
  const [unavailable, setUnavailable] = useState(false);
  return <span className="cc-avatar cc-avatar-portrait">
    {unavailable ? <UserRound size={38} aria-hidden="true" /> :
      <Image src={api + path} alt={`Portrait of ${name}`} width={96} height={96} unoptimized
        onError={() => setUnavailable(true)} />}
  </span>;
}

export function EmployeesWorkspace({ tenantId, company }: { tenantId: string; company: string }) {
  const [query, setQuery] = useState({ search: "", includeArchived: false, offset: 0, revision: 0 });
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [selectedId, selectEmployee] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ employee: Employee | null } | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const mutation = useRef<AbortController | null>(null);
  const path = `/employees/${tenantId}`;
  const params = new URLSearchParams({
    search: query.search, include_archived: String(query.includeArchived), offset: String(query.offset),
  });
  const url = `${path}?${params}`;
  const key = `${url}:${query.revision}`;
  const current = loaded?.key === key ? loaded : null;
  const employees = current?.page?.items ?? [];
  const units = current?.units ?? [];
  const activeUnits = units.filter(unit => unit.status === "active");
  const selected = employees.find(item => item.id === selectedId) ?? employees[0] ?? null;
  const unit = units.find(item => item.id === selected?.unit_id);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      try {
        const [response, unitRows] = await Promise.all([
          scopedRequest(url, tenantId, signal), fetchUnits(tenantId, signal),
        ]);
        const page = await response.json() as Page;
        if (!Array.isArray(page.items) || page.items.some(item => item.tenant_id !== tenantId)) throw new Error("Invalid directory");
        if (!signal.aborted) setLoaded({ key, page, units: unitRows });
      } catch (cause) {
        if (!signal.aborted) {
          const denied = cause === 401 || cause === 403 || cause === 409;
          setLoaded({ key, error: denied ? "Employee access changed. Select your company again." : "The employee directory could not be loaded." });
        }
      }
    }
    void load();
    return () => controller.abort();
  }, [key, tenantId, url]);

  useEffect(() => () => mutation.current?.abort(), []);

  async function save(suffix: string, method: "POST" | "PATCH" | "PUT" | "DELETE", body: object | File | null, success: string) {
    if (mutation.current) return;
    const controller = new AbortController();
    const photoChange = method === "PUT" || method === "DELETE";
    mutation.current = controller;
    setSaving(true);
    setNotice("");
    setError("");
    try {
      const cookie = document.cookie.split("; ").find(part => part.startsWith("pm_csrf="))?.slice(8) ?? "";
      const photo = body instanceof File ? body : null;
      const result = await scopedRequest(path + suffix, tenantId, controller.signal, {
        method, headers: { "Content-Type": photo?.type ?? "application/json", "X-CSRF-Token": decodeURIComponent(cookie) },
        body: photo ?? (body ? JSON.stringify(body) : undefined),
      });
      const saved = await result.json() as Employee;
      if (saved.tenant_id !== tenantId || (suffix && saved.id !== suffix.split("/")[1])) throw new Error("Invalid employee");
      if (controller.signal.aborted) return;
      selectEmployee(saved.id);
      setEditor(null);
      setNotice(success);
      setQuery(previous => ({ ...previous, offset: photoChange ? previous.offset : 0, revision: previous.revision + 1 }));
    } catch (cause) {
      if (controller.signal.aborted) return;
      const contextChanged = cause === 401 || cause === 403 || cause === 409;
      if (contextChanged) {
        setEditor(null);
        setQuery(previous => ({ ...previous, revision: previous.revision + 1 }));
      }
      if (contextChanged) setError("The change could not be confirmed. Review the refreshed directory before trying again.");
      else if (photoChange && cause === 413) setError("The photo exceeds 2 MB.");
      else if (photoChange && cause === 507) setError("There is not enough space in the company's storage allowance.");
      else if (photoChange && (cause === 415 || cause === 422)) setError("Choose a valid JPG or PNG photo, from 64 to 4096 pixels per side.");
      else if (photoChange) setError("The photo change was not confirmed. Try again.");
      else setError("The profile could not be saved. Review the fields and try again.");
    } finally {
      if (mutation.current === controller) mutation.current = null;
      if (!controller.signal.aborted) setSaving(false);
    }
  }

  function savePortrait(event: FormEvent<HTMLFormElement>, employee: Employee) {
    event.preventDefault();
    const file = new FormData(event.currentTarget).get("portrait");
    if (!(file instanceof File) || !file.size || file.size > employeePhotoUploadLimit
      || !["image/jpeg", "image/png"].includes(file.type)) {
      setError("Choose a JPG or PNG photo up to 2 MB.");
      return;
    }
    void save(`/${employee.id}/photo?expected_version=${employee.row_version}`, "PUT", file, "Profile photo saved.");
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor) return;
    const data = new FormData(event.currentTarget);
    const body = {
      full_name: String(data.get("full_name")).trim(),
      job_title: String(data.get("job_title")).trim(),
      unit_id: String(data.get("unit_id")),
    };
    if (!body.full_name || !body.job_title) {
      setError("Enter a full name and job title.");
      return;
    }
    const row = editor.employee;
    if (row) {
      void save(`/${row.id}`, "PATCH", { ...body, expected_version: row.row_version }, "Employee profile updated.");
    } else {
      void save("", "POST", body, "Employee profile created.");
    }
  }

  return <section className="cc-workspace" aria-labelledby="employees-heading">
    <header className="cc-workspace-header">
      <span className="cc-icon"><UsersRound size={24} aria-hidden="true" /></span>
      <div><p className="cc-overline">{company}</p><h2 id="employees-heading">Employee directory</h2>
        <p>Manage employee profiles and the teams they belong to.</p></div>
      <button className="cc-primary" type="button" disabled={!activeUnits.length || saving || !!editor}
        onClick={() => { setError(""); setNotice(""); setEditor({ employee: null }); }}>
        <Plus size={18} aria-hidden="true" /> Add employee
      </button>
    </header>
    {notice && <p className="cc-notice" role="status">{notice}</p>}
    {error && <p role="alert">{error}</p>}
    {!current && <div className="cc-card" role="status" aria-busy="true">Loading employee profiles…</div>}
    {current?.error && <div className="cc-card cc-form"><p role="alert">{current.error}</p>
      <button type="button" className="cc-secondary" onClick={() => setQuery(previous => ({ ...previous, revision: previous.revision + 1 }))}>Retry</button>
    </div>}
    {current?.page && !activeUnits.length && <p>Add an active unit in Organization before creating a profile.</p>}
    {editor && current?.page && <form className="cc-card cc-form" onSubmit={submit} aria-label={editor.employee ? "Edit employee" : "New employee"}>
      <h3>{editor.employee ? "Edit employee" : "New employee"}</h3>
      <div className="cc-form-grid">
        <label>Full name<input required maxLength={160} name="full_name" defaultValue={editor.employee?.full_name} disabled={saving} /></label>
        <label>Job title<input required maxLength={160} name="job_title" defaultValue={editor.employee?.job_title} disabled={saving} /></label>
        <label>Organization unit<select required name="unit_id" disabled={saving}
          defaultValue={activeUnits.some(item => item.id === editor.employee?.unit_id) ? editor.employee?.unit_id : ""}>
          <option value="" disabled>Choose a unit</option>
          {activeUnits.map(item => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}
        </select></label>
      </div>
      <div className="cc-actions"><button className="cc-primary" type="submit" disabled={saving}>Save profile</button>
        <button className="cc-secondary" type="button" disabled={saving} onClick={() => { setEditor(null); setError(""); }}>Cancel</button></div>
    </form>}
    <div className="cc-split cc-employee-workspace-grid">
      <section className="cc-card" aria-labelledby="employee-list-heading">
        <h3 id="employee-list-heading">Browse employees</h3>
        <form className="cc-form" onSubmit={event => {
          event.preventDefault();
          const search = String(new FormData(event.currentTarget).get("search")).trim();
          setQuery(previous => ({ ...previous, search, offset: 0 }));
        }}>
          <label>Search by name or job title<input name="search" type="search" maxLength={120} disabled={saving || !!editor} /></label>
          <div className="cc-actions"><button type="submit" className="cc-secondary" disabled={saving || !!editor}>Search</button>
            <label className="cc-directory-check"><input type="checkbox" checked={query.includeArchived} disabled={saving || !!editor}
              onChange={event => setQuery({ ...query, includeArchived: event.target.checked, offset: 0 })} /> Include archived</label></div>
        </form>
        {employees.length > 0 && <ul className="cc-person-list">{employees.map(row => <li key={row.id}>
          <button type="button" className="cc-pick" aria-pressed={row.id === selected?.id} disabled={saving || !!editor}
            onClick={() => selectEmployee(row.id)}>
            <span className="cc-avatar"><UserRound size={18} aria-hidden="true" /></span>
            <span><strong>{row.full_name}</strong><small>{row.job_title}{row.status === "archived" && " · Archived"}</small></span>
          </button>
        </li>)}</ul>}
        {current?.page && !employees.length && <p>{query.search ? "No employees match this search." : "No employees in this view."}</p>}
        {(query.offset > 0 || current?.page?.has_more) && <nav className="cc-actions" aria-label="Employee directory pages">
          <button type="button" className="cc-secondary" disabled={query.offset === 0 || saving || !!editor}
            onClick={() => setQuery({ ...query, offset: query.offset - pageSize })}>Previous</button>
          <button type="button" className="cc-secondary" disabled={!current?.page?.has_more || query.offset + pageSize > 100000 || saving || !!editor}
            onClick={() => setQuery({ ...query, offset: query.offset + pageSize })}>Next</button>
        </nav>}
      </section>
      {selected && <section className="cc-card cc-form" aria-labelledby="employee-live-profile">
        <header className="cc-employee-identity">
          {selected.has_portrait ? <EmployeePortrait key={`${selected.id}:${selected.row_version}`}
            path={`${path}/${selected.id}/photo?v=${selected.row_version}`} name={selected.full_name} /> :
            <span className="cc-avatar cc-avatar-portrait"><UserRound size={38} aria-hidden="true" /></span>}
          <div><span className="cc-chip">{formatStatus(selected)}</span>
            <h3 id="employee-live-profile">{selected.full_name}</h3><p>{selected.job_title}</p></div>
        </header>
        <dl className="cc-facts"><div><dt><Building2 size={14} aria-hidden="true" /> Organization unit</dt>
          <dd>{unit?.name ?? "Unavailable"}{unit?.status === "archived" && " (archived)"}</dd></div></dl>
        {selected.status === "active" && <form className="cc-form" key={`${selected.id}:${selected.row_version}`}
          aria-label="Profile photo" onSubmit={event => savePortrait(event, selected)}>
          <label>{selected.has_portrait ? "Replace profile photo" : "Choose profile photo"}
            <input type="file" name="portrait" accept="image/jpeg,image/png" required
              aria-describedby="employee-portrait-guide" disabled={saving || !!editor} />
          </label>
          <small id="employee-portrait-guide">JPG or PNG up to 2 MB.</small>
          <div className="cc-actions">
            <button type="submit" className="cc-secondary" disabled={saving || !!editor}>Save photo</button>
            {selected.has_portrait && <button type="button" className="cc-secondary" disabled={saving || !!editor}
              onClick={() => void save(`/${selected.id}/photo?expected_version=${selected.row_version}`, "DELETE", null, "Profile photo removed.")}>Remove photo</button>}
          </div>
        </form>}
        <div className="cc-actions">
          {selected.status === "active" && <button type="button" className="cc-primary" disabled={saving || !!editor || !activeUnits.length}
            onClick={() => { setError(""); setNotice(""); setEditor({ employee: selected }); }}>Edit profile</button>}
          <button type="button" className="cc-secondary" disabled={saving || !!editor || (selected.status === "archived" && unit?.status !== "active")}
            onClick={() => {
              const archived = selected.status === "archived";
              void save(`/${selected.id}/${archived ? "restore" : "archive"}`, "POST", { expected_version: selected.row_version },
                archived ? "Employee profile restored." : "Employee profile archived.");
            }}>{selected.status === "archived" ? "Restore employee" : "Archive employee"}</button>
        </div>
        {selected.status === "archived" && unit?.status === "archived" && <p>Restore the organization unit before restoring this employee.</p>}
      </section>}
    </div>
  </section>;
}
