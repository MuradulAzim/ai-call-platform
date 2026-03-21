import type { Metadata } from 'next';
import Link from 'next/link';
import { ShieldCheck } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Data Deletion Status – Fazle AI',
  description: 'Status of your data deletion request',
};

export default function DeletionStatusPage() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* Header */}
      <header className="border-b">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-xl font-bold">Fazle AI</Link>
          <nav className="flex gap-6 text-sm">
            <Link href="/privacy-policy" className="hover:underline">Privacy Policy</Link>
            <Link href="/terms-services" className="hover:underline">Terms of Service</Link>
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto flex max-w-2xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <div className="rounded-full bg-green-100 p-4 dark:bg-green-900">
          <ShieldCheck className="h-12 w-12 text-green-600 dark:text-green-400" />
        </div>
        <h1 className="mt-6 text-2xl font-bold">Data Deletion Complete</h1>
        <p className="mt-3 text-muted-foreground">
          Your data deletion request has been successfully processed.
          All personal data associated with your account has been permanently removed from our systems.
        </p>
        <p className="mt-6 text-sm text-muted-foreground">
          If you have any questions, please contact us at{' '}
          <a href="mailto:contact@iamazim.com" className="text-primary underline">contact@iamazim.com</a>
        </p>
      </main>

      {/* Footer */}
      <footer className="border-t py-6 text-center text-sm text-muted-foreground">
        <p>&copy; {new Date().getFullYear()} Fazle AI. All rights reserved.</p>
      </footer>
    </div>
  );
}
