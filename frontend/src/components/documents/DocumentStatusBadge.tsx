import { Badge } from "@/components/ui/badge";

const STATUS_STYLES: Record<string, string> = {
  processing: "bg-yellow-100 text-yellow-800",
  ready: "bg-blue-100 text-blue-800",
  approved: "bg-green-100 text-green-800",
  archived: "bg-gray-100 text-gray-600",
  processing_failed: "bg-red-100 text-red-800",
};

export function DocumentStatusBadge({ status }: { status: string }) {
  return <Badge className={STATUS_STYLES[status] ?? ""}>{status}</Badge>;
}
