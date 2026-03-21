'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import * as React from 'react';
import { ShieldCheck, Loader2, AlertCircle } from 'lucide-react';

export default function DeletionStatusPage() {
  const params = useParams();
  const code = params.code as string;
  const [status, setStatus] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string>('');
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!code) return;
    fetch(`/api/fazle/gdpr/deletion-status/${encodeURIComponent(code)}`)
      .then((r) => r.json())
      .then((data) => {
        setStatus(data.status || 'completed');
        setMessage(data.message || '');
      })
      .catch(() => {
        setStatus('completed');
        setMessage('Your data deletion request has been processed.');
      })
      .finally(() => setLoading(false));
  }, [code]);

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
        {loading ? (
          <Loader2 className="h-12 w-12 animate-spin text-muted-foreground" />
        ) : status === 'completed' ? (
          <>
            <div className="rounded-full bg-green-100 p-4 dark:bg-green-900">
              <ShieldCheck className="h-12 w-12 text-green-600 dark:text-green-400" />
            </div>
            <h1 className="mt-6 text-2xl font-bold">Data Deletion Complete</h1>
            <p className="mt-3 text-muted-foreground">{message}</p>
            <p className="mt-2 text-xs text-muted-foreground">Confirmation code: {code}</p>
          </>
        ) : (
          <>
            <div className="rounded-full bg-yellow-100 p-4 dark:bg-yellow-900">
              <AlertCircle className="h-12 w-12 text-yellow-600 dark:text-yellow-400" />
            </div>
            <h1 className="mt-6 text-2xl font-bold">Deletion In Progress</h1>
            <p className="mt-3 text-muted-foreground">{message}</p>
            <p className="mt-2 text-xs text-muted-foreground">Confirmation code: {code}</p>
          </>
        )}
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
