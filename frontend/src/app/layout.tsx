import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";

import "./globals.css";

const body = localFont({
  src: "../fonts/atkinson-hyperlegible-next-latin-wght.woff2",
  weight: "200 800",
  variable: "--font-body",
  display: "swap",
});

const title = localFont({
  src: "../fonts/gabarito-latin-wght.woff2",
  weight: "400 900",
  variable: "--font-title",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Kibaba", template: "%s · Kibaba" },
  description: "Officials see which members to follow up and why. Members see their own records.",
  applicationName: "Kibaba",
  appleWebApp: { capable: true, title: "Kibaba", statusBarStyle: "default" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#14213d",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${body.variable} ${title.variable}`}>
      <body className="min-h-dvh">
        <a href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-button focus:bg-ink focus:px-5 focus:py-3 focus:text-[16px] focus:font-bold focus:text-white">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
