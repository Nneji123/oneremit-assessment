import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Oneremit Payout Dashboard",
  description: "Foundation for the Oneremit payout assessment.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
