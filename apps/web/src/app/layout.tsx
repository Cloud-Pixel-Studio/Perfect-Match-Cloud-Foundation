import type { Metadata } from "next";

import "@fontsource-variable/inter";
import "@perfect-match/design-system/tokens.css";
import "./styles.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000"),
  title: { default: "Perfect Match QMS", template: "%s | Perfect Match QMS" },
  description: "Quality operations, evidence and compliance in one governed workspace.",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [{ url: "/brand/selected/favicon.svg", type: "image/svg+xml" }, { url: "/brand/raster/favicon-64.png", sizes: "64x64", type: "image/png" }],
    apple: "/brand/raster/apple-touch-icon.png",
  },
  openGraph: {
    title: "Perfect Match QMS",
    description: "Quality operations, evidence and compliance in one governed workspace.",
    images: [{ url: "/brand/social/raster/og-perfect-match-qms-1200x630.png", width: 1200, height: 630, alt: "Perfect Match QMS — evidence, responsibility and decisions aligned" }],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
