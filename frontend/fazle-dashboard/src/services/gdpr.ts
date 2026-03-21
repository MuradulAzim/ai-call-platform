import { apiGet, apiPost } from './api';

export interface GdprRequest {
  id: string;
  request_type: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface UserConsent {
  terms_accepted: boolean;
  privacy_accepted: boolean;
  accepted_at: string | null;
}

export interface UserDataExport {
  status: string;
  request_id: string;
  filename: string;
  data: Record<string, unknown>;
}

export const gdprService = {
  getMyData: () => apiGet<Record<string, unknown>>('/gdpr/me'),

  exportMyData: () => apiPost<UserDataExport>('/gdpr/export'),

  deleteMyData: () => apiPost<{ status: string; message: string; request_id: string; deleted_from: string[] }>('/gdpr/delete'),

  getRequests: () => apiGet<{ requests: GdprRequest[] }>('/gdpr/status'),

  getConsent: () => apiGet<UserConsent>('/gdpr/consent'),

  saveConsent: (terms: boolean, privacy: boolean) =>
    apiPost<{ status: string; consent: UserConsent }>('/gdpr/consent', { terms, privacy }),
};
