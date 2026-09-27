import { Card, CardContent } from "@/components/ui/card";
import type { Source } from "@/lib/types";

export function SourceCitation({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs font-medium text-muted-foreground">Sources</p>
      {sources.map((s) => (
        <Card key={s.documentId} className="bg-muted/50">
          <CardContent className="p-2 text-xs">
            <span className="font-medium">{s.title}</span>
            <p className="text-muted-foreground line-clamp-2">{s.snippet}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
