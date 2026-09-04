import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "MPLADS Sentinel",
  description: "AI-Powered Monitoring & Decision Support",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>;
}
