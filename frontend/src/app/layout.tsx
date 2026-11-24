import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gym-OS — Gym management made simple",
  description: "Members, QR check-in, payments and reminders for gyms. Powered by Manima AI Tech Solutions.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { themeColor: "#0f172a", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
