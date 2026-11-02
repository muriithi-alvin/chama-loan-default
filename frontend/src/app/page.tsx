import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { apiGetOptional } from "@/lib/server-api";
import type { Me } from "@/lib/types";

import { Landing } from "./landing";

export const metadata: Metadata = { title: { absolute: "Kibaba · Early warning for chamas" } };

// Signed in: straight to your pages. Otherwise the landing page.
export default async function Home() {
  const me = await apiGetOptional<Me>("/api/me");
  if (me) redirect(me.user.role === "member" ? "/m" : "/o");
  return <Landing />;
}
