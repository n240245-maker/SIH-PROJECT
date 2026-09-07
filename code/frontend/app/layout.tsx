import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "TRACE-X KAVACH",
  description: "MPLADS Monitoring & Management Platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>;
}
