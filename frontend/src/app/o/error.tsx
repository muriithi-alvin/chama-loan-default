"use client";

import { useRouter } from "next/navigation";
import { startTransition } from "react";

import { ServiceError } from "@/components/service-error";

// Production builds hide server error messages, so the page says what it can.
export default function OfficialsError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const router = useRouter();
  const message = error.message && !error.message.startsWith("An error occurred")
    ? error.message
    : "Kibaba could not load this page. Check that the API is running, then try again.";
  return (
    <ServiceError message={message} reference={error.digest}
      retry={() => startTransition(() => { router.refresh(); reset(); })} />
  );
}
