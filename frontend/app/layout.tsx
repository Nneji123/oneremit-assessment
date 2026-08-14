import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Oneremit Payout Dashboard",
  description: "Create, track, and manage payouts.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="site-header__brand">
            <span className="site-header__mark" aria-hidden="true">
              O
            </span>
            <span>
              Oneremit <span className="site-header__sub">/ PayOut</span>
            </span>
          </Link>
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
