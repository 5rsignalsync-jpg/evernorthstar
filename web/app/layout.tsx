import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/components/AuthProvider";
import { Footer } from "@/components/Footer";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://evernorthstar.app"),
  title: {
    default: "EverNorthstar · Honest signals for smart-money markets",
    template: "%s · EverNorthstar",
  },
  description:
    "Track Burry, Buffett, Ackman, Pelosi, and 6 more smart-money portfolios — "
    + "cross-referenced against your own brokerage holdings via Plaid. "
    + "13F + Form 4 + STOCK Act flows · FinBERT-scored news · honest backtests with realistic costs. "
    + "Research signals, not financial advice.",
  keywords: [
    "smart money tracker", "13F tracker", "Pelosi tracker", "Congressional trades",
    "Form 4 insider trading", "momentum signals", "portfolio sync Plaid",
    "investment research tool", "Burry portfolio", "Buffett portfolio",
  ],
  authors: [{ name: "5Royals Investments LLC" }],
  creator: "5Royals Investments LLC",
  publisher: "EverNorthstar",
  alternates: {
    canonical: "https://evernorthstar.app",
  },
  openGraph: {
    title: "EverNorthstar · Honest signals for smart-money markets",
    description:
      "Mirror Burry, Buffett, Ackman, Pelosi, and 6 more — cross-referenced "
      + "against your own holdings via Plaid. AI-explained, lag-honest, backtested.",
    url: "https://evernorthstar.app",
    siteName: "EverNorthstar",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "EverNorthstar · Honest signals for smart-money markets",
    description:
      "Mirror Burry, Buffett, Pelosi + 7 more. Cross-referenced with your "
      + "brokerage via Plaid. Honest signals. Not advice.",
    creator: "@evernorthstar",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  category: "finance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          <div className="flex-1">{children}</div>
          <Footer />
        </AuthProvider>
      </body>
    </html>
  );
}
