import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "SkillSync — Resume & ATS analysis",
  description:
    "Score your resume the way an applicant tracking system reads it, see which job requirements you are missing, and turn the gap into a plan.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
