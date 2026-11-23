import { ImageResponse } from "next/og";

// iOS-specific PWA icon — Apple uses 180x180 for home screen. Keep the
// visual distinct-enough from the Android/desktop icon.tsx that the
// branding stays coherent, but Apple applies rounded corners + a subtle
// gloss on its own so we render a plain filled square.

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background:
            "linear-gradient(135deg, #064e3b 0%, #022c22 50%, #000000 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#6ee7b7",
          fontSize: 100,
          fontWeight: 800,
          fontFamily: "system-ui, -apple-system, Helvetica, Arial, sans-serif",
        }}
      >
        ⭐
      </div>
    ),
    { ...size },
  );
}
