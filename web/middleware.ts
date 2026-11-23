import { NextRequest, NextResponse } from "next/server";

// Subdomain router.
//
// Lets us serve dedicated content at xrpl.evernorthstar.app without
// creating a separate Vercel project. A request to that subdomain is
// rewritten internally to /xrpl, so the same Next.js app renders the
// XRPL tracker page while the URL in the address bar stays on the
// subdomain. SEO-wise Google treats it as a separate site; operationally
// it's one codebase, one deploy, one domain config.
//
// Add new subdomains by extending SUBDOMAIN_ROUTES below.

const SUBDOMAIN_ROUTES: Record<string, string> = {
  xrpl: "/xrpl",
};

export function middleware(req: NextRequest) {
  const host = req.headers.get("host") || "";
  // Only route the host-level subdomain; ignore vercel preview URLs and
  // localhost which also have multi-part hosts.
  if (!host.endsWith("evernorthstar.app")) {
    return NextResponse.next();
  }
  const parts = host.split(".");
  // parts.length === 3 means something like xrpl.evernorthstar.app
  // (apex is 2 parts: evernorthstar.app)
  if (parts.length !== 3) {
    return NextResponse.next();
  }
  const subdomain = parts[0];
  const target = SUBDOMAIN_ROUTES[subdomain];
  if (!target) {
    return NextResponse.next();
  }
  // Don't rewrite requests that already target the subdomain's path or
  // static Next.js asset URLs (_next, favicon, api).
  const url = req.nextUrl;
  if (
    url.pathname === target ||
    url.pathname.startsWith(target + "/") ||
    url.pathname.startsWith("/_next") ||
    url.pathname.startsWith("/api") ||
    url.pathname === "/favicon.ico" ||
    url.pathname === "/robots.txt" ||
    url.pathname === "/sitemap.xml"
  ) {
    return NextResponse.next();
  }
  // Rewrite the root (and any unmapped path) under this subdomain to the
  // target page. e.g. xrpl.evernorthstar.app/ → /xrpl
  const rewriteUrl = url.clone();
  rewriteUrl.pathname = target;
  return NextResponse.rewrite(rewriteUrl);
}

export const config = {
  matcher: [
    // Run on every request except Next internals + static files
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)",
  ],
};
