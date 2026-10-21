import type { Metadata, Viewport } from "next";
import "./marketplace.css";

export const metadata: Metadata = {
  title: "EventraHQ — Extraordinary artists. Unforgettable events.",
  description: "Discover bands, DJs, singers and instrumentalists for your next extraordinary occasion.",
  manifest: "/brand/manifest.webmanifest",
  icons: { icon: "/brand/favicon.svg", apple: "/brand/apple-touch-icon.png" },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#F7F6F2" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
