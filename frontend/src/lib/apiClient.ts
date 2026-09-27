import { createClient } from "./supabase/client";

export async function apiFetch(path: string, options: RequestInit = {}) {
  const supabase = createClient();

  const {
    data: { session },
  } = await supabase.auth.getSession();

  return fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${session?.access_token}`,
    },
  });
}
