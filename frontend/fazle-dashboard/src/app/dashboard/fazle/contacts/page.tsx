'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  socialService,
  type ContactBookEntry,
} from '@/services/social';
import {
  Users, Search, Upload, RefreshCw, Loader2, Plus,
  CheckCircle2, XCircle, Edit, Trash2, Save, X,
  Phone, Building2, UserCheck, Star, MessageCircle,
} from 'lucide-react';

type EditingContact = Partial<ContactBookEntry> & { id?: string };

export default function ContactsPage() {
  const [contacts, setContacts] = React.useState<ContactBookEntry[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState('');
  const [platformFilter, setPlatformFilter] = React.useState('');
  const [message, setMessage] = React.useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [editing, setEditing] = React.useState<EditingContact | null>(null);
  const [showImport, setShowImport] = React.useState(false);
  const [csvText, setCsvText] = React.useState('');
  const [importing, setImporting] = React.useState(false);
  const [total, setTotal] = React.useState(0);

  const showMsg = (text: string, type: 'success' | 'error' = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const fetchContacts = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await socialService.listContactBook({
        search: search || undefined,
        platform: platformFilter || undefined,
        limit: 200,
      });
      setContacts(data.contacts || []);
      setTotal(data.total || 0);
    } catch {
      showMsg('Failed to load contacts', 'error');
    } finally {
      setLoading(false);
    }
  }, [search, platformFilter]);

  React.useEffect(() => {
    const t = setTimeout(fetchContacts, 300);
    return () => clearTimeout(t);
  }, [fetchContacts]);

  const handleSave = async () => {
    if (!editing?.id) return;
    try {
      await socialService.updateContactBookEntry(editing.id, {
        name: editing.name,
        relation: editing.relation,
        notes: editing.notes,
        company: editing.company,
        personality_hint: editing.personality_hint,
      } as Partial<ContactBookEntry>);
      showMsg('Contact updated');
      setEditing(null);
      fetchContacts();
    } catch {
      showMsg('Update failed', 'error');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this contact?')) return;
    try {
      await socialService.deleteContactBookEntry(id);
      showMsg('Contact deleted');
      fetchContacts();
    } catch {
      showMsg('Delete failed', 'error');
    }
  };

  const handleImport = async () => {
    if (!csvText.trim()) return;
    setImporting(true);
    try {
      const result = await socialService.importContactsCsv(csvText);
      showMsg(`Imported ${result.imported} contacts`);
      setCsvText('');
      setShowImport(false);
      fetchContacts();
    } catch {
      showMsg('Import failed', 'error');
    } finally {
      setImporting(false);
    }
  };

  const interestColor = (level: string) => {
    switch (level) {
      case 'hot': return 'bg-red-500/20 text-red-600 dark:text-red-400';
      case 'warm': return 'bg-orange-500/20 text-orange-600 dark:text-orange-400';
      case 'cold': return 'bg-blue-500/20 text-blue-600 dark:text-blue-400';
      case 'risk': return 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-400';
      default: return 'bg-gray-500/20 text-gray-600 dark:text-gray-400';
    }
  };

  const relationColor = (rel: string) => {
    switch (rel) {
      case 'vip': return 'bg-purple-500/20 text-purple-600 dark:text-purple-400';
      case 'client': return 'bg-green-500/20 text-green-600 dark:text-green-400';
      case 'friend': return 'bg-blue-500/20 text-blue-600 dark:text-blue-400';
      case 'family': return 'bg-pink-500/20 text-pink-600 dark:text-pink-400';
      case 'employee': return 'bg-amber-500/20 text-amber-600 dark:text-amber-400';
      default: return 'bg-gray-500/20 text-gray-600 dark:text-gray-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Contact Book</h1>
          <p className="text-muted-foreground">
            Personal contact intelligence — {total} contacts
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowImport(!showImport)}>
            <Upload className="mr-2 h-4 w-4" /> Import CSV
          </Button>
          <Button variant="outline" size="sm" onClick={fetchContacts}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
        </div>
      </div>

      {/* Feedback */}
      {message && (
        <div className={`rounded-lg border p-3 flex items-center gap-2 ${
          message.type === 'success'
            ? 'border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-400'
            : 'border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          <span className="text-sm">{message.text}</span>
        </div>
      )}

      {/* CSV Import Panel */}
      {showImport && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Import Contacts from CSV</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              CSV columns: phone, name, relation, notes, company, personality_hint, platform
            </p>
            <Textarea
              placeholder={'phone,name,relation,notes,company,personality_hint,platform\n01711234567,Ahmed,client,Regular buyer,ABC Corp,formal,whatsapp'}
              rows={6}
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
            />
            <div className="flex gap-2">
              <Button onClick={handleImport} disabled={importing || !csvText.trim()}>
                {importing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                Import
              </Button>
              <Button variant="ghost" onClick={() => setShowImport(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Search & Filter */}
      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by name, phone, company..."
            className="pl-10"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          className="rounded-md border bg-background px-3 py-2 text-sm"
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
        >
          <option value="">All Platforms</option>
          <option value="whatsapp">WhatsApp</option>
          <option value="facebook">Facebook</option>
        </select>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Contact List */}
      {!loading && contacts.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Users className="mx-auto mb-4 h-12 w-12 opacity-50" />
            <p>No contacts found</p>
          </CardContent>
        </Card>
      )}

      {!loading && contacts.length > 0 && (
        <div className="grid gap-3">
          {contacts.map((c) => (
            <Card key={c.id} className="hover:border-primary/30 transition-colors">
              <CardContent className="py-4">
                {editing?.id === c.id ? (
                  /* Edit Mode */
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label className="text-xs">Name</Label>
                        <Input
                          value={editing.name || ''}
                          onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                        />
                      </div>
                      <div>
                        <Label className="text-xs">Relation</Label>
                        <select
                          className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                          value={editing.relation || 'unknown'}
                          onChange={(e) => setEditing({ ...editing, relation: e.target.value })}
                        >
                          <option value="unknown">Unknown</option>
                          <option value="client">Client</option>
                          <option value="vip">VIP</option>
                          <option value="friend">Friend</option>
                          <option value="family">Family</option>
                          <option value="employee">Employee</option>
                        </select>
                      </div>
                      <div>
                        <Label className="text-xs">Company</Label>
                        <Input
                          value={editing.company || ''}
                          onChange={(e) => setEditing({ ...editing, company: e.target.value })}
                        />
                      </div>
                      <div>
                        <Label className="text-xs">Personality Hint</Label>
                        <Input
                          placeholder="e.g. formal, strict, friendly"
                          value={editing.personality_hint || ''}
                          onChange={(e) => setEditing({ ...editing, personality_hint: e.target.value })}
                        />
                      </div>
                    </div>
                    <div>
                      <Label className="text-xs">Notes</Label>
                      <Textarea
                        rows={2}
                        value={editing.notes || ''}
                        onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleSave}>
                        <Save className="mr-1 h-3 w-3" /> Save
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                        <X className="mr-1 h-3 w-3" /> Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  /* View Mode */
                  <div className="flex items-start justify-between">
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-base">
                          {c.name || c.phone}
                        </span>
                        <Badge variant="outline" className={relationColor(c.relation)}>
                          {c.relation}
                        </Badge>
                        {c.interest_level && c.interest_level !== 'unknown' && (
                          <Badge variant="outline" className={interestColor(c.interest_level)}>
                            {c.interest_level}
                          </Badge>
                        )}
                        <Badge variant="outline" className="text-xs">
                          {c.platform}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Phone className="h-3 w-3" /> {c.phone}
                        </span>
                        {c.company && (
                          <span className="flex items-center gap-1">
                            <Building2 className="h-3 w-3" /> {c.company}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <MessageCircle className="h-3 w-3" /> {c.interaction_count} msgs
                        </span>
                      </div>
                      {c.personality_hint && (
                        <p className="text-sm text-muted-foreground">
                          <UserCheck className="inline h-3 w-3 mr-1" />
                          Hint: {c.personality_hint}
                        </p>
                      )}
                      {c.notes && (
                        <p className="text-sm text-muted-foreground truncate max-w-lg">
                          Notes: {c.notes}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-1 ml-3">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={() => setEditing({ ...c })}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-red-500 hover:text-red-600"
                        onClick={() => handleDelete(c.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
