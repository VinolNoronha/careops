"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch } from "@/lib/apiClient";

export function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [docType, setDocType] = useState("");
  const [rawText, setRawText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resetForm = () => {
    setTitle("");
    setDepartment("");
    setDocType("");
    setRawText("");
    setFile(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!rawText.trim() && !file) {
      setError("Provide either pasted text or a .txt file");
      return;
    }

    setSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("title", title);
      formData.append("department", department);
      formData.append("doc_type", docType);

      if (file) {
        formData.append("file", file);
      } else {
        formData.append("raw_text", rawText);
      }

      const uploadRes = await apiFetch("/documents", {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        const err: { detail?: string } = await uploadRes.json();
        throw new Error(err.detail || "Upload failed");
      }

      const { id }: { id: string } = await uploadRes.json();

      const processRes = await apiFetch(`/documents/${id}/process`, {
        method: "POST",
      });

      if (!processRes.ok) {
        const err: { detail?: string } = await processRes.json();
        throw new Error(err.detail || "Processing failed");
      }

      resetForm();
      onUploaded();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Upload Document</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
          <Input
            placeholder="Department"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            required
          />
          <Input
            placeholder="Document Type (e.g. Policy, SOP)"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            required
          />

          <Textarea
            placeholder="Paste document text here (or upload a .txt file below instead)..."
            value={rawText}
            onChange={(e) => {
              setRawText(e.target.value);
              if (e.target.value) setFile(null); // text and file are mutually exclusive
            }}
            className="min-h-[100px]"
            disabled={!!file}
          />

          <div className="text-center text-xs text-muted-foreground">
            — or —
          </div>

          <Input
            type="file"
            accept=".txt"
            onChange={(e) => {
              const selected = e.target.files?.[0] ?? null;
              setFile(selected);
              if (selected) setRawText("");
            }}
            disabled={!!rawText.trim()}
          />

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Uploading & processing..." : "Upload"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
