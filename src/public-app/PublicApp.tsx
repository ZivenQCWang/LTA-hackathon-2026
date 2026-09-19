import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Copy,
  HeartHandshake,
  HelpCircle,
  Info,
  LocateFixed,
  LoaderCircle,
  MapPin,
  MessageSquareText,
  ShieldCheck,
  TrainFront,
  X,
} from "lucide-react";
import { submitReport } from "./api";
import { categories, categoryLabel, dateLabel } from "./constants";
import { PhotoPicker } from "./components/PhotoPicker";
import { MyReports } from "./components/MyReports";
import type { Page, PhotoAttachment, PublicReport, ReportDraft } from "./types";
import "./public-app.css";

const emptyDraft = (): ReportDraft => ({
  request_id: crypto.randomUUID(),
  category: "",
  location: "",
  description: "",
  latitude: null,
  longitude: null,
});
const pageFromHash = (): Page =>
  location.hash === "#reports"
    ? "reports"
    : location.hash === "#help"
      ? "help"
      : "report";

export default function PublicApp() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<ReportDraft>(emptyDraft);
  const [photos, setPhotos] = useState<PhotoAttachment[]>([]);
  const photosRef = useRef(photos);
  const [processing, setProcessing] = useState(false);
  const [sending, setSending] = useState(false);
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState("");
  const [locationError, setLocationError] = useState("");
  const [submitted, setSubmitted] = useState<PublicReport | null>(null);
  const [copied, setCopied] = useState(false);
  const submissionLock = useRef(false);
  const formTop = useRef<HTMLDivElement>(null);
  const interacted = useRef(false);
  const locationRequest = useRef(0);

  useEffect(() => {
    document.title = "PLiZ Public · Report an issue";
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute(
        "content",
        "Spot an issue on your journey? Add a photo, share the location and track your report with PLiZ Public.",
      );
    const onHash = () => {
      if (["", "#report", "#reports", "#help"].includes(location.hash)) {
        setPage(pageFromHash());
      }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    photosRef.current = photos;
  }, [photos]);
  useEffect(
    () => () => {
      photosRef.current.forEach((photo) => URL.revokeObjectURL(photo.preview));
      locationRequest.current++;
    },
    [],
  );
  useEffect(() => {
    if (interacted.current) {
      formTop.current?.scrollIntoView({ behavior: "instant", block: "start" });
      formTop.current?.focus({ preventScroll: true });
    }
  }, [step, page, submitted]);

  function navigate(next: Page) {
    if (sending || processing) return;
    interacted.current = true;
    location.hash = next;
    setPage(next);
    setError("");
  }
  function nextStep(value: number) {
    interacted.current = true;
    setError("");
    setStep(value);
  }
  function reset() {
    locationRequest.current++;
    setLocating(false);
    setLocationError("");
    photos.forEach((photo) => URL.revokeObjectURL(photo.preview));
    setPhotos([]);
    setDraft(emptyDraft());
    setStep(0);
    setSubmitted(null);
    setCopied(false);
    navigate("report");
  }
  function locate() {
    if (!navigator.geolocation) {
      setLocationError(
        "Location is unavailable. Enter the station or landmark below.",
      );
      return;
    }
    const request = ++locationRequest.current;
    setLocating(true);
    setLocationError("");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        if (request !== locationRequest.current) return;
        setDraft((current) => ({
          ...current,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }));
        setLocating(false);
      },
      () => {
        if (request !== locationRequest.current) return;
        setLocationError(
          "Could not access your location. You can enter the station or landmark below.",
        );
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
    );
  }
  async function send() {
    if (submissionLock.current) return;
    submissionLock.current = true;
    setSending(true);
    setError("");
    try {
      const result = await submitReport(draft, photos);
      interacted.current = true;
      setSubmitted(result);
      photos.forEach((photo) => URL.revokeObjectURL(photo.preview));
      setPhotos([]);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not send your report. Please try again.",
      );
    } finally {
      submissionLock.current = false;
      setSending(false);
    }
  }

  return (
    <div className="pub-app">
      <a href="#public-content" className="pub-skip">
        Skip to content
      </a>
      <header className="pub-header">
        <div className="pub-header-inner">
          <button
            className="pub-brand"
            onClick={() => navigate("report")}
            aria-label="PLiZ Public home"
          >
            <img src="/brand/pliz-wordmark.png" alt="PLiZ" />
            <span>PUBLIC</span>
          </button>
          <span className="pub-demo">
            <span />
            Demo
          </span>
        </div>
      </header>

      <main id="public-content" className="pub-layout">
        <aside className="pub-intro">
          <span className="pub-intro-tag">
            <TrainFront size={15} />A LITTLE CARE. A BETTER JOURNEY.
          </span>
          <h1>
            See something?
            <br />
            <span>Say something.</span>
          </h1>
          <p>
            From a broken light to a blocked walkway, help make the next journey
            a little better.
          </p>
          <div className="pub-intro-bottom">
            <span className="pub-heart">
              <HeartHandshake size={25} strokeWidth={1.5} />
            </span>
            <div>
              <strong>Your voice makes a difference.</strong>
              <span>A photo. A few details. That’s all it takes.</span>
            </div>
          </div>
          <div className="pub-desktop-note">
            <ShieldCheck size={18} />
            <span>
              No account needed.
              <br />
              Follow your reports on this browser.
            </span>
          </div>
        </aside>

        <div className="pub-workspace" ref={formTop} tabIndex={-1}>
          {page === "report" &&
            (submitted ? (
              <section className="pub-panel pub-success" aria-live="polite">
                <span className="pub-success-icon">
                  <Check size={37} strokeWidth={1.8} />
                </span>
                <span className="pub-eyebrow">THANK YOU FOR SPEAKING UP</span>
                <h2>Your report is in.</h2>
                <p>
                  You’ve taken the first step.
                  <br />
                  Your report and photos have been saved.
                </p>
                <div className="pub-receipt">
                  <span className="pub-caption">REPORT REFERENCE</span>
                  <strong>{submitted.reference}</strong>
                  <button
                    className="pub-text-button"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(
                          submitted.reference,
                        );
                        setCopied(true);
                      } catch {
                        setError("Copy the reference shown above to save it.");
                      }
                    }}
                  >
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                    {copied ? "Copied" : "Copy reference"}
                  </button>
                  <hr />
                  <span>{categoryLabel(submitted.category)}</span>
                  <b>
                    <MapPin size={15} />
                    {submitted.location}
                  </b>
                  <small>{dateLabel(submitted.created_at)}</small>
                </div>
                <div className="pub-inline-note">
                  <Info size={17} />
                  <span>
                    {submitted.delivery_status === "pending"
                      ? "Your report is safely saved and waiting to reach the operations inbox. Delivery will retry automatically."
                      : submitted.delivery_status === "delivered"
                        ? "Your report is saved in DBStudios and available in the PLiZ operations inbox. No crew has been dispatched."
                        : "Your report is saved in this demo. No crew has been dispatched."}
                  </span>
                </div>
                {error && (
                  <div className="pub-error" role="alert">
                    {error}
                  </div>
                )}
                <button
                  className="pub-button pub-green"
                  onClick={() => navigate("reports")}
                >
                  View my reports <ArrowRight size={18} />
                </button>
                <button className="pub-text-button" onClick={reset}>
                  Report another issue
                </button>
              </section>
            ) : (
              <section className="pub-panel">
                <div className="pub-section-heading">
                  <div>
                    <span className="pub-eyebrow">LET’S MAKE IT BETTER</span>
                    <h2>Report an issue</h2>
                  </div>
                  <span className="pub-step-count">
                    0{step + 1}
                    <span> / 03</span>
                  </span>
                </div>
                <ol className="pub-steps" aria-label="Report progress">
                  {["Add photos", "The details", "Review & send"].map(
                    (label, index) => (
                      <li
                        key={label}
                        className={
                          index === step
                            ? "current"
                            : index < step
                              ? "complete"
                              : ""
                        }
                        aria-current={index === step ? "step" : undefined}
                      >
                        <span>
                          {index < step ? <Check size={13} /> : index + 1}
                        </span>
                        {label}
                      </li>
                    ),
                  )}
                </ol>
                {step === 0 && (
                  <div className="pub-form-step">
                    <PhotoPicker
                      photos={photos}
                      onChange={setPhotos}
                      onBusy={setProcessing}
                    />
                    <div className="pub-inline-note">
                      <ShieldCheck size={19} />
                      <span>
                        Stay in a public area and avoid including people’s faces
                        or personal details.
                      </span>
                    </div>
                    <button
                      className="pub-button pub-green pub-full"
                      disabled={processing}
                      onClick={() => nextStep(1)}
                    >
                      {photos.length
                        ? "Continue to details"
                        : "Continue without a photo"}
                      <ArrowRight size={18} />
                    </button>
                  </div>
                )}
                {step === 1 && (
                  <form
                    className="pub-form-step"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (!draft.category) {
                        setError("Choose the type of issue first.");
                        return;
                      }
                      if (
                        draft.location.trim().length < 3 ||
                        draft.description.trim().length < 10
                      ) {
                        setError(
                          "Enter a location and at least 10 characters describing the issue.",
                        );
                        return;
                      }
                      nextStep(2);
                    }}
                  >
                    <fieldset className="pub-fieldset">
                      <legend>
                        What’s the issue? <span>Required</span>
                      </legend>
                      <div className="pub-categories">
                        {categories.map(({ id, label, detail, icon: Icon }) => (
                          <label
                            key={id}
                            className={draft.category === id ? "selected" : ""}
                          >
                            <input
                              type="radio"
                              name="category"
                              value={id}
                              required
                              checked={draft.category === id}
                              onChange={() =>
                                setDraft({ ...draft, category: id })
                              }
                            />
                            <Icon size={21} strokeWidth={1.7} />
                            <span>
                              <strong>{label}</strong>
                              <small>{detail}</small>
                            </span>
                            <span className="pub-radio">
                              {draft.category === id && <Check size={12} />}
                            </span>
                          </label>
                        ))}
                      </div>
                    </fieldset>
                    <div className="pub-field">
                      <label htmlFor="report-location">
                        Where did you spot it? <span>Required</span>
                      </label>
                      <input
                        id="report-location"
                        placeholder="Station, exit, platform or nearby landmark"
                        required
                        minLength={3}
                        maxLength={160}
                        value={draft.location}
                        onChange={(e) =>
                          setDraft({ ...draft, location: e.target.value })
                        }
                      />
                      <p className="pub-field-hint">
                        For example: City Hall station, Exit B, near the lift.
                      </p>
                      {draft.latitude !== null ? (
                        <div className="pub-location-added">
                          <CheckCircle2 size={17} />
                          <span>GPS location attached</span>
                          <button
                            type="button"
                            aria-label="Remove GPS location"
                            onClick={() =>
                              setDraft({
                                ...draft,
                                latitude: null,
                                longitude: null,
                              })
                            }
                          >
                            <X size={17} />
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          className="pub-text-button"
                          disabled={locating}
                          onClick={locate}
                        >
                          {locating ? (
                            <LoaderCircle size={16} className="pub-spin" />
                          ) : (
                            <LocateFixed size={16} />
                          )}
                          {locating
                            ? "Getting your location…"
                            : "Attach my current location"}
                          <span className="pub-optional">Optional</span>
                        </button>
                      )}
                      {locationError && (
                        <p className="pub-error" role="alert">
                          {locationError}
                        </p>
                      )}
                    </div>
                    <div className="pub-field">
                      <label htmlFor="report-description">
                        Tell us a little more <span>Required</span>
                      </label>
                      <textarea
                        id="report-description"
                        rows={4}
                        placeholder="What happened? Include details that would help someone find and understand the issue."
                        required
                        minLength={10}
                        maxLength={2000}
                        value={draft.description}
                        onChange={(e) =>
                          setDraft({ ...draft, description: e.target.value })
                        }
                      />
                      <span className="pub-character-count">
                        {draft.description.length.toLocaleString()} / 2,000
                      </span>
                    </div>
                    {error && (
                      <div className="pub-error" role="alert">
                        {error}
                      </div>
                    )}
                    <div className="pub-form-actions">
                      <button
                        type="button"
                        className="pub-button pub-back"
                        onClick={() => nextStep(0)}
                      >
                        <ArrowLeft size={18} />
                        Back
                      </button>
                      <button
                        className="pub-button pub-green"
                        disabled={locating}
                        type="submit"
                      >
                        Review report <ArrowRight size={18} />
                      </button>
                    </div>
                  </form>
                )}
                {step === 2 && (
                  <div className="pub-form-step">
                    <div className="pub-review-heading">
                      <h3>Looking right?</h3>
                      <p>Take a quick look before sending.</p>
                    </div>
                    <div className="pub-review">
                      <div>
                        <span>ISSUE</span>
                        <strong>{categoryLabel(draft.category)}</strong>
                      </div>
                      <div>
                        <span>LOCATION</span>
                        <strong>
                          <MapPin size={17} />
                          {draft.location}
                        </strong>
                        {draft.latitude !== null && (
                          <small>
                            GPS attached · {draft.latitude.toFixed(5)},{" "}
                            {draft.longitude?.toFixed(5)}
                          </small>
                        )}
                      </div>
                      <div>
                        <span>WHAT HAPPENED</span>
                        <p>{draft.description}</p>
                      </div>
                      <div>
                        <span>PHOTOS · {photos.length}</span>
                        {photos.length ? (
                          <div className="pub-review-photos">
                            {photos.map((photo, index) => (
                              <img
                                key={photo.id}
                                src={photo.preview}
                                alt={`Photo ${index + 1} to submit`}
                              />
                            ))}
                          </div>
                        ) : (
                          <p>No photos attached.</p>
                        )}
                      </div>
                    </div>
                    <div className="pub-inline-note">
                      <Info size={18} />
                      <span>
                        Your report, photos and any attached location will be
                        available to the PLiZ operations team for review. This
                        demo does not automatically dispatch a crew.
                      </span>
                    </div>
                    {error && (
                      <div className="pub-error" role="alert">
                        {error}
                      </div>
                    )}
                    <div className="pub-form-actions">
                      <button
                        className="pub-button pub-back"
                        disabled={sending}
                        onClick={() => nextStep(1)}
                      >
                        <ArrowLeft size={18} />
                        Edit
                      </button>
                      <button
                        className="pub-button pub-green"
                        disabled={sending}
                        onClick={() => void send()}
                      >
                        {sending ? (
                          <LoaderCircle size={18} className="pub-spin" />
                        ) : (
                          <MessageSquareText size={18} />
                        )}
                        {sending ? "Sending report…" : "Send report"}
                        {!sending && <ArrowRight size={18} />}
                      </button>
                    </div>
                  </div>
                )}
              </section>
            ))}
          {page === "reports" && (
            <MyReports
              onNew={() => (submitted ? reset() : navigate("report"))}
            />
          )}
          {page === "help" && (
            <section className="pub-panel pub-help">
              <span className="pub-eyebrow">HERE TO HELP</span>
              <h2>A little guidance.</h2>
              <p className="pub-muted">
                A useful report starts with a few clear details.
              </p>
              {[
                [
                  "What can I report?",
                  "Tell us about cleanliness, damaged facilities, accessibility issues or safety concerns around stations and public transport spaces.",
                ],
                [
                  "Do I need a photo?",
                  "No. You can continue without a photo. If you do add one, show the issue clearly from a safe, public area. Avoid including faces and personal details.",
                ],
                [
                  "What happens after I send?",
                  "Your report is saved with a reference number and sent to the PLiZ operations inbox through DBStudios. If the connection is interrupted, the saved report retries automatically. Open My reports to see its delivery status. Crew dispatch is not automatic.",
                ],
                [
                  "Where can I find my reports?",
                  "Use My reports on this browser. No account is needed. Clearing browser storage, using private browsing or changing devices can remove access. A reference number alone does not restore access.",
                ],
                [
                  "How is my location used?",
                  "The station or landmark you enter is saved with the report. GPS is optional and is only attached when you tap the location button and allow access. Photo metadata is removed before storage.",
                ],
              ].map(([question, answer]) => (
                <details key={question}>
                  <summary>
                    {question}
                    <ChevronRight size={18} />
                  </summary>
                  <p>{answer}</p>
                </details>
              ))}
              <div className="pub-help-safety">
                <ShieldCheck size={22} />
                <div>
                  <strong>Something needs immediate attention?</strong>
                  <p>
                    Speak to station staff or contact local emergency services
                    if someone is in danger. This demo is not monitored for
                    emergencies.
                  </p>
                </div>
              </div>
            </section>
          )}
          <p className="pub-page-foot">
            <HeartHandshake size={15} />
            Small actions. Better journeys.
          </p>
        </div>
      </main>
      <nav className="pub-bottom-nav" aria-label="Public app navigation">
        <div>
          {(
            [
              { id: "report", label: "Report an issue", icon: Camera },
              { id: "reports", label: "My reports", icon: ClipboardList },
              { id: "help", label: "Help & info", icon: HelpCircle },
            ] as const
          ).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              disabled={sending || processing}
              className={page === id ? "active" : ""}
              aria-current={page === id ? "page" : undefined}
              onClick={() => navigate(id)}
            >
              <span>
                <Icon size={21} strokeWidth={1.8} />
              </span>
              {label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}
