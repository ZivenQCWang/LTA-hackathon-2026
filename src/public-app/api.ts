import type { PhotoAttachment, PublicReport, ReportDraft } from "./types";

const API = (import.meta.env.VITE_API_URL ?? "/api") + "/public";
const KEY = "pliz.public.report-key.v1";

function reportKey(): string {
  try {
    let key = localStorage.getItem(KEY);
    if (!key) {
      key = crypto.randomUUID() + crypto.randomUUID();
      localStorage.setItem(KEY, key);
    }
    return key;
  } catch {
    throw new Error(
      "Allow browser storage to submit and track your reports on this device.",
    );
  }
}

async function request(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(API + path, {
      ...init,
      headers: { ...init.headers, "X-Report-Key": reportKey() },
    });
  } catch (error) {
    if (error instanceof Error && error.message.includes("browser storage"))
      throw error;
    throw new Error(
      "Could not connect. Check your connection and try again. Your form is still here.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "We could not save your report. Please try again.",
    );
  }
  return response;
}

export async function submitReport(
  draft: ReportDraft,
  photos: PhotoAttachment[],
): Promise<PublicReport> {
  const body = new FormData();
  body.append("report", JSON.stringify(draft));
  photos.forEach((photo) => body.append("photos", photo.file));
  return (await request("/reports", { method: "POST", body })).json();
}

export async function getReports(): Promise<PublicReport[]> {
  return (await (await request("/reports")).json()).reports;
}

export async function getPhoto(
  reportId: string,
  photoId: string,
): Promise<Blob> {
  return (await request(`/reports/${reportId}/photos/${photoId}`)).blob();
}

export async function preparePhoto(file: File): Promise<PhotoAttachment> {
  if (file.size > 8 * 1024 * 1024)
    throw new Error("Choose a photo smaller than 8 MB.");
  if (
    ![
      "image/jpeg",
      "image/png",
      "image/webp",
      "image/heic",
      "image/heif",
    ].includes(file.type)
  ) {
    throw new Error(
      "Choose a JPG, PNG or WebP photo. You can also take a photo with your camera.",
    );
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const scale = Math.min(
      1,
      1600 / Math.max(img.naturalWidth, img.naturalHeight),
    );
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Image processing is unavailable.");
    context.fillStyle = "#fff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(img, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        (result) => (result ? resolve(result) : reject()),
        "image/jpeg",
        0.85,
      ),
    );
    const safeFile = new File([blob], "report-photo.jpg", {
      type: "image/jpeg",
    });
    return {
      id: crypto.randomUUID(),
      file: safeFile,
      preview: URL.createObjectURL(blob),
    };
  } catch {
    throw new Error(
      "This photo could not be opened. Try a JPG, PNG or WebP version.",
    );
  } finally {
    URL.revokeObjectURL(url);
  }
}
