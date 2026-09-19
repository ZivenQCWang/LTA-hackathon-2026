export type Category =
  "cleanliness" | "facilities" | "accessibility" | "safety" | "other";
export type Page = "report" | "reports" | "help";

export interface ReportDraft {
  request_id: string;
  category: Category | "";
  location: string;
  description: string;
  latitude: number | null;
  longitude: number | null;
}

export interface PublicReport extends Omit<ReportDraft, "request_id"> {
  id: string;
  reference: string;
  status: "received" | "in_review" | "resolved";
  created_at: string;
  photo_ids: string[];
  delivery_status: 'local' | 'pending' | 'delivered';
}

export interface PhotoAttachment {
  id: string;
  file: File;
  preview: string;
}
