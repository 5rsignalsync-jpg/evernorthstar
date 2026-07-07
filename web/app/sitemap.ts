import type { MetadataRoute } from "next";

/**
 * Static sitemap covering the public-facing pages a search engine should
 * crawl. Auth-gated pages (account, portfolio) are excluded — they require
 * a session cookie and don't render useful HTML to a bot.
 *
 * Next.js generates /sitemap.xml from this at build time.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://evernorthstar.app";
  // Use a stable hardcoded date for the lastModified so re-deploys don't
  // churn the sitemap for unchanged content. Bump manually when content
  // materially changes (e.g., legal-page revisions).
  const lastModified = "2026-06-18";
  return [
    { url: `${base}/`, lastModified, priority: 1.0, changeFrequency: "daily" },
    { url: `${base}/pricing`, lastModified, priority: 0.9, changeFrequency: "weekly" },
    { url: `${base}/planner`, lastModified, priority: 0.7, changeFrequency: "monthly" },
    { url: `${base}/sign-up`, lastModified, priority: 0.7, changeFrequency: "monthly" },
    { url: `${base}/sign-in`, lastModified, priority: 0.5, changeFrequency: "monthly" },
    { url: `${base}/legal/terms`, lastModified, priority: 0.3, changeFrequency: "yearly" },
    { url: `${base}/legal/privacy`, lastModified, priority: 0.3, changeFrequency: "yearly" },
    { url: `${base}/legal/refunds`, lastModified, priority: 0.3, changeFrequency: "yearly" },
    { url: `${base}/legal/disclaimer`, lastModified, priority: 0.3, changeFrequency: "yearly" },
  ];
}
