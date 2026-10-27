import type { MetadataRoute } from "next";

// Lets officials add the site to a phone's home screen (X7).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Kibaba: chama early warning",
    short_name: "Kibaba",
    description: "Which members to follow up and why, from the chama's own records.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#14213d",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon-maskable.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
  };
}
