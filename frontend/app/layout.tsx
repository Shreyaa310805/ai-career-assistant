import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "CareerPilot", description: "AI-powered career preparation" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
