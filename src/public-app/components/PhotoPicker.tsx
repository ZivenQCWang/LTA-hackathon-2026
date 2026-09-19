import { useRef, useState } from "react";
import { Camera, ImagePlus, LoaderCircle, X } from "lucide-react";
import { preparePhoto } from "../api";
import type { PhotoAttachment } from "../types";

export function PhotoPicker({
  photos,
  onChange,
  onBusy,
}: {
  photos: PhotoAttachment[];
  onChange: (photos: PhotoAttachment[]) => void;
  onBusy: (busy: boolean) => void;
}) {
  const camera = useRef<HTMLInputElement>(null);
  const gallery = useRef<HTMLInputElement>(null);
  const locked = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function add(files: FileList | null) {
    if (!files?.length || locked.current) return;
    const selected = Array.from(files);
    if (photos.length + selected.length > 3) {
      setError("You can attach up to 3 photos.");
      return;
    }
    locked.current = true;
    setBusy(true);
    onBusy(true);
    setError("");
    const added: PhotoAttachment[] = [];
    try {
      for (const file of selected) added.push(await preparePhoto(file));
      onChange([...photos, ...added]);
    } catch (e) {
      added.forEach((photo) => URL.revokeObjectURL(photo.preview));
      setError(e instanceof Error ? e.message : "Could not add that photo.");
    } finally {
      locked.current = false;
      setBusy(false);
      onBusy(false);
    }
  }

  return (
    <div className="pub-photo-picker">
      <input
        ref={camera}
        className="pub-hidden"
        type="file"
        accept="image/*"
        capture="environment"
        aria-label="Take a photo"
        onChange={(e) => {
          void add(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={gallery}
        className="pub-hidden"
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
        multiple
        aria-label="Choose photos"
        onChange={(e) => {
          void add(e.target.files);
          e.target.value = "";
        }}
      />
      {photos.length > 0 && (
        <div className="pub-photo-grid">
          {photos.map((photo, index) => (
            <div className="pub-photo" key={photo.id}>
              <img src={photo.preview} alt={`Attached photo ${index + 1}`} />
              <button
                type="button"
                className="pub-remove"
                disabled={busy}
                aria-label={`Remove photo ${index + 1}`}
                onClick={() => {
                  URL.revokeObjectURL(photo.preview);
                  onChange(photos.filter((item) => item.id !== photo.id));
                }}
              >
                <X size={17} />
              </button>
              <span>{String(index + 1).padStart(2, "0")}</span>
            </div>
          ))}
        </div>
      )}
      {photos.length < 3 && (
        <div className="pub-upload-zone">
          <span className="pub-camera-icon">
            <Camera size={29} strokeWidth={1.6} />
          </span>
          <h3>
            {photos.length
              ? "Another angle can help."
              : "Show us what you see."}
          </h3>
          <p>A photo helps explain the issue. Add up to 3.</p>
          <button
            type="button"
            className="pub-button pub-yellow"
            disabled={busy}
            onClick={() => camera.current?.click()}
          >
            {busy ? (
              <LoaderCircle size={19} className="pub-spin" />
            ) : (
              <Camera size={19} />
            )}
            {busy ? "Preparing photos…" : "Take a photo"}
          </button>
          <button
            type="button"
            className="pub-text-button"
            disabled={busy}
            onClick={() => gallery.current?.click()}
          >
            <ImagePlus size={17} />
            Choose from gallery
          </button>
        </div>
      )}
      <p className="pub-caption">
        {photos.length}/3 photos · Up to 8 MB each · Photos are optional
      </p>
      {error && (
        <div className="pub-error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
