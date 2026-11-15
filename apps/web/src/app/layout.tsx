import type { Metadata } from "next";

import "@perfect-match/design-system/tokens.css";
import "./styles.css";

export const metadata: Metadata = {
  title: "BEMS Quality | Quality Management Cloud",
  icons: { icon: "/bems-quality-mark.svg" },
  description: "Secure identity and organization access for BEMS Quality by Perfect Match Systems",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
