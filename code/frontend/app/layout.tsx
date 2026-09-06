import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "TraceX - Kavach",
  description: "TraceX - Kavach synthetic demonstration of AI-powered MPLADS monitoring and human decision support",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>;
}
