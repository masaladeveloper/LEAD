import { useEffect, useRef, useState } from "react";
import {
  Bell,
  Check,
  ChevronLeft,
  ChevronRight,
  Columns3,
  Download,
  FileSpreadsheet,
  History as HistoryIcon,
  Image,
  List,
  LoaderCircle,
  Plus,
  Pencil,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  X,
  Maximize2,
  Minimize2,
  Mail,
} from "lucide-react";
import { api, downloadReport, initialize } from "./api";
import { cardBlob, renderCard } from "./card";
import { fields, responses, statuses } from "./types";
import type {
  Detail,
  Job,
  Lead,
  Reminder,
  Settings,
  Collection,
  CollectionRequest,
  Preferences,
  ReplyRequest,
} from "./types";
import "./style.css";

type View = "leads" | "followups" | "replies" | "reports" | "settings";
const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const display = (value: unknown) =>
  value == null || value === "" ? "—" : String(value);
const time = (value: string) =>
  value ? value.replace("T", " ").slice(0, 16) : "Not recorded";
const defaultColumns = [
  "customer_name",
  "lead_id",
  "enquiry_date",
  "contact_no",
  "model",
  "responded",
  "relevance",
  "status",
  "follow_up_date",
];
const tableFields: Record<string, string> = {
  ...fields,
  responded: "Customer response",
  relevance: "Relevance",
  updated_at: "Last updated",
};
function Select({
  value,
  choices,
  onChange,
  label,
}: {
  value: string;
  choices: string[];
  onChange: (s: string) => void;
  label: string;
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {!choices.includes(value) && <option>{value}</option>}
      {choices.map((v) => (
        <option key={v} value={v}>
          {(
            {
              latest: "Date: newest first",
              oldest: "Date: oldest first",
              name_asc: "Name: A to Z",
              name_desc: "Name: Z to A",
              call_id_asc: "Call ID: A to Z",
              call_id_desc: "Call ID: Z to A",
            } as Record<string, string>
          )[v] ||
            v ||
            "Not set"}
        </option>
      ))}
    </select>
  );
}
function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const old = document.activeElement as HTMLElement;
    ref.current?.focus();
    const key = (e: KeyboardEvent) => {
      const dialogs = document.querySelectorAll('[role="dialog"]');
      if (ref.current !== dialogs[dialogs.length - 1]) return;
      if (e.key === "Escape") close.current();
      if (e.key === "Tab") {
        const targets = ref.current?.querySelectorAll<HTMLElement>(
          'button, input, select, textarea, [tabindex="0"]',
        );
        if (!targets?.length) return;
        const first = targets[0],
          last = targets[targets.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      old?.focus();
    };
  }, []);
  return (
    <div
      className="overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={"modal " + (wide ? "wide" : "")}
      >
        <header>
          <div>
            <span className="eyebrow">LEAD WORKSPACE</span>
            <h2>{title}</h2>
          </div>
          <button className="icon" aria-label="Close dialog" onClick={onClose}>
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

export default function App() {
  const [ready, setReady] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionId, setCollectionId] = useState<number | null>(null);
  const [viewYear, setViewYear] = useState<number | null>(
    new Date().getFullYear(),
  );
  const [preferences, setPreferences] = useState<Preferences>({
    default_enquiry_year: "current",
    resolved_year: new Date().getFullYear(),
    auto_check_mail: true,
  });
  const [expanded, setExpanded] = useState(false);
  const [resultsOpen, setResultsOpen] = useState(false);
  const [replyRequests, setReplyRequests] = useState<ReplyRequest[]>([]);
  const previousRequests = useRef<Set<number> | null>(null);
  const scopeQuery = collectionId
    ? `&collection_id=${collectionId}`
    : viewYear
      ? `&year=${viewYear}`
      : "&all_years=true";
  const [collectionDialog, setCollectionDialog] = useState(false);
  const [rescanCollection, setRescanCollection] = useState(false);
  const [startingCollection, setStartingCollection] = useState(false);
  const [sort, setSort] = useState("latest");
  const [pagination, setPagination] = useState({ total: 0, pages: 1 });
  const selectedCollection =
    collections.find((c) =>
      collectionId ? c.id === collectionId : c.year === viewYear,
    ) ?? null;
  const scopeLabel = viewYear
    ? `${viewYear} enquiries`
    : selectedCollection
      ? `${selectedCollection.label} enquiries`
      : "All enquiries";
  const [view, setView] = useState<View>("leads"),
    [q, setQ] = useState(""),
    [status, setStatus] = useState("All leads"),
    [page, setPage] = useState(1);
  const [leads, setLeads] = useState<Lead[]>([]),
    [counts, setCounts] = useState<Record<string, number>>({
      total: 0,
      open_count: 0,
      due: 0,
      won: 0,
    });
  const [loading, setLoading] = useState(false),
    [columns, setColumns] = useState<string[]>(() => {
      try {
        const saved = JSON.parse(
          localStorage.getItem("lead-columns") || "null",
        );
        return Array.isArray(saved) &&
          saved.length &&
          saved.every((k) => k in tableFields && k !== "enquiry_time")
          ? saved
          : defaultColumns;
      } catch {
        return defaultColumns;
      }
    });
  const [columnMenu, setColumnMenu] = useState(false),
    [widths, setWidths] = useState<Record<string, number>>({
      customer_name: 165,
      lead_id: 72,
      enquiry_date: 100,
      contact_no: 110,
      model: 85,
      responded: 125,
      relevance: 85,
      status: 112,
      follow_up_date: 112,
      voice_of_customer: 250,
      remark: 250,
    });
  const [detail, setDetail] = useState<Detail | null>(null),
    [creating, setCreating] = useState(false),
    [card, setCard] = useState<Detail | null>(null),
    [refresh, setRefresh] = useState(0);
  const [job, setJob] = useState<Job>({
      running: false,
      result: null,
      error: "",
      finished_at: "",
    }),
    [reminders, setReminders] = useState<Reminder[]>([]);
  const [through, setThrough] = useState(localToday()),
    [reportBusy, setReportBusy] = useState(false),
    [notificationTick, setNotificationTick] = useState(0);
  const sequence = useRef(0),
    notified = useRef(new Set<number>()),
    lastFinished = useRef<string | null>(null);
  const touch = () => setRefresh((n) => n + 1);
  useEffect(() => {
    initialize()
      .then(() => api<Preferences>("/preferences"))
      .then((prefs) => {
        setPreferences(prefs);
        setViewYear(prefs.resolved_year);
        setReady(true);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!ready) return;
    api<Collection[]>("/collections")
      .then((data) => {
        setCollections(data);
        setCollectionId((id) => (data.some((c) => c.id === id) ? id : null));
      })
      .catch((e) => setError(e.message));
  }, [ready, refresh]);
  useEffect(() => {
    localStorage.setItem("lead-columns", JSON.stringify(columns));
  }, [columns]);
  useEffect(() => {
    if (!ready) return;
    const id = ++sequence.current;
    const timer = setTimeout(
      () => {
        setLoading(true);
        api<{
          leads: Lead[];
          total: number;
          pages: number;
          page: number;
          counts: Record<string, number>;
        }>(
          `/leads?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}&page=${page}&sort=${sort}${scopeQuery}`,
        )
          .then((data) => {
            if (id !== sequence.current) return;
            setLeads(data.leads);
            setPagination({ total: data.total, pages: data.pages });
            setPage(data.page);
            setCounts(data.counts);
          })
          .catch((e) => {
            if (id === sequence.current) setError(e.message);
          })
          .finally(() => {
            if (id === sequence.current) setLoading(false);
          });
      },
      q ? 220 : 0,
    );
    return () => clearTimeout(timer);
  }, [ready, q, status, page, refresh, sort, collectionId, viewYear]);
  useEffect(() => {
    if (!ready) return;
    api<Reminder[]>("/reminders")
      .then(setReminders)
      .catch((e) => setError(e.message));
  }, [ready, refresh, notificationTick]);
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    api<ReplyRequest[]>("/reply-requests")
      .then((requests) => {
        if (cancelled) return;
        const ids = new Set(requests.map((r) => r.id));
        if (
          previousRequests.current &&
          requests.some((r) => !previousRequests.current!.has(r.id))
        ) {
          setNotice(
            "New reply received. Open Reply requests to review and update the enquiry.",
          );
        }
        previousRequests.current = ids;
        setReplyRequests(requests);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [ready, refresh, notificationTick]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(timer);
  }, [notice]);
  useEffect(() => {
    if (!ready) return;
    const poll = () =>
      api<Job>("/sync")
        .then((data) => {
          setJob(data);
          if (data.finished_at && data.finished_at !== lastFinished.current) {
            const initialPoll = lastFinished.current === null;
            lastFinished.current = data.finished_at;
            if (data.collection && !initialPoll && !data.automatic) {
              setCollectionId(data.collection.year ? null : data.collection.id);
              setViewYear(data.collection.year);
              setPage(1);
              setQ("");
              setStatus("All leads");
              setSort("latest");
              setView("leads");
            }
            if (!data.automatic && !initialPoll) setResultsOpen(true);
            touch();
          } else if (lastFinished.current === null) {
            lastFinished.current = data.finished_at;
          }
        })
        .catch((e) => setError(e.message));
    poll();
    const timer = setInterval(poll, 1800);
    return () => clearInterval(timer);
  }, [ready]);
  useEffect(() => {
    const timer = setInterval(() => setNotificationTick((n) => n + 1), 30000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!("Notification" in window) || Notification.permission !== "granted")
      return;
    for (const reminder of reminders) {
      if (
        !reminder.completed_at &&
        new Date(reminder.due_at).getTime() <= Date.now() &&
        !notified.current.has(reminder.id)
      ) {
        notified.current.add(reminder.id);
        new Notification(`Follow up: ${reminder.customer_name}`, {
          body: reminder.note || "Your scheduled follow-up is due.",
        });
      }
    }
  }, [reminders, notificationTick]);
  async function openLead(id: number) {
    try {
      setDetail(await api<Detail>(`/leads/${id}`));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function collect(request: CollectionRequest) {
    lastFinished.current = "";
    setStartingCollection(true);
    setError("");
    try {
      setJob(await api<Job>("/sync", "POST", request));
      setNotice("");
      setCollectionDialog(false);
    } catch (e) {
      setError((e as Error).message);
      throw e;
    } finally {
      setStartingCollection(false);
    }
  }
  function chooseCollection(id: number | null, year: number | null = null) {
    setCollectionId(id);
    setViewYear(year);
    setPage(1);
    setQ("");
    setStatus("All leads");
    setSort("latest");
    setView("leads");
  }
  async function report() {
    setReportBusy(true);
    setError("");
    try {
      await downloadReport(through, scopeQuery);
      setNotice("Your Excel report is ready.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReportBusy(false);
    }
  }
  const due = reminders.filter(
    (r) => !r.completed_at && new Date(r.due_at).getTime() <= Date.now(),
  );
  const navigate = (next: View) => {
    setView(next);
    setError("");
    setNotice("");
  };
  const resize = (event: React.PointerEvent, key: string) => {
    event.preventDefault();
    const start = event.clientX;
    const width =
      event.currentTarget.parentElement!.getBoundingClientRect().width;
    const move = (e: PointerEvent) =>
      setWidths((w) => ({
        ...w,
        [key]: Math.max(90, Math.min(600, width + e.clientX - start)),
      }));
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  };
  return (
    <div className={"app " + (expanded && view === "leads" ? "expanded" : "")}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-symbol">m</span>
          <div>
            muneer<span>LEAD WORKSPACE</span>
          </div>
        </div>
        <div className="nav-heading">WORKSPACE</div>
        {(
          [
            ["leads", "Enquiries", List],
            ["replies", "Reply requests", Mail],
            ["followups", "Follow-ups", Bell],
            ["reports", "Reports", FileSpreadsheet],
            ["settings", "Settings", SettingsIcon],
          ] as const
        ).map(([key, title, Icon]) => (
          <button
            key={key}
            className={"nav " + (view === key ? "active" : "")}
            onClick={() => navigate(key)}
          >
            <Icon size={17} />
            {title}
            {key === "followups" && due.length > 0 && <b>{due.length}</b>}
            {key === "replies" && replyRequests.length > 0 && (
              <b>{replyRequests.length}</b>
            )}
          </button>
        ))}
        <div className="sidebar-bottom">
          <ShieldCheck size={17} />
          <span>
            On this computer<span>Saved locally · no cloud account</span>
          </span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>Muneer Heavy Earthmoving Equipment</span>
          <div>
            {(job.result || job.error) && (
              <button
                className="results-button"
                onClick={() => setResultsOpen(true)}
              >
                Collection results
                {job.error || job.result?.errors.length || job.result?.unparsed
                  ? " · needs attention"
                  : ""}
              </button>
            )}
            <span className="local-dot" />
            Local workspace
            <button
              className="icon"
              aria-label="Refresh workspace"
              onClick={touch}
            >
              <RefreshCw size={16} />
            </button>
          </div>
        </header>
        <div className={"content " + (view === "leads" ? "leads-content" : "")}>
          <div className="page-heading">
            <div>
              <span className="eyebrow">SALES WORKSPACE</span>
              <h1>
                {view === "leads"
                  ? scopeLabel
                  : view === "replies"
                    ? "Replies needing your update"
                    : view === "followups"
                      ? "Keep the conversation moving"
                      : view === "reports"
                        ? "Your master, ready to send"
                        : "Connect your Thunderbird"}
              </h1>
              <p>
                {view === "leads"
                  ? "Collect enquiries. Review the details. Make the next move."
                  : view === "replies"
                    ? "Incoming mail for your enquiries, including saved previous years."
                    : view === "followups"
                      ? "Upcoming conversations and overdue follow-ups."
                      : view === "reports"
                        ? "Download the complete lead history through your chosen date."
                        : "Read downloaded mail directly from the folders on this PC."}
              </p>
            </div>
            <div className="actions">
              {view === "leads" && (
                <button onClick={() => setCreating(true)}>
                  <Plus size={16} />
                  Add lead
                </button>
              )}
              <button
                className="primary"
                disabled={!ready || job.running}
                onClick={() => {
                  setRescanCollection(false);
                  setCollectionDialog(true);
                }}
              >
                {job.running ? (
                  <LoaderCircle className="spin" size={16} />
                ) : (
                  <RefreshCw size={16} />
                )}{" "}
                {job.running ? "Collecting…" : "Collect from mail"}
              </button>
            </div>
          </div>
          {view === "leads" && (
            <div className="collection-bar">
              <span>Enquiry year</span>
              {[
                ...new Set([
                  preferences.resolved_year,
                  new Date().getFullYear(),
                  ...collections.filter((c) => c.year).map((c) => c.year!),
                ]),
              ]
                .sort((a, b) => b - a)
                .map((year) => (
                  <button
                    key={year}
                    className={viewYear === year ? "selected" : ""}
                    onClick={() => chooseCollection(null, year)}
                  >
                    {year}
                    {year === preferences.resolved_year && (
                      <small>default</small>
                    )}
                  </button>
                ))}
              <select
                aria-label="View enquiry year"
                value={viewYear ?? ""}
                onChange={(e) => chooseCollection(null, Number(e.target.value))}
              >
                <option value="" disabled>
                  Choose year
                </option>
                {Array.from(
                  { length: new Date().getFullYear() - 1899 },
                  (_, i) => new Date().getFullYear() - i,
                ).map((year) => (
                  <option key={year}>{year}</option>
                ))}
              </select>
              {collections
                .filter((c) => !c.year)
                .map((c) => (
                  <button
                    key={c.id}
                    className={collectionId === c.id ? "selected" : ""}
                    onClick={() => chooseCollection(c.id)}
                  >
                    {c.label} <small>{c.total}</small>
                  </button>
                ))}
              <button
                className={!collectionId && !viewYear ? "selected" : ""}
                onClick={() => chooseCollection(null)}
              >
                All years
              </button>
              <button
                className="expand-button"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? <Minimize2 size={15} /> : <Maximize2 size={15} />}{" "}
                {expanded ? "Exit expanded view" : "Expand enquiries"}
              </button>
              {expanded && (
                <button
                  onClick={() => {
                    setExpanded(false);
                    navigate("replies");
                  }}
                >
                  Replies ({replyRequests.length})
                </button>
              )}
            </div>
          )}
          {error && (
            <div role="alert" className="banner error workspace-toast">
              <span>{error}</span>
              <button
                className="icon"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="banner success workspace-toast">
              {notice}
            </div>
          )}
          {!ready && !error && (
            <div className="empty">Connecting to your local workspace…</div>
          )}
          {view === "leads" && (
            <>
              <div className="summary-strip">
                <span>
                  <b>{counts.total.toLocaleString()}</b>Total leads
                </span>
                <span>
                  <b>{counts.open_count.toLocaleString()}</b>Open
                </span>
                <span>
                  <b>{counts.due.toLocaleString()}</b>Follow-ups due
                </span>
                <span>
                  <b>{counts.won.toLocaleString()}</b>Won
                </span>
                <div className="summary-note">
                  Click a customer to view and edit their full details
                </div>
              </div>
              <section className="table-panel">
                <div className="table-tools">
                  <div className="search">
                    <Search size={16} />
                    <input
                      aria-label="Search leads"
                      value={q}
                      placeholder="Search name, Call ID, phone, model, notes…"
                      onChange={(e) => {
                        setQ(e.target.value);
                        setPage(1);
                      }}
                    />
                    {q && (
                      <button
                        className="icon"
                        aria-label="Clear search"
                        onClick={() => {
                          setQ("");
                          setPage(1);
                        }}
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>
                  <Select
                    label="Filter leads"
                    value={status}
                    choices={[
                      "All leads",
                      "Open leads",
                      "Follow-ups due",
                      "Upcoming follow-ups",
                      ...statuses,
                    ]}
                    onChange={(s) => {
                      setStatus(s);
                      setPage(1);
                    }}
                  />
                  <Select
                    label="Sort leads"
                    value={sort}
                    choices={[
                      "latest",
                      "oldest",
                      "name_asc",
                      "name_desc",
                      "call_id_asc",
                      "call_id_desc",
                    ]}
                    onChange={(s) => {
                      setSort(s);
                      setPage(1);
                    }}
                  />
                  <div className="columns-wrap">
                    <button onClick={() => setColumnMenu(!columnMenu)}>
                      <Columns3 size={16} />
                      Columns
                    </button>
                    {columnMenu && (
                      <div className="column-menu">
                        <div className="menu-heading">
                          Show in your table
                          <button
                            className="icon"
                            aria-label="Close column menu"
                            onClick={() => setColumnMenu(false)}
                          >
                            <X size={15} />
                          </button>
                        </div>
                        {Object.entries(tableFields)
                          .filter(([key]) => key !== "enquiry_time")
                          .map(([key, name]) => (
                            <label key={key}>
                              <input
                                type="checkbox"
                                checked={columns.includes(key)}
                                disabled={
                                  columns.length === 1 && columns.includes(key)
                                }
                                onChange={(e) =>
                                  setColumns((c) =>
                                    e.target.checked
                                      ? [...c, key]
                                      : c.filter((k) => k !== key),
                                  )
                                }
                              />
                              {name}
                            </label>
                          ))}
                        <button onClick={() => setColumns(defaultColumns)}>
                          Reset columns
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <div className="table-scroll" aria-busy={loading}>
                  <table>
                    <colgroup>
                      {columns.map((key) => (
                        <col key={key} style={{ width: widths[key] || 145 }} />
                      ))}
                      <col style={{ width: 80 }} />
                    </colgroup>
                    <thead>
                      <tr>
                        {columns.map((key) => (
                          <th
                            key={key}
                            className={
                              key === "customer_name" ? "pinned-customer" : ""
                            }
                          >
                            {tableFields[key]}
                            <span
                              className="resize"
                              onPointerDown={(e) => resize(e, key)}
                            />
                          </th>
                        ))}
                        <th className="row-actions">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {leads.map((lead) => (
                        <tr key={lead.id}>
                          {columns.map((key) => (
                            <td
                              key={key}
                              className={
                                key === "customer_name" ? "pinned-customer" : ""
                              }
                              title={display(
                                key === "remark"
                                  ? lead.remark_preview
                                  : lead[key as keyof Lead],
                              )}
                            >
                              {key === "customer_name" ? (
                                <button
                                  className="customer"
                                  onClick={() => openLead(lead.id)}
                                >
                                  {display(lead.customer_name)}
                                </button>
                              ) : key === "status" ? (
                                <span
                                  className={
                                    "badge " +
                                    lead.status
                                      .toLowerCase()
                                      .replaceAll(" ", "-")
                                  }
                                >
                                  {lead.status}
                                </span>
                              ) : key === "remark" ? (
                                display(lead.remark_preview || lead.remark)
                              ) : key === "updated_at" ? (
                                time(lead.updated_at)
                              ) : (
                                display(lead[key as keyof Lead])
                              )}
                            </td>
                          ))}
                          <td className="row-actions">
                            <button
                              className="icon"
                              aria-label={`Edit ${lead.customer_name}`}
                              onClick={() => openLead(lead.id)}
                            >
                              <Pencil size={15} />
                            </button>
                            <button
                              className="icon"
                              aria-label={`Create card for ${lead.customer_name}`}
                              onClick={async () => {
                                try {
                                  setCard(
                                    await api<Detail>(`/leads/${lead.id}`),
                                  );
                                } catch (e) {
                                  setError((e as Error).message);
                                }
                              }}
                            >
                              <Image size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!leads.length && (
                    <div className="empty">
                      <List size={32} />
                      <h3>
                        {q || status !== "All leads"
                          ? "No matching leads"
                          : "Ready for your first enquiry"}
                      </h3>
                      <p>
                        {q
                          ? "Try another name, phone number or note."
                          : "Connect your Inbox in Settings, then collect from mail."}
                      </p>
                      {!q && (
                        <button onClick={() => navigate("settings")}>
                          Open email settings
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <footer className="table-footer">
                  <span>
                    {loading
                      ? "Loading…"
                      : `${pagination.total ? (page - 1) * 25 + 1 : 0}–${pagination.total ? (page - 1) * 25 + leads.length : 0} of ${pagination.total.toLocaleString()} leads · Page ${page} of ${pagination.pages}`}
                  </span>
                  <div>
                    <button
                      aria-label="Previous page"
                      disabled={page === 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      <ChevronLeft size={16} />
                    </button>
                    <label className="page-jump">
                      Go to page
                      <input
                        aria-label="Go to page"
                        type="number"
                        min={1}
                        max={pagination.pages}
                        value={page}
                        onChange={(e) => {
                          const next = Number(e.target.value);
                          if (
                            Number.isInteger(next) &&
                            next >= 1 &&
                            next <= pagination.pages
                          )
                            setPage(next);
                        }}
                      />
                    </label>
                    <button
                      aria-label="Next page"
                      disabled={page >= pagination.pages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      <ChevronRight size={16} />
                    </button>
                  </div>
                </footer>
              </section>
            </>
          )}
          {view === "replies" && (
            <section className="reply-panel">
              {!replyRequests.length && (
                <div className="empty">
                  <Mail size={32} />
                  <h3>No replies awaiting review</h3>
                  <p>
                    New matched incoming replies appear here after a mailbox
                    check.
                  </p>
                </div>
              )}
              {replyRequests.map((request) => (
                <article className="reply-request" key={request.id}>
                  <header>
                    <div>
                      <strong>
                        Request received · {request.customer_name}
                      </strong>
                      <small>
                        Call ID {request.call_id || "—"} ·{" "}
                        {request.enquiry_date} · {request.sender} ·{" "}
                        {time(request.occurred_at)}
                      </small>
                    </div>
                    <span className="badge">Needs update</span>
                  </header>
                  <p>{request.body}</p>
                  <div className="actions">
                    <button
                      className="primary"
                      onClick={() => openLead(request.lead_id)}
                    >
                      Open enquiry / update
                    </button>
                    <button
                      onClick={async () => {
                        try {
                          await api(
                            `/reply-requests/${request.id}/review`,
                            "POST",
                          );
                          touch();
                          setNotice("Reply marked reviewed.");
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }}
                    >
                      Mark reviewed
                    </button>
                  </div>
                </article>
              ))}
            </section>
          )}
          {view === "followups" && (
            <Followups
              reminders={reminders}
              open={openLead}
              refreshed={touch}
              error={setError}
            />
          )}
          {view === "reports" && (
            <section className="report-panel">
              <div className="report-icon">
                <FileSpreadsheet size={34} />
              </div>
              <h2>IndiaMART lead master</h2>
              <p>
                {selectedCollection
                  ? `Leads in ${selectedCollection.label}, from ${selectedCollection.from_date} through the cutoff date.`
                  : viewYear
                    ? `Enquiries from ${viewYear}, through the cutoff date.`
                    : "Every saved lead from the beginning through the cutoff date."}{" "}
                Includes your manual remarks and outgoing email updates.
              </p>
              <label className="field">
                Include enquiries through
                <input
                  type="date"
                  value={through}
                  onChange={(e) => setThrough(e.target.value)}
                />
              </label>
              <button
                className="primary"
                disabled={reportBusy || !through}
                onClick={report}
              >
                {reportBusy ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Download size={16} />
                )}
                Download Excel report
              </button>
              <div className="report-info">
                <Check size={16} />
                17 columns matching your supplied workbook
                <br />
                <Check size={16} />
                Customer response, relevance, Hot / Cold / Warm Deals and
                Win/Lost fields
                <br />
                <Check size={16} />
                Your outgoing updates and manual Remark, without greetings or
                signatures
              </div>
              <small>
                The report is ready to attach to your weekly email. Use a
                database backup to preserve reminders and undo history.
              </small>
            </section>
          )}
          {view === "settings" && ready && (
            <SettingsPage
              preferences={preferences}
              onPreferences={(prefs) => {
                setPreferences(prefs);
                chooseCollection(null, prefs.resolved_year);
                setView("settings");
                touch();
              }}
              onNotice={setNotice}
              onError={setError}
              rescan={() => {
                setRescanCollection(true);
                setCollectionDialog(true);
              }}
              busy={job.running}
            />
          )}
        </div>
      </main>
      {resultsOpen && (job.result || job.error) && (
        <Modal title="Collection results" onClose={() => setResultsOpen(false)}>
          <div
            className={
              "collection-result " +
              (job.error || job.result?.errors.length ? "issue" : "")
            }
          >
            <div>
              <strong>
                {job.error
                  ? "Collection needs attention"
                  : `${job.result!.new_leads} new leads · ${job.result!.updated_leads} changed leads · ${job.result!.remarks_added} mail updates`}
              </strong>
              <span>
                {job.error ||
                  job.result?.errors.join(" · ") ||
                  ` ${job.result!.unparsed} unparsed · ${job.result!.out_of_range} outside range · ${job.result!.pending} unmatched replies`}
              </span>
            </div>
            <button
              className="icon collection-dismiss"
              aria-label="Dismiss collection result"
              onClick={() => setResultsOpen(false)}
            >
              <X size={14} />
            </button>
            {!!job.result?.issues.length && (
              <details>
                <summary>
                  Review unparsed enquiries ({job.result.issues.length})
                </summary>
                {job.result.issues.map((issue, i) => (
                  <p key={i}>
                    <b>
                      {issue.folder} · {issue.subject}
                    </b>
                    <br />
                    {issue.reason}
                  </p>
                ))}
                <small>
                  After correcting the template/settings, use Rescan in Settings
                  to retry them.
                </small>
              </details>
            )}
          </div>
        </Modal>
      )}

      {collectionDialog && (
        <CollectionDialog
          selected={selectedCollection}
          preferredYear={viewYear ?? preferences.resolved_year}
          rescan={rescanCollection}
          busy={startingCollection}
          start={collect}
          onClose={() => !startingCollection && setCollectionDialog(false)}
        />
      )}
      {(detail || creating) && (
        <LeadDialog
          detail={detail}
          onClose={() => {
            setDetail(null);
            setCreating(false);
          }}
          onSaved={(d) => {
            setDetail(d);
            setCreating(false);
            touch();
          }}
          onCard={setCard}
        />
      )}
      {card && <CardDialog detail={card} onClose={() => setCard(null)} />}
    </div>
  );
}

function CollectionDialog({
  preferredYear,
  selected,
  rescan,
  busy,
  start,
  onClose,
}: {
  preferredYear: number;
  selected: Collection | null;
  rescan: boolean;
  busy: boolean;
  start: (request: CollectionRequest) => Promise<void>;
  onClose: () => void;
}) {
  const currentYear = new Date().getFullYear();
  const [mode, setMode] = useState(selected ? "update" : "year");
  const [year, setYear] = useState(selected?.year ?? preferredYear);
  const [from, setFrom] = useState(
    selected?.from_date ?? `${preferredYear}-01-01`,
  );
  const [to, setTo] = useState(selected?.to_date ?? localToday());
  const [error, setError] = useState("");
  const yearEnd = (y: number) =>
    `${y}-12-31` < localToday() ? `${y}-12-31` : localToday();
  const range =
    mode === "update" && selected
      ? {
          from: selected.from_date,
          to: selected.year ? yearEnd(selected.year) : selected.to_date,
        }
      : mode === "year"
        ? { from: `${year}-01-01`, to: yearEnd(year) }
        : { from, to };
  async function submit() {
    setError("");
    const request: CollectionRequest =
      mode === "update" && selected
        ? { collection_id: selected.id, rescan }
        : mode === "year"
          ? { year, rescan }
          : { from_date: from, to_date: to, rescan };
    try {
      await start(request);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <Modal
      title={rescan ? "Rescan a collection" : "Collect leads from mail"}
      onClose={onClose}
    >
      <div className="modal-body collection-form">
        <p>
          Choose the enquiry dates to collect. Saved leads stay on this PC;
          opening a saved collection does not scan mail.
        </p>
        <label className="field">
          Collection choice
          <select
            aria-label="Collection choice"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            {selected && (
              <option value="update">Update {selected.label}</option>
            )}
            <option value="year">Choose a year</option>
            <option value="custom">Custom date range</option>
          </select>
        </label>
        {mode === "year" && (
          <label className="field">
            Year
            <input
              aria-label="Collection year"
              type="number"
              min={1900}
              max={currentYear}
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </label>
        )}
        {mode === "custom" && (
          <div className="form-grid">
            <label className="field">
              From
              <input
                aria-label="Collect from date"
                type="date"
                max={localToday()}
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              />
            </label>
            <label className="field">
              Through
              <input
                aria-label="Collect through date"
                type="date"
                min={from}
                max={localToday()}
                value={to}
                onChange={(e) => setTo(e.target.value)}
              />
            </label>
          </div>
        )}
        <div className="range-preview">
          <strong>
            {range.from} → {range.to}
          </strong>
          <small>
            Enquiry dates, inclusive. Outgoing updates appear in Remark.
            Incoming replies create review requests, even if they arrived after
            these enquiry dates.
          </small>
        </div>
        {mode === "update" && (
          <p className="muted">
            Existing leads are kept. New enquiries and changed mail are
            collected; unchanged messages are skipped.
          </p>
        )}
        {rescan && (
          <p className="muted">
            Rescan checks the selected range from the beginning and retries
            unparsed enquiries. Known mail is deduplicated.
          </p>
        )}
        {error && (
          <div role="alert" className="banner error">
            {error}
          </div>
        )}
      </div>
      <footer className="modal-footer">
        <div className="actions">
          <button disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            disabled={
              busy ||
              !range.from ||
              !range.to ||
              range.from > range.to ||
              range.to > localToday() ||
              (mode === "year" &&
                (!Number.isInteger(year) || year < 1900 || year > currentYear))
            }
            onClick={submit}
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <RefreshCw size={16} />
            )}
            {busy
              ? "Starting…"
              : rescan
                ? "Rescan selected range"
                : mode === "update"
                  ? "Update saved collection"
                  : "Collect selected range"}
          </button>
        </div>
      </footer>
    </Modal>
  );
}

function Followups({
  reminders,
  open,
  refreshed,
  error,
}: {
  reminders: Reminder[];
  open: (id: number) => void;
  refreshed: () => void;
  error: (s: string) => void;
}) {
  const [completed, setCompleted] = useState(false),
    [filter, setFilter] = useState("All scheduled");
  const list = reminders
    .filter((r) => (completed ? !!r.completed_at : !r.completed_at))
    .filter(
      (r) => filter !== "Overdue" || new Date(r.due_at).getTime() <= Date.now(),
    );
  async function done(id: number) {
    try {
      await api(`/reminders/${id}/complete`, "POST");
      refreshed();
    } catch (e) {
      error((e as Error).message);
    }
  }
  return (
    <section className="table-panel">
      <div className="table-tools">
        <strong>Follow-up reminders</strong>
        <Select
          value={filter}
          choices={["All scheduled", "Overdue"]}
          label="Reminder filter"
          onChange={setFilter}
        />
        <label className="checkbox">
          <input
            type="checkbox"
            checked={completed}
            onChange={(e) => setCompleted(e.target.checked)}
          />
          Completed
        </label>
        <button
          onClick={async () => {
            if ("Notification" in window) {
              const permission = await Notification.requestPermission();
              if (permission !== "granted")
                error(
                  "Browser notifications were not enabled. Due reminders remain visible here.",
                );
              else refreshed();
            } else
              error(
                "Browser notifications are unavailable; reminders remain visible here.",
              );
          }}
        >
          <Bell size={16} />
          Enable notifications
        </button>
      </div>
      <div className="reminder-list">
        {list.map((r) => (
          <div className="reminder-row" key={r.id}>
            <div
              className={
                "reminder-date " +
                (!r.completed_at && new Date(r.due_at).getTime() <= Date.now()
                  ? "overdue"
                  : "")
              }
            >
              <Bell size={18} />
              <span>
                {time(r.due_at)}
                <small>
                  {r.completed_at
                    ? "Completed"
                    : new Date(r.due_at).getTime() <= Date.now()
                      ? "Due now"
                      : "Upcoming"}
                </small>
              </span>
            </div>
            <div>
              <button className="customer" onClick={() => open(r.lead_id)}>
                {r.customer_name}
              </button>
              <p>{r.note || "Follow up with this customer"}</p>
              <small>
                {r.contact_no} · {r.status}
              </small>
            </div>
            {!r.completed_at && (
              <button onClick={() => done(r.id)}>
                <Check size={16} />
                Mark done
              </button>
            )}
          </div>
        ))}
        {!list.length && (
          <div className="empty">
            <Bell size={32} />
            <h3>No reminders here yet</h3>
            <p>Open a lead and schedule its next conversation.</p>
          </div>
        )}
      </div>
      <div className="panel-note">
        Reminders use your PC's clock. Keep this browser tab open for enabled
        browser notifications. The leads table also filters by next follow-up
        date.
      </div>
    </section>
  );
}

function LeadDialog({
  detail,
  onClose,
  onSaved,
  onCard,
}: {
  detail: Detail | null;
  onClose: () => void;
  onSaved: (d: Detail) => void;
  onCard: (d: Detail) => void;
}) {
  const [tab, setTab] = useState("Details"),
    [values, setValues] = useState<Record<string, string | number | null>>({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [note, setNote] = useState(""),
    [due, setDue] = useState(""),
    [reminderNote, setReminderNote] = useState("");
  useEffect(() => {
    setValues(
      detail
        ? Object.fromEntries(
            Object.keys(fields)
              .filter((k) => k !== "enquiry_time")
              .map((k) => [k, detail.lead[k as keyof Lead] ?? ""]),
          )
        : {
            customer_name: "",
            lead_id: "",
            enquiry_date: localToday(),
            contact_no: "",
            email_id: "",
            alt_no: "",
            model: "",
            quantity: 1,
            city: "",
            dealer: "Muneer Heavy Earthmoving Equipment",
            voice_of_customer: "",
            category: "",
            remark: "",
            responded: "",
            relevance: "",
            deal_temperature: "",
            status: "New",
            follow_up_date: "",
          },
    );
  }, [detail]);
  const hasLeadChanges = detail
    ? Object.entries(values).some(
        ([key, value]) =>
          String(value ?? "") !== String(detail.lead[key as keyof Lead] ?? ""),
      )
    : Boolean(values.customer_name || values.contact_no || values.remark);
  function requestClose() {
    if (busy) return;
    if (
      (hasLeadChanges || note.trim() || due || reminderNote.trim()) &&
      !confirm("Discard the unsaved details or notes in this window?")
    )
      return;
    onClose();
  }
  async function action(
    operation: () => Promise<Detail>,
    savingDetails = false,
  ) {
    if (
      !savingDetails &&
      hasLeadChanges &&
      !confirm(
        "Discard the unsaved lead details and continue? Save the lead first to keep them.",
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      onSaved(await operation());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function save() {
    const changed = detail
      ? Object.fromEntries(
          Object.entries(values).filter(
            ([k, v]) =>
              String(v ?? "") !== String(detail.lead[k as keyof Lead] ?? ""),
          ),
        )
      : values;
    return action(
      () =>
        api<Detail>(
          detail ? `/leads/${detail.lead.id}` : "/leads",
          detail ? "PATCH" : "POST",
          { revision: detail?.lead.revision || 0, values: changed },
        ),
      true,
    );
  }
  const input = (key: string) => {
    const options =
      key === "status"
        ? statuses
        : key === "responded"
          ? responses
          : key === "relevance"
            ? ["", "Relevant", "Irrelevant"]
            : ["", "Hot", "Warm", "Cold"];
    return (
      <label
        className={
          "field " +
          (["voice_of_customer", "remark", "dealer"].includes(key)
            ? "span-two"
            : "")
        }
        key={key}
      >
        {fields[key]}
        {["status", "responded", "relevance", "deal_temperature"].includes(
          key,
        ) ? (
          <Select
            value={String(values[key] || "")}
            choices={options}
            label={fields[key]}
            onChange={(v) => setValues((s) => ({ ...s, [key]: v }))}
          />
        ) : ["voice_of_customer", "remark"].includes(key) ? (
          <textarea
            value={String(values[key] || "")}
            rows={key === "remark" ? 4 : 3}
            onChange={(e) =>
              setValues((s) => ({ ...s, [key]: e.target.value }))
            }
          />
        ) : (
          <input
            aria-label={fields[key]}
            type={
              key.endsWith("date")
                ? "date"
                : key === "quantity"
                  ? "number"
                  : "text"
            }
            min={key === "quantity" ? 1 : undefined}
            value={values[key] ?? ""}
            onChange={(e) =>
              setValues((s) => ({
                ...s,
                [key]:
                  key === "quantity" ? Number(e.target.value) : e.target.value,
              }))
            }
          />
        )}
        {key === "category" && (
          <small>Category provided in the enquiry email.</small>
        )}
        {key === "deal_temperature" && (
          <small>
            Hot: buying soon · Warm: within 2 months · Cold: more than 2 to 6
            months.
          </small>
        )}
        {key === "remark" && (
          <small>
            Your editable remark. Cleaned outgoing replies appear below and are
            included in Excel. Incoming mail and call notes stay in Activity.
          </small>
        )}
      </label>
    );
  };
  return (
    <Modal
      wide
      title={detail ? detail.lead.customer_name : "Add a lead"}
      onClose={requestClose}
    >
      <div className="detail-meta">
        {detail ? (
          <>
            Call ID {detail.lead.lead_id || "—"} · Last updated{" "}
            {time(detail.lead.updated_at)}
            {detail.enquiry_time && <> · Email {time(detail.enquiry_time)}</>}
          </>
        ) : (
          "Enter the customer details and save to your master."
        )}
      </div>
      <div className="tabs">
        {["Details", "Activity", "Follow-ups", "Change history"].map((t) => (
          <button
            key={t}
            disabled={!detail && t !== "Details"}
            className={tab === t ? "selected" : ""}
            onClick={() => setTab(t)}
          >
            {t}
            {t === "Change history" && detail && (
              <span>{detail.history.length}/5</span>
            )}
          </button>
        ))}
      </div>
      {error && (
        <div role="alert" className="banner error">
          {error}
          {detail && (
            <button
              onClick={() =>
                action(() => api<Detail>(`/leads/${detail.lead.id}`))
              }
            >
              Reload lead
            </button>
          )}
        </div>
      )}
      <div className="modal-body">
        {tab === "Details" && (
          <>
            <div className="form-section">
              <h3>Customer & enquiry</h3>
              <div className="form-grid">
                {[
                  "customer_name",
                  "lead_id",
                  "enquiry_date",
                  "contact_no",
                  "email_id",
                  "alt_no",
                  "model",
                  "quantity",
                  "city",
                  "category",
                  "dealer",
                  "voice_of_customer",
                ].map(input)}
              </div>
            </div>
            <div className="form-section">
              <h3>Your sales updates</h3>
              <div className="form-grid">
                {[
                  "status",
                  "responded",
                  "relevance",
                  "deal_temperature",
                  "follow_up_date",
                  "remark",
                ].map(input)}
              </div>
            </div>
            {detail && detail.remark_text && (
              <section className="remark-history">
                <h3>Remark · outgoing updates</h3>
                <p>{detail.remark_text}</p>
              </section>
            )}
          </>
        )}
        {tab === "Activity" && detail && (
          <>
            <label className="field">
              Log a conversation
              <textarea
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Call notes, customer feedback or your next action…"
              />
            </label>
            <button
              disabled={busy || !note.trim()}
              onClick={() =>
                action(async () => {
                  const d = await api<Detail>(
                    `/leads/${detail.lead.id}/notes`,
                    "POST",
                    { body: note },
                  );
                  setNote("");
                  return d;
                })
              }
            >
              Save note
            </button>
            <div className="timeline">
              {detail.activities.map((a) => (
                <article key={a.id}>
                  <div>
                    <span className="event-dot" />
                    <b>{a.kind}</b>
                    <time>{time(a.occurred_at)}</time>
                  </div>
                  {a.sender && <small>{a.sender}</small>}
                  <p>{a.body}</p>
                </article>
              ))}
              {!detail.activities.length && (
                <p className="muted">No activity recorded yet.</p>
              )}
            </div>
          </>
        )}
        {tab === "Follow-ups" && detail && (
          <>
            <h3>Schedule the next conversation</h3>
            <div className="form-grid">
              <label className="field">
                Date & time
                <input
                  aria-label="Reminder date and time"
                  type="datetime-local"
                  value={due}
                  onChange={(e) => setDue(e.target.value)}
                />
              </label>
              <label className="field">
                Reminder note
                <input
                  aria-label="Reminder note"
                  value={reminderNote}
                  onChange={(e) => setReminderNote(e.target.value)}
                  placeholder="Call about the quotation"
                />
              </label>
            </div>
            <button
              className="primary"
              disabled={!due || busy}
              onClick={() =>
                action(async () => {
                  const d = await api<Detail>(
                    `/leads/${detail.lead.id}/reminders`,
                    "POST",
                    { due_at: due, note: reminderNote },
                  );
                  setDue("");
                  setReminderNote("");
                  return d;
                })
              }
            >
              <Plus size={16} />
              Schedule reminder
            </button>
            <div className="timeline">
              {detail.reminders.map((r) => (
                <article key={r.id}>
                  <b>{time(r.due_at)}</b>
                  <p>{r.note || "Follow up"}</p>
                  {r.completed_at ? (
                    <small>Completed</small>
                  ) : (
                    <button
                      disabled={busy}
                      onClick={() =>
                        action(async () => {
                          await api(`/reminders/${r.id}/complete`, "POST");
                          return api<Detail>(`/leads/${detail.lead.id}`);
                        })
                      }
                    >
                      <Check size={14} />
                      Mark done
                    </button>
                  )}
                </article>
              ))}
            </div>
          </>
        )}
        {tab === "Change history" && detail && (
          <>
            <div className="history-info">
              <HistoryIcon size={20} />
              <p>
                The last five saved edits are available to undo. Restoring a
                version saves your current details as another undo point.
              </p>
            </div>
            {detail.history.map((h) => (
              <article className="history-item" key={h.id}>
                <div>
                  <b>Before edit · {time(h.saved_at)}</b>
                  <button
                    disabled={busy}
                    onClick={() => {
                      if (
                        confirm(
                          "Restore these saved details? Your current details will be kept as an undo point.",
                        )
                      )
                        action(() =>
                          api<Detail>(
                            `/leads/${detail.lead.id}/history/${h.id}/restore`,
                            "POST",
                            { revision: detail.lead.revision },
                          ),
                        );
                    }}
                  >
                    Restore this version
                  </button>
                </div>
                <dl>
                  {h.changed_fields.map((k) => (
                    <div key={k}>
                      <dt>{fields[k] || k}</dt>
                      <dd>{display(h.snapshot[k])}</dd>
                    </div>
                  ))}
                </dl>
              </article>
            ))}
            {!detail.history.length && (
              <div className="empty">
                <HistoryIcon size={30} />
                <h3>No saved changes</h3>
                <p>Your next edit will create an undo point.</p>
              </div>
            )}
            {!!detail.history.length && (
              <div className="permanent">
                <p>
                  Happy with the current details? Keep them and remove the five
                  undo points.
                </p>
                <button
                  disabled={busy}
                  onClick={() => {
                    if (
                      confirm(
                        "Keep the current details and permanently clear this lead’s undo history?",
                      )
                    )
                      action(() =>
                        api<Detail>(
                          `/leads/${detail.lead.id}/history`,
                          "DELETE",
                          { revision: detail.lead.revision },
                        ),
                      );
                  }}
                >
                  <ShieldCheck size={16} />
                  Make permanent
                </button>
              </div>
            )}
          </>
        )}
      </div>
      <footer className="modal-footer">
        {detail && (
          <button onClick={() => onCard(detail)}>
            <Image size={16} />
            Create lead card
          </button>
        )}
        <div className="actions">
          <button disabled={busy} onClick={requestClose}>
            Close
          </button>
          {tab === "Details" && (
            <button
              className="primary"
              disabled={busy || !String(values.customer_name || "").trim()}
              onClick={save}
            >
              {busy ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Check size={16} />
              )}
              Save lead
            </button>
          )}
        </div>
      </footer>
    </Modal>
  );
}

function SettingsPage({
  preferences,
  onPreferences,
  onNotice,
  onError,
  rescan,
  busy,
}: {
  preferences: Preferences;
  onPreferences: (prefs: Preferences) => void;
  onNotice: (s: string) => void;
  onError: (s: string) => void;
  rescan: () => void;
  busy: boolean;
}) {
  const [data, setData] = useState<Settings>({
      mailbox_paths: ["", ""],
      sender_filter: "",
      my_email: "",
    }),
    [saving, setSaving] = useState(false);
  useEffect(() => {
    api<Settings>("/settings")
      .then(setData)
      .catch((e) => onError(e.message));
  }, []);
  const path = (index: number, value: string) =>
    setData((d) => {
      const paths = [d.mailbox_paths[0] || "", d.mailbox_paths[1] || ""];
      paths[index] = value;
      return { ...d, mailbox_paths: paths };
    });
  async function save() {
    setSaving(true);
    onError("");
    try {
      await api("/settings", "PUT", {
        mailbox_paths: data.mailbox_paths,
        sender_filter: data.sender_filter,
        my_email: data.my_email,
      });
      onNotice(
        "Email settings saved. Collect from mail to read your enquiries.",
      );
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="settings-layout">
      <section className="settings-panel">
        <h2>Mailbox connection</h2>
        <p>
          Thunderbird downloads the mail; this app reads the local mbox files.
        </p>
        <label className="field">
          Inbox file path
          <input
            value={data.mailbox_paths[0] || ""}
            onChange={(e) => path(0, e.target.value)}
            placeholder="C:\Users\…\Thunderbird\…\INBOX"
          />
          <small>
            Copy the full path, including INBOX. Leave off the .msf extension.
          </small>
        </label>
        <label className="field">
          Sent file path · optional
          <input
            value={data.mailbox_paths[1] || ""}
            onChange={(e) => path(1, e.target.value)}
            placeholder="C:\Users\…\Thunderbird\…\Sent"
          />
          <small>
            Add Sent to include your outgoing replies in the lead's activity.
          </small>
        </label>
        <label className="field">
          Enquiry sender addresses
          <input
            value={data.sender_filter}
            onChange={(e) =>
              setData((d) => ({ ...d, sender_filter: e.target.value }))
            }
            placeholder="leads@example.com"
          />
          <small>Exact email addresses, separated by commas.</small>
        </label>
        <label className="field">
          Your sales email address
          <input
            value={data.my_email}
            onChange={(e) =>
              setData((d) => ({ ...d, my_email: e.target.value }))
            }
            placeholder="sales@example.com"
          />
        </label>
        <button className="primary" disabled={saving || busy} onClick={save}>
          <Check size={16} />
          Save email settings
        </button>
      </section>
      <div>
        <PreferencePanel
          data={preferences}
          saved={onPreferences}
          notice={onNotice}
          error={onError}
        />
        <section className="help-panel">
          <h3>Find your mailbox files</h3>
          <ol>
            <li>
              In Thunderbird, open <b>Account Settings → Server Settings</b>.
            </li>
            <li>
              Copy the <b>Local directory</b> path, then add <b>\INBOX</b> or{" "}
              <b>\Sent</b>.
            </li>
            <li>
              Enable offline downloads under <b>Synchronization & Storage</b>.
            </li>
            <li>Use mbox storage. Maildir directories are not supported.</li>
          </ol>
          <p>
            Keep Thunderbird downloading mail. Automatic checks run every minute
            while the local server is running; you can disable them below.
          </p>
        </section>
        <section className="help-panel">
          <h3>Database & recovery</h3>
          <small className="path">{data.database_path}</small>
          <p>
            Backups are created before the first collection each day. Your
            manual edits are protected from source refreshes.
          </p>
          <div className="actions">
            <button
              disabled={busy}
              onClick={async () => {
                try {
                  const d = await api<{ path: string }>("/backup", "POST");
                  onNotice("Backup saved: " + d.path);
                } catch (e) {
                  onError((e as Error).message);
                }
              }}
            >
              <ShieldCheck size={15} />
              Back up database
            </button>
            <button disabled={busy} onClick={rescan}>
              <RefreshCw size={15} />
              Rescan folders
            </button>
          </div>
          <small>
            Rescan retries older enquiries after changing mailbox settings or
            improving extraction.
          </small>
        </section>
      </div>
    </div>
  );
}

function CardDialog({
  detail,
  onClose,
}: {
  detail: Detail;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState([
      "customer_name",
      "contact_no",
      "model",
      "responded",
      "enquiry_date",
      "enquiry_time",
    ]),
    [preview, setPreview] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    setPreview(renderCard(detail, selected).toDataURL("image/png"));
  }, [detail, selected]);
  async function download() {
    setBusy(true);
    try {
      const url = URL.createObjectURL(await cardBlob(detail, selected));
      const a = document.createElement("a");
      a.href = url;
      a.download = `Lead ${detail.lead.lead_id || detail.lead.id}.png`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function copy(whatsapp = false) {
    setError("");
    setNotice("");
    const popup = whatsapp
      ? window.open(
          "https://web.whatsapp.com/",
          "_blank",
          "noopener,noreferrer",
        )
      : null;
    setBusy(true);
    try {
      if (!navigator.clipboard?.write || typeof ClipboardItem === "undefined")
        throw new Error(
          "Image copy is unavailable in this browser. Download the card and attach it in WhatsApp.",
        );
      const blob = cardBlob(detail, selected);
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": blob }),
      ]);
      setNotice(
        whatsapp
          ? "Card copied. In WhatsApp, choose a chat, paste the image and send."
          : "Card image copied to the clipboard.",
      );
    } catch (e) {
      popup?.close();
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal wide title="Create a lead card" onClose={onClose}>
      {error && (
        <div role="alert" className="banner error">
          {error}
        </div>
      )}
      {notice && (
        <div role="status" className="banner success">
          {notice}
        </div>
      )}
      <div className="modal-body card-builder">
        <div>
          <h3>Choose what to share</h3>
          <p className="muted">Only selected details appear in the image.</p>
          {Object.entries(fields).map(([key, name]) => (
            <label key={key} className="checkbox">
              <input
                type="checkbox"
                checked={selected.includes(key)}
                onChange={(e) =>
                  setSelected((s) =>
                    e.target.checked ? [...s, key] : s.filter((k) => k !== key),
                  )
                }
              />
              {name}
            </label>
          ))}
        </div>
        <div className="card-preview">
          <span className="eyebrow">IMAGE PREVIEW</span>
          <img src={preview} alt="Preview of the selected lead details" />
        </div>
      </div>
      <footer className="modal-footer">
        <small>
          WhatsApp sends after you choose a chat and paste the image.
        </small>
        <div className="actions">
          <button disabled={busy || !selected.length} onClick={download}>
            <Download size={16} />
            Download PNG
          </button>
          <button disabled={busy || !selected.length} onClick={() => copy()}>
            Copy image
          </button>
          <button
            className="primary"
            disabled={busy || !selected.length}
            onClick={() => copy(true)}
          >
            Copy & WhatsApp
          </button>
        </div>
      </footer>
    </Modal>
  );
}

function PreferencePanel({
  data,
  saved,
  notice,
  error,
}: {
  data: Preferences;
  saved: (p: Preferences) => void;
  notice: (s: string) => void;
  error: (s: string) => void;
}) {
  const [choice, setChoice] = useState(data.default_enquiry_year);
  const [automatic, setAutomatic] = useState(data.auto_check_mail);
  const [busy, setBusy] = useState(false);
  const currentYear = new Date().getFullYear();
  return (
    <section className="help-panel preference-panel">
      <h3>Workspace preferences</h3>
      <label className="field">
        Default enquiry year
        <select
          aria-label="Default enquiry year"
          value={choice === "current" ? "current" : "fixed"}
          onChange={(e) =>
            setChoice(
              e.target.value === "current" ? "current" : String(currentYear),
            )
          }
        >
          <option value="current">
            Active year (automatically changes each January)
          </option>
          <option value="fixed">Choose a fixed year</option>
        </select>
      </label>
      {choice !== "current" && (
        <label className="field">
          Year
          <input
            aria-label="Fixed default year"
            type="number"
            min={1900}
            max={currentYear}
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
          />
        </label>
      )}
      <label className="preference-toggle">
        <input
          type="checkbox"
          checked={automatic}
          onChange={(e) => setAutomatic(e.target.checked)}
        />{" "}
        Check downloaded mail every minute
      </label>
      <p>
        Every launch opens your default year. Previous years and All years are
        available in Enquiries. Automatic checks monitor the default year and
        saved collections for incoming replies.
      </p>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            const prefs = await api<Preferences>("/preferences", "PUT", {
              default_enquiry_year: choice,
              auto_check_mail: automatic,
            });
            saved(prefs);
            notice("Workspace preferences saved.");
          } catch (e) {
            error((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        Save preferences
      </button>
    </section>
  );
}
