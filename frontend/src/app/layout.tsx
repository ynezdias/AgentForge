import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "AgentForge | Operations Dashboard",
  description: "Monitor invoices and automation workflows in AgentForge.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
