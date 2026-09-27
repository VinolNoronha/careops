"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { apiFetch } from "@/lib/apiClient";
import type { Document } from "@/lib/types";

export function DocumentCard({
  doc,
  onStatusChanged,
}: {
  doc: Document;
  onStatusChanged: () => void;
}) {
  const [updating, setUpdating] = useState(false);

  const updateStatus = async (status: "approved" | "archived") => {
    setUpdating(true);
    try {
      const res = await apiFetch(`/documents/${doc.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) {
        const err: { detail?: string } = await res.json();
        throw new Error(err.detail || "Failed to update status");
      }
      onStatusChanged();
    } catch (err) {
      console.error(err);
    } finally {
      setUpdating(false);
    }
  };

  return (
    <Card className="transition hover:shadow-md">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-base">{doc.title}</CardTitle>
        <DocumentStatusBadge status={doc.status} />
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {doc.department} · {doc.docType} · v{doc.version}
        </p>

        {doc.status === "ready" && (
          <Button
            size="sm"
            className="w-full"
            disabled={updating}
            onClick={() => updateStatus("approved")}
          >
            {updating ? "Approving..." : "Approve"}
          </Button>
        )}

        {doc.status === "approved" && (
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            disabled={updating}
            onClick={() => updateStatus("archived")}
          >
            {updating ? "Archiving..." : "Archive"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
