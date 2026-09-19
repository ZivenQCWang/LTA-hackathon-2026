import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  ClipboardList,
  Database,
  ExternalLink,
  LockKeyhole,
  MapPin,
  RefreshCw,
  Search,
} from "lucide-react";
import { Metric } from "../ui";
import {
  categories,
  categoryLabel,
  dateLabel,
  statusLabels,
} from "../public-app/constants";
import type { PublicReport } from "../public-app/types";
import {
  basicAuthorization,
  InboxError,
  requestInbox,
  type ReportInbox,
} from "./api";
import { ReportDetails } from "./ReportDetails";
import "./public-reports.css";

export default function PublicReportsWorkspace() {
  const [data, setData] = useState<ReportInbox | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);
  const [authorization, setAuthorization] = useState("");
  const [selected, setSelected] = useState<PublicReport | null>(null);
  const [updated, setUpdated] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ page: String(page), q: query });
    if (category) params.set("category", category);
    setLoading(true);
    setError("");
    requestInbox("?" + params, authorization, controller.signal)
      .then((response) => response.json())
      .then((result: ReportInbox) => {
        if (controller.signal.aborted) return;
        setData(result);
        setNeedsLogin(false);
        setUpdated(
          new Date().toLocaleTimeString("en-SG", {
            hour: "2-digit",
            minute: "2-digit",
          }),
        );
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        if (e instanceof InboxError && e.status === 401) {
          setNeedsLogin(true);
          setData(null);
          setSelected(null);
        }
        setError(
          e instanceof InboxError
            ? e.message
            : "Could not connect to report storage. Please try again.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [authorization, query, category, page, refresh]);

  useEffect(() => {
    if (needsLogin) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible")
        setRefresh((value) => value + 1);
    }, 30000);
    return () => window.clearInterval(timer);
  }, [needsLogin]);

  return (
    <div className="report-inbox">
      <section className="inbox-introduction">
        <div>
          <span className="overline">FROM YOUR COMMUNITY</span>
          <h2>Every report is a place to start.</h2>
          <p>
            Photos and observations submitted through PLiZ Public, ready for
            your team to review.
          </p>
        </div>
        <a
          className="button primary"
          href="/public/"
          target="_blank"
          rel="noreferrer"
        >
          Open public app <ExternalLink size={16} />
        </a>
      </section>
      {needsLogin ? (
        <section className="panel inbox-login">
          <LockKeyhole size={28} />
          <h3>Operator access</h3>
          <p>Sign in to view submitted reports and photos.</p>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const values = new FormData(event.currentTarget);
              setAuthorization(
                basicAuthorization(
                  String(values.get("username")),
                  String(values.get("password")),
                ),
              );
              setRefresh((value) => value + 1);
              event.currentTarget.reset();
            }}
          >
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                required
                maxLength={120}
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={200}
              />
            </label>
            {error && (
              <p className="error-text" role="alert">
                {error}
              </p>
            )}
            <button className="primary" disabled={loading}>
              {loading ? "Signing in…" : "View reports"}
              <ArrowRight size={16} />
            </button>
          </form>
        </section>
      ) : (
        <>
          {data && (
            <div className="metrics inbox-metrics">
              <Metric
                value={data.summary.total}
                label="Public reports"
                detail="All submissions"
              />
              <Metric
                value={data.summary.received}
                label="Received"
                detail="Ready for review"
              />
              <Metric
                value={data.summary.photos}
                label="Attached photos"
                detail="Across all reports"
              />
            </div>
          )}
          <section className="panel inbox-list-panel">
            <div className="section-heading">
              <div>
                <span className="overline">PUBLIC’S REPORT</span>
                <h2>Reports inbox</h2>
              </div>
              <button
                disabled={loading}
                onClick={() => setRefresh((value) => value + 1)}
              >
                <RefreshCw size={16} className={loading ? "inbox-spin" : ""} />
                Refresh reports
              </button>
            </div>
            <div className="inbox-tools">
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  setQuery(search.trim());
                  setPage(1);
                }}
              >
                <label className="sr-only" htmlFor="inbox-search">
                  Search reports
                </label>
                <Search size={18} />
                <input
                  id="inbox-search"
                  placeholder="Search location, details or reference"
                  maxLength={160}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
                <button type="submit">Search</button>
              </form>
              <label>
                <span className="sr-only">Issue category</span>
                <select
                  aria-label="Issue category"
                  value={category}
                  onChange={(event) => {
                    setCategory(event.target.value);
                    setPage(1);
                  }}
                >
                  <option value="">All categories</option>
                  {categories.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {error && (
              <div className="banner error" role="alert">
                {error}
                <button onClick={() => setRefresh((value) => value + 1)}>
                  Retry
                </button>
              </div>
            )}
            {loading && !data ? (
              <div className="inbox-empty" role="status">
                <span className="spinner" />
                <p>Loading public reports…</p>
              </div>
            ) : data && !data.reports.length ? (
              <div className="inbox-empty">
                <ClipboardList size={35} />
                <h3>
                  {query || category
                    ? "No matching reports"
                    : "Your community inbox starts here."}
                </h3>
                <p>
                  {query || category
                    ? "Try another search or category."
                    : "When someone submits a report in the public app, it will appear here with their details and photos."}
                </p>
                {(query || category) && (
                  <button
                    onClick={() => {
                      setQuery("");
                      setSearch("");
                      setCategory("");
                      setPage(1);
                    }}
                  >
                    Clear filters
                  </button>
                )}
              </div>
            ) : (
              data && (
                <>
                  <div className="inbox-results-meta">
                    <span>
                      {data.total} report{data.total === 1 ? "" : "s"}
                      {loading ? " · Refreshing…" : ""}
                    </span>
                    <span>Newest first</span>
                  </div>
                  <div className="inbox-report-list">
                    {data.reports.map((report) => (
                      <button
                        className="inbox-report-row"
                        key={report.id}
                        onClick={() => setSelected(report)}
                      >
                        <span className="inbox-row-icon">
                          <ClipboardList size={23} />
                        </span>
                        <span className="inbox-row-copy">
                          <span className="inbox-row-kicker">
                            {categoryLabel(report.category)}{" "}
                            <span>· {report.reference}</span>
                          </span>
                          <strong>
                            <MapPin size={15} />
                            {report.location}
                          </strong>
                          <span className="inbox-row-description">
                            {report.description}
                          </span>
                          <span className="inbox-row-meta">
                            {dateLabel(report.created_at)}
                            <span>
                              <Camera size={14} />
                              {report.photo_ids.length} photo
                              {report.photo_ids.length === 1 ? "" : "s"}
                            </span>
                          </span>
                        </span>
                        <span className="badge inbox-status">
                          {statusLabels[report.status]}
                        </span>
                        <ArrowRight size={18} className="inbox-row-arrow" />
                      </button>
                    ))}
                  </div>
                  {data.total > data.page_size && (
                    <div className="inbox-pagination">
                      <button
                        aria-label="Previous reports page"
                        disabled={loading || page <= 1}
                        onClick={() => setPage((value) => value - 1)}
                      >
                        <ArrowLeft size={16} />
                        Previous
                      </button>
                      <span>
                        Page {page} of {Math.ceil(data.total / data.page_size)}
                      </span>
                      <button
                        aria-label="Next reports page"
                        disabled={
                          loading || page * data.page_size >= data.total
                        }
                        onClick={() => setPage((value) => value + 1)}
                      >
                        Next
                        <ArrowRight size={16} />
                      </button>
                    </div>
                  )}
                </>
              )
            )}
            {data && (
              <div className="inbox-storage">
                <span>
                  <Database size={14} />
                  {data.storage.destination === "dbstudios"
                    ? "DBStudios · NightShift AI / public_reports"
                    : "Local workspace database"}
                </span>
                <span>Updated {updated} · Refreshes every 30 seconds</span>
                {authorization && (
                  <button
                    onClick={() => {
                      setAuthorization("");
                      setData(null);
                      setSelected(null);
                    }}
                  >
                    Sign out
                  </button>
                )}
              </div>
            )}
          </section>
        </>
      )}
      {selected && (
        <ReportDetails
          report={selected}
          authorization={authorization}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
