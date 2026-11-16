import AppShell from "@/components/AppShell";

export default function CompanyLayout({ children }: LayoutProps<"/company">) {
  return <AppShell portal="company">{children}</AppShell>;
}
