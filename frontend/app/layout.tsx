import type { Metadata } from "next";
import Link from "next/link";
import { Albert_Sans } from "next/font/google";
import "./globals.css";

const albertSans = Albert_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-albert-sans",
  display: "swap",
});

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
      <body className={albertSans.variable}>
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
