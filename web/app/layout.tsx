import type { Metadata } from "next";
import { Space_Grotesk } from "next/font/google";
import "./globals.css";
import { Toaster } from "sonner";

const display = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Session Doctor",
  description: "Fix Hermes chats stuck on stale locked thoughts. Local only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${display.variable}`}>
      <body className="grain bg-canvas-950 font-sans text-neutral-100 antialiased">
        {children}
        <Toaster
          richColors
          position="bottom-right"
          toastOptions={{
            style: { background: "#0f1011", border: "1px solid rgba(255,255,255,.1)" },
          }}
        />
      </body>
    </html>
  );
}
