import type { Metadata } from "next";
import Image from "next/image";
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
  icons: {
    icon: "/favicon.svg",
  },
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
          <div className="site-header__inner">
            <Link href="/" className="site-header__brand" aria-label="Oneremit home">
              <Image
                src="/oneremit-logo.svg"
                alt="Oneremit"
                width={138}
                height={26}
                priority
              />
              <span className="site-header__sub">PayOut</span>
            </Link>
            <nav className="site-header__switcher" aria-label="Account type">
              <Link className="site-header__switcher-active" href="/">
                Business
              </Link>
              <a href="#create-transfer">Personal</a>
              <a href="#transfers">Student</a>
            </nav>
            <div className="site-header__actions">
              <a className="site-header__signup" href="#create-transfer">
                Get started
              </a>
              <a className="site-header__login" href="#transfers">
                Log in
              </a>
            </div>
          </div>
        </header>
        <main className="site-main">{children}</main>
      </body>
    </html>
  );
}
