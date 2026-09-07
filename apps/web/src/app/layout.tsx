import type { Metadata } from "next";

import "@perfect-match/design-system/tokens.css";
import "./styles.css";

export const metadata: Metadata = {
  title: "Perfect Match | Quality Management Cloud",
  description: "Secure identity and organization access for Perfect Match Cloud",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
