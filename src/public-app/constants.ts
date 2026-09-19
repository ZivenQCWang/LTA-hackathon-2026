import {
  Accessibility,
  CircleHelp,
  ShieldAlert,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { Category } from "./types";

export const categories = [
  {
    id: "cleanliness",
    label: "Cleanliness",
    detail: "Litter, spills & dirty areas",
    icon: Sparkles,
  },
  {
    id: "facilities",
    label: "Facilities",
    detail: "Lights, lifts & equipment",
    icon: Wrench,
  },
  {
    id: "accessibility",
    label: "Accessibility",
    detail: "Blocked or difficult access",
    icon: Accessibility,
  },
  {
    id: "safety",
    label: "Safety concern",
    detail: "Damage & potential hazards",
    icon: ShieldAlert,
  },
  {
    id: "other",
    label: "Something else",
    detail: "Anything we have missed",
    icon: CircleHelp,
  },
] as const;

export function categoryLabel(category: Category | "") {
  return categories.find((item) => item.id === category)?.label ?? "Report";
}

export const statusLabels = {
  received: "Received",
  in_review: "In review",
  resolved: "Resolved",
};

export function dateLabel(value: string) {
  return new Intl.DateTimeFormat("en-SG", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
