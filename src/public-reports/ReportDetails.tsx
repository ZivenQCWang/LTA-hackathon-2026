import { useEffect, useState } from "react";
import { Clock3, MapPin } from "lucide-react";
import { Modal } from "../ui";
import type { PublicReport } from "../public-app/types";
import {
  categoryLabel,
  dateLabel,
  statusLabels,
} from "../public-app/constants";
import { requestInbox } from "./api";

function ReportImage({
  reportId,
  photoId,
  index,
  authorization,
}: {
  reportId: string;
  photoId: string;
  index: number;
  authorization: string;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl = "";
    requestInbox(
      `/${reportId}/photos/${photoId}`,
      authorization,
      controller.signal,
    )
      .then((response) => response.blob())
      .then((blob) => {
        if (!controller.signal.aborted) {
          objectUrl = URL.createObjectURL(blob);
          setUrl(objectUrl);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [reportId, photoId, authorization]);
  return url ? (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open attached photo ${index + 1}`}
    >
      <img src={url} alt={`Public report photo ${index + 1}`} />
    </a>
  ) : (
    <div className="inbox-photo-placeholder" role="status">
      {error ? "Photo could not load" : "Loading photo…"}
    </div>
  );
}

export function ReportDetails({
  report,
  authorization,
  onClose,
}: {
  report: PublicReport;
  authorization: string;
  onClose: () => void;
}) {
  return (
    <Modal title={report.reference} onClose={onClose}>
      <div className="inbox-detail">
        <div className="inbox-detail-tags">
          <span className="badge">{categoryLabel(report.category)}</span>
          <span className="badge inbox-status">
            {statusLabels[report.status]}
          </span>
        </div>
        <h3>
          <MapPin size={19} />
          {report.location}
        </h3>
        <p className="inbox-date">
          <Clock3 size={15} />
          {dateLabel(report.created_at)}
        </p>
        <h4>What was reported</h4>
        <p className="inbox-description">{report.description}</p>
        {report.latitude !== null && (
          <div className="inbox-gps">
            <MapPin size={17} />
            <span>
              GPS attached by the reporter: {report.latitude.toFixed(5)},{" "}
              {report.longitude?.toFixed(5)}
            </span>
          </div>
        )}
        <h4>
          Photos <span className="count">{report.photo_ids.length}</span>
        </h4>
        {report.photo_ids.length ? (
          <div className="inbox-photos">
            {report.photo_ids.map((id, index) => (
              <ReportImage
                key={id}
                photoId={id}
                reportId={report.id}
                index={index}
                authorization={authorization}
              />
            ))}
          </div>
        ) : (
          <p className="muted">No photos were attached.</p>
        )}
        <p className="note">
          This report is available for review. Receiving a report does not
          create a maintenance job or dispatch a crew.
        </p>
      </div>
    </Modal>
  );
}
