"use client";

import { useRouter } from "next/navigation";
import { startTransition } from "react";

import { ServiceError } from "@/components/service-error";

export default function MembersError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const router = useRouter();
  return (
    <ServiceError message="Your records could not load just now. Try again in a minute." reference={error.digest}
      retry={() => startTransition(() => { router.refresh(); reset(); })} />
  );
}
