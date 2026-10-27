import { NotAllowed } from "@/components/not-allowed";
import { apiGetOptional } from "@/lib/server-api";
import type { Me } from "@/lib/types";

// Rendered with HTTP 403 whenever a page calls forbidden() (R4, MEM-3).
export default async function Forbidden() {
  const me = await apiGetOptional<Me>("/api/me");
  if (me?.user.role === "member") return <NotAllowed home="/m" homeLabel="Go to my summary" />;
  if (me) return <NotAllowed home="/o" homeLabel="Go to the overview" />;
  return <NotAllowed home="/signin" homeLabel="Sign in" />;
}
