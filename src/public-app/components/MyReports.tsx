import { useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  ClipboardList,
  Clock3,
  LoaderCircle,
  MapPin,
  RefreshCw,
} from "lucide-react";
import { getPhoto, getReports } from "../api";
import { categoryLabel, dateLabel, statusLabels } from "../constants";
import type { PublicReport } from "../types";

function SavedPhoto({
  reportId,
  photoId,
  index,
}: {
  reportId: string;
  photoId: string;
  index: number;
}) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true,
      objectUrl = "";
    getPhoto(reportId, photoId)
      .then((blob) => {
        if (active) {
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        }
      })
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [reportId, photoId]);
  return url ? (
    <a
      className="pub-saved-photo"
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open report photo ${index + 1}`}
    >
      <img src={url} alt={`Report photo ${index + 1}`} />
    </a>
  ) : (
    <span className="pub-photo-loading">
      {failed ? "Photo unavailable" : "Loading photo…"}
    </span>
  );
}

export function MyReports({ onNew }: { onNew: () => void }) {
  const [reports, setReports] = useState<PublicReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    getReports()
      .then((items) => active && setReports(items))
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [reload]);
  return (
    <section className="pub-panel pub-reports">
      <div className="pub-section-heading">
        <div>
          <span className="pub-eyebrow">KEEP IN THE LOOP</span>
          <h2>My reports</h2>
        </div>
        <button
          className="pub-icon-button"
          aria-label="Refresh reports"
          disabled={loading}
          onClick={() => setReload((value) => value + 1)}
        >
          <RefreshCw size={19} className={loading ? "pub-spin" : ""} />
        </button>
      </div>
      <p className="pub-muted">
        Reports submitted from this browser appear here.
      </p>
      {loading ? (
        <div className="pub-empty" role="status">
          <LoaderCircle className="pub-spin" />
          <p>Loading your reports…</p>
        </div>
      ) : error ? (
        <div className="pub-error" role="alert">
          {error}
          <button
            className="pub-text-button"
            onClick={() => setReload((value) => value + 1)}
          >
            Try again <RefreshCw size={16} />
          </button>
        </div>
      ) : reports.length ? (
        <div className="pub-report-list">
          {reports.map((report) => (
            <details className="pub-report-card" key={report.id}>
              <summary>
                <span className="pub-report-category">
                  {categoryLabel(report.category)}
                </span>
                <span className={"pub-status pub-status-" + report.status}>
                  {statusLabels[report.status] ?? report.status}
                </span>
                <strong>{report.location}</strong>
                <span className="pub-report-meta">
                  {report.reference} · {dateLabel(report.created_at)}
                </span>
                <span className="pub-report-expand">
                  View report <ArrowRight size={15} />
                </span>
              </summary>
              <div className="pub-report-detail">
                <p>{report.description}</p>
                {report.latitude !== null && (
                  <p className="pub-caption">
                    <MapPin size={14} />
                    GPS attached: {report.latitude.toFixed(5)},{" "}
                    {report.longitude?.toFixed(5)}
                  </p>
                )}
                {!!report.photo_ids.length && (
                  <div className="pub-saved-photos">
                    {report.photo_ids.map((id, index) => (
                      <SavedPhoto
                        key={id}
                        photoId={id}
                        reportId={report.id}
                        index={index}
                      />
                    ))}
                  </div>
                )}
                <div className="pub-timeline">
                  <span>
                    <Check size={17} />
                  </span>
                  <div>
                    <strong>Report received</strong>
                    <p>
                      {report.delivery_status === "pending"
                        ? "Saved safely. Delivery to the operations inbox is waiting to retry."
                        : report.delivery_status === "delivered"
                          ? "Delivered to the PLiZ operations inbox. No crew has been dispatched."
                          : "Saved to the local demo. No crew has been dispatched."}
                    </p>
                  </div>
                </div>
                {report.status !== "received" && (
                  <div className="pub-timeline">
                    <span>
                      <Clock3 size={17} />
                    </span>
                    <div>
                      <strong>{statusLabels[report.status]}</strong>
                    </div>
                  </div>
                )}
              </div>
            </details>
          ))}
        </div>
      ) : (
        <div className="pub-empty">
          <span className="pub-empty-icon">
            <ClipboardList size={33} strokeWidth={1.4} />
          </span>
          <h3>A small report. A useful first step.</h3>
          <p>
            You haven’t submitted a report yet.
            <br />
            Spot something along your journey? Let us know.
          </p>
          <button className="pub-button pub-green" onClick={onNew}>
            Make your first report <ArrowRight size={18} />
          </button>
        </div>
      )}
      <p className="pub-storage-note">
        Your reports are saved on the server. This browser holds the access key;
        clearing browser storage or switching devices removes your access.
      </p>
    </section>
  );
}
