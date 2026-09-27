import { NavBar } from "@/components/layout/NavBar";
import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CareOps",
  description: "Hospital knowledge assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <NavBar />
        {children}
      </body>
    </html>
  );
}
