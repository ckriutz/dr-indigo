import { Geist, Geist_Mono } from "next/font/google";
import { CopilotKit } from "@copilotkit/react-core"; 
import "./globals.css";
import "@copilotkit/react-ui/styles.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "Dr. Indigo Medical Assistant",
  description: "A medical assistant powered by AI",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <CopilotKit runtimeUrl="/api/copilotkit"> 
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}
