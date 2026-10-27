import type { NextConfig } from "next";

// The Python API (uvicorn chama.web.app:app). The browser only ever talks to
// this Next.js server, which forwards /api/* there, so the session cookie is
// first-party and the API is never exposed on its own.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(self), geolocation=(), microphone=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  // The dev server only serves its live-reload connection to pages opened at
  // localhost; opened at 127.0.0.1 a page showed but never came to life.
  allowedDevOrigins: ["127.0.0.1"],
  // forbidden(): the "not allowed" page with HTTP 403 (R4)
  experimental: { authInterrupts: true },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [
      { source: "/:path*", headers: securityHeaders },
      {
        source: "/fonts/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
    ];
  },
};

export default nextConfig;
