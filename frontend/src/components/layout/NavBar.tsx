import Link from "next/link";
import { getUser } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { LogoutButton } from "./LogoutButton";

export async function NavBar() {
  const user = await getUser();
  const isAdmin = user?.role === "admin";

  return (
    <nav className="flex items-center justify-between border-b px-6 py-3">
      <div className="flex items-center gap-6">
        <Link href="/chat" className="text-lg font-semibold">
          CareOps
        </Link>
        <Link
          href="/chat"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Ask
        </Link>
        {isAdmin && (
          <>
            <Link
              href="/documents"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Documents
            </Link>
            <Link
              href="/audit"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Audit
            </Link>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        {user && (
          <>
            <Badge variant="secondary">{user.role}</Badge>
            <span className="text-sm text-muted-foreground">{user.email}</span>
            <LogoutButton />
          </>
        )}
      </div>
    </nav>
  );
}
