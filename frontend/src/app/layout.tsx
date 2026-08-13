import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rafaela – AI Secretary",
  description: "GDPR-compliant AI Executive Secretary",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="el" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
