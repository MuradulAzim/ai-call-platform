import "../globals.css";
import AuthProvider from "../components/AuthProvider";

export const metadata = {
  title: "Fazle — Personal AI",
  description: "Fazle Personal AI System — Your intelligent assistant",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0a0a0f]">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
