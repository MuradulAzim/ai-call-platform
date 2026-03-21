'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { gdprService, type GdprRequest, type UserConsent } from '@/services/gdpr';
import {
  ShieldCheck, Download, Trash2, Eye, Loader2, CheckCircle2,
  XCircle, AlertTriangle, FileText, History,
} from 'lucide-react';

export default function PrivacyDashboardPage() {
  const [loading, setLoading] = React.useState(true);
  const [userData, setUserData] = React.useState<Record<string, unknown> | null>(null);
  const [showData, setShowData] = React.useState(false);
  const [dataLoading, setDataLoading] = React.useState(false);

  const [exporting, setExporting] = React.useState(false);

  const [deleting, setDeleting] = React.useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = React.useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = React.useState('');

  const [consent, setConsent] = React.useState<UserConsent>({
    terms_accepted: false,
    privacy_accepted: false,
    accepted_at: null,
  });
  const [savingConsent, setSavingConsent] = React.useState(false);

  const [requests, setRequests] = React.useState<GdprRequest[]>([]);
  const [message, setMessage] = React.useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const showMsg = (text: string, type: 'success' | 'error') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const fetchAll = React.useCallback(async () => {
    try {
      const [consentRes, requestsRes] = await Promise.all([
        gdprService.getConsent(),
        gdprService.getRequests(),
      ]);
      setConsent(consentRes);
      setRequests(requestsRes.requests || []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── View My Data ──
  const handleViewData = async () => {
    setDataLoading(true);
    try {
      const data = await gdprService.getMyData();
      setUserData(data);
      setShowData(true);
    } catch {
      showMsg('Failed to load your data', 'error');
    } finally {
      setDataLoading(false);
    }
  };

  // ── Export Data ──
  const handleExport = async () => {
    setExporting(true);
    try {
      const result = await gdprService.exportMyData();
      const filename = result.filename || `fazle-data-export-${new Date().toISOString().split('T')[0]}.json`;
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      showMsg('Data exported and downloaded successfully', 'success');
      fetchAll();
    } catch {
      showMsg('Failed to export data', 'error');
    } finally {
      setExporting(false);
    }
  };

  // ── Delete Account ──
  const handleDelete = async () => {
    if (deleteConfirmText !== 'DELETE') return;
    setDeleting(true);
    try {
      const result = await gdprService.deleteMyData();
      const tables = result.deleted_from?.length
        ? ` (${result.deleted_from.join(', ')})`
        : '';
      showMsg(`All your data has been permanently deleted${tables}`, 'success');
      // Clear local state and redirect to login
      localStorage.removeItem('fazle_token');
      localStorage.removeItem('fazle_role');
      setTimeout(() => { window.location.href = '/login'; }, 2000);
    } catch {
      showMsg('Failed to delete data', 'error');
      setDeleting(false);
    }
  };

  // ── Save Consent ──
  const handleSaveConsent = async () => {
    setSavingConsent(true);
    try {
      const res = await gdprService.saveConsent(consent.terms_accepted, consent.privacy_accepted);
      setConsent(res.consent);
      showMsg('Consent preferences saved', 'success');
    } catch {
      showMsg('Failed to save consent', 'error');
    } finally {
      setSavingConsent(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <ShieldCheck className="h-8 w-8 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">Privacy & Data</h1>
          <p className="text-sm text-muted-foreground">Manage your data, privacy preferences, and GDPR rights</p>
        </div>
      </div>

      {/* Feedback message */}
      {message && (
        <div className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm ${
          message.type === 'success'
            ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200'
            : 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          {message.text}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* 1. My Data */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5" />
              My Data
            </CardTitle>
            <CardDescription>View all personal data stored about you</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={handleViewData} disabled={dataLoading} className="w-full">
              {dataLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Eye className="mr-2 h-4 w-4" />}
              View My Data
            </Button>
            {showData && userData && (
              <div className="max-h-64 overflow-auto rounded-md bg-muted p-3">
                <pre className="text-xs whitespace-pre-wrap break-words">
                  {JSON.stringify(userData, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 2. Export Data */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5" />
              Export Data
            </CardTitle>
            <CardDescription>Download a copy of all your data in JSON format</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={handleExport} disabled={exporting} className="w-full">
              {exporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
              Download My Data
            </Button>
          </CardContent>
        </Card>

        {/* 3. Delete Account */}
        <Card className="border-destructive/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" />
              Delete Account
            </CardTitle>
            <CardDescription>
              Permanently delete all your data. This action cannot be undone.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!showDeleteConfirm ? (
              <Button variant="destructive" onClick={() => setShowDeleteConfirm(true)} className="w-full">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete My Data
              </Button>
            ) : (
              <div className="space-y-3 rounded-lg border border-destructive/50 bg-destructive/5 p-4">
                <div className="flex items-start gap-2 text-sm text-destructive">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>This will permanently delete your profile, messages, AI logs, and social data. Type <strong>DELETE</strong> to confirm.</span>
                </div>
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  placeholder="Type DELETE to confirm"
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                />
                <div className="flex gap-2">
                  <Button
                    variant="destructive"
                    onClick={handleDelete}
                    disabled={deleteConfirmText !== 'DELETE' || deleting}
                    className="flex-1"
                  >
                    {deleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Confirm Delete
                  </Button>
                  <Button variant="outline" onClick={() => { setShowDeleteConfirm(false); setDeleteConfirmText(''); }}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 4. Consent Management */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Consent Management
            </CardTitle>
            <CardDescription>Manage your consent for platform terms and policies</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consent.terms_accepted}
                  onChange={(e) => setConsent(prev => ({ ...prev, terms_accepted: e.target.checked }))}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <span className="text-sm">
                  I accept the{' '}
                  <a href="/terms-services" target="_blank" className="text-primary underline">Terms of Service</a>
                </span>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={consent.privacy_accepted}
                  onChange={(e) => setConsent(prev => ({ ...prev, privacy_accepted: e.target.checked }))}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <span className="text-sm">
                  I accept the{' '}
                  <a href="/privacy-policy" target="_blank" className="text-primary underline">Privacy Policy</a>
                </span>
              </label>
            </div>
            {consent.accepted_at && (
              <p className="text-xs text-muted-foreground">
                Last updated: {new Date(consent.accepted_at).toLocaleDateString()}
              </p>
            )}
            <Button onClick={handleSaveConsent} disabled={savingConsent} className="w-full">
              {savingConsent ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
              Save Preferences
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* 5. GDPR Request History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            GDPR Request History
          </CardTitle>
          <CardDescription>All your data access, export, and deletion requests</CardDescription>
        </CardHeader>
        <CardContent>
          {requests.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No requests yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 font-medium">Request Type</th>
                    <th className="pb-2 font-medium">Status</th>
                    <th className="pb-2 font-medium">Requested</th>
                    <th className="pb-2 font-medium">Completed</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((req) => (
                    <tr key={req.id} className="border-b last:border-0">
                      <td className="py-3 capitalize">{req.request_type}</td>
                      <td className="py-3">
                        <Badge variant={req.status === 'completed' ? 'default' : req.status === 'failed' ? 'destructive' : 'secondary'}>
                          {req.status}
                        </Badge>
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {new Date(req.created_at).toLocaleString()}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {req.completed_at ? new Date(req.completed_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
