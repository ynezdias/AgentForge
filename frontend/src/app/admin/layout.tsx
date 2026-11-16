import AppShell from "@/components/AppShell";

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return <AppShell portal="admin">{children}</AppShell>;
}
