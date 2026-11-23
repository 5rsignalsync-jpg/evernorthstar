import type { MetadataRoute } from "next";

// PWA manifest for EverNorthstar. When this file exists, Next.js serves
// /manifest.webmanifest automatically — no wiring needed.
//
// Lets users "Add to Home Screen" on iOS / Android and get a true
// standalone app shell (no Safari / Chrome chrome). On Chrome/Edge
// desktop it enables the install prompt + windowed app mode.
//
// theme_color + background_color match the site's dark emerald palette.
// id + start_url pin PWA re-opens to the root dashboard; scope keeps the
// whole site in-app.

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "EverNorthstar · Honest signals for smart-money markets",
    short_name: "EverNorthstar",
    description:
      "Smart Money tracker (Burry / Buffett / Ackman / Pelosi + more), Merlin-style position planner, zone detection, portfolio sync, XRPL adoption tracker. Research tool, not advice.",
    id: "/?source=pwa",
    start_url: "/?source=pwa",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0a0a0a",
    theme_color: "#0a0a0a",
    categories: ["finance", "business", "productivity"],
    icons: [
      // Dynamically rendered via app/icon.tsx + app/apple-icon.tsx. These
      // URL references match the paths Next.js serves those routes at.
      {
        src: "/icon",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icon",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/apple-icon",
        sizes: "180x180",
        type: "image/png",
        purpose: "any",
      },
    ],
    shortcuts: [
      {
        name: "Dashboard",
        url: "/?source=pwa-shortcut",
      },
      {
        name: "Position Planner",
        url: "/planner?source=pwa-shortcut",
      },
      {
        name: "XRPL Tracker",
        url: "/xrpl?source=pwa-shortcut",
      },
      {
        name: "Portfolio",
        url: "/portfolio?source=pwa-shortcut",
      },
    ],
  };
}
