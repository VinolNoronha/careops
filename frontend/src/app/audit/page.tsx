"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/apiClient";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type AuditLog = {
  id: string;
  event_type: string;
  actor_email: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

const EVENT_STYLES: Record<string, string> = {
  ask: "bg-blue-100 text-blue-800",
  document_upload: "bg-purple-100 text-purple-800",
  document_processed: "bg-indigo-100 text-indigo-800",
  document_processing_failed: "bg-red-100 text-red-800",
  document_status_changed: "bg-amber-100 text-amber-800",
};

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/audit");
      const data: AuditLog[] = await res.json();
      setLogs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch on mount
    fetchLogs();
  }, [fetchLogs]);

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-xl font-semibold">Audit Log</h1>

      {loading ? (
        <p className="text-sm text-muted-foreground">Loading audit trail...</p>
      ) : logs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No audit events yet.</p>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <Card key={log.id}>
              <CardContent className="flex items-start justify-between gap-4 p-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge className={EVENT_STYLES[log.event_type] ?? ""}>
                      {log.event_type}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {log.actor_email ?? "unknown user"}
                    </span>
                  </div>
                  {log.metadata && Object.keys(log.metadata).length > 0 && (
                    <pre className="max-w-xl overflow-x-auto rounded bg-muted p-2 text-xs text-muted-foreground">
                      {JSON.stringify(log.metadata, null, 2)}
                    </pre>
                  )}
                </div>
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  {new Date(log.created_at).toLocaleString()}
                </span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
