"use client";

import { useEffect, useState, useCallback } from "react";
import { DocumentCard } from "@/components/documents/DocumentCard";
import { UploadForm } from "@/components/documents/UploadForm";
import { apiFetch } from "@/lib/apiClient";
import type { Document } from "@/lib/types";

type DocumentApiResponse = {
  id: string;
  title: string;
  department: string | null;
  doc_type: string | null;
  version: number;
  status: Document["status"];
  created_at: string;
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/documents");
      const data: DocumentApiResponse[] = await res.json();
      setDocuments(
        data.map((d) => ({
          id: d.id,
          title: d.title,
          department: d.department ?? "",
          docType: d.doc_type ?? "",
          version: d.version,
          status: d.status,
          createdAt: d.created_at,
        })),
      );
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch on mount is the correct pattern here; the setState calls happen inside fetchDocuments's async body/callbacks, not synchronously in the effect itself
    fetchDocuments();
  }, [fetchDocuments]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-xl font-semibold">Knowledge Base</h1>
      <UploadForm onUploaded={fetchDocuments} />
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading documents...</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {documents.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              onStatusChanged={fetchDocuments}
            />
          ))}
        </div>
      )}
    </div>
  );
}
