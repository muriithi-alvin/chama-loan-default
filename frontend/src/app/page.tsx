import { redirect } from "next/navigation";

import { apiGetOptional } from "@/lib/server-api";
import type { Me } from "@/lib/types";

export default async function Home() {
  const me = await apiGetOptional<Me>("/api/me");
  if (!me) redirect("/signin");
  redirect(me.user.role === "member" ? "/m" : "/o");
}
