import type { MetadataRoute } from "next";

/**
 * Robots policy. Allow indexing of the marketing surface (homepage,
 * pricing, legal) but disallow auth-gated user pages — they require a
 * session cookie and the bot just sees the redirect to /sign-in.
 *
 * Next.js generates /robots.txt from this at build time.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/pricing", "/sign-up", "/sign-in", "/legal/"],
        disallow: ["/account", "/portfolio", "/billing/"],
      },
    ],
    sitemap: "https://evernorthstar.app/sitemap.xml",
    host: "https://evernorthstar.app",
  };
}
