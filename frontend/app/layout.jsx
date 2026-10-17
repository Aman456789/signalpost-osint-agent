import "./globals.css";
import { AppShell } from "@/components/AppShell";
import { JobProvider } from "@/lib/job-context";

export const metadata = {
  title: "Signalpost",
  description: "Signalpost OSINT Agent dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <JobProvider>
          <AppShell>{children}</AppShell>
        </JobProvider>
      </body>
    </html>
  );
}
