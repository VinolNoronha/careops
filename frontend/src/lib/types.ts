export type Source = {
  documentId: string;
  title: string;
  snippet: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  insufficientEvidence?: boolean;
};

export type Document = {
  id: string;
  title: string;
  department: string;
  docType: string;
  status:
    | "processing"
    | "ready"
    | "approved"
    | "archived"
    | "processing_failed";
  version: number;
  createdAt: string;
};
