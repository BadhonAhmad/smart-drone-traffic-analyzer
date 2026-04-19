import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Smart Drone Traffic Analyzer",
  description: "Upload drone video to detect, track, and count vehicles",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0f1117] text-gray-200 antialiased">
        {children}
      </body>
    </html>
  );
}
