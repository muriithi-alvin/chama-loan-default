import { forbidden } from "next/navigation";

import { AppFooter } from "@/components/app-footer";
import { OfficialShell } from "@/components/official-shell";
import { apiGet, apiGetOptional } from "@/lib/server-api";
import type { Me, RecordsStatus } from "@/lib/types";

// Officials' pages (/o/). The shell needs the signed-in person; the API
// checks the role again on every data request.
export default async function OfficialsLayout({ children }: { children: React.ReactNode }) {
  const [me, status] = await Promise.all([
    apiGet<Me>("/api/me"),
    apiGetOptional<RecordsStatus>("/api/records-status"),
  ]);
  if (me.user.role === "member") forbidden();
  return (
    <OfficialShell me={me} footer={<AppFooter role={me.user.role} status={status} />}>
      {children}
    </OfficialShell>
  );
}
