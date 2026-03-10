import "../globals.css";
import AuthProvider from "../components/AuthProvider";

export const metadata = {
  title: "Fazle — Family AI",
  description: "Your Family's Personal AI — Private & Secure",
  manifest: "/manifest.json",
  themeColor: "#0a0a0f",
  viewport: {
    width: "device-width",
    initialScale: 1,
    maximumScale: 1,
    viewportFit: "cover",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Fazle",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="mobile-web-app-capable" content="yes" />
        <link rel="apple-touch-icon" href="/icon-192.png" />
      </head>
      <body className="min-h-screen bg-[#0a0a0f]">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
