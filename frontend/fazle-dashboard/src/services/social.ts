import { apiGet, apiPost } from './api';

export interface SocialStats {
  total_contacts: number;
  whatsapp_messages: number;
  facebook_posts: number;
  pending_scheduled: number;
  active_campaigns: number;
}

export interface SocialContact {
  id: string;
  name: string;
  platform: string;
  identifier: string;
  phone_number?: string;
  profile_link?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SocialMessage {
  id: string;
  direction: string;
  contact_identifier: string;
  content: string;
  message_text?: string;
  ai_response?: string;
  status: string;
  created_at: string;
}

export interface SocialPost {
  id: string;
  post_id: string | null;
  content: string;
  image_url: string | null;
  status: string;
  created_at: string;
}

export interface ScheduledItem {
  id: string;
  action_type: string;
  payload: Record<string, unknown>;
  scheduled_at: string;
  status: string;
  created_at: string;
}

export interface Campaign {
  id: string;
  name: string;
  platform: string;
  campaign_type: string;
  config: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface SocialIntegration {
  id: string;
  platform: string;
  app_id: string;
  app_secret: string;
  access_token: string;
  page_id: string;
  phone_number: string;
  phone_number_id: string;
  waba_id: string;
  verify_token: string;
  webhook_url: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface IntegrationStatus {
  platforms: {
    platform: string;
    connected: boolean;
    webhook_url: string;
    last_message_at: string | null;
  }[];
  service: string;
  version: string;
}

export const socialService = {
  // Stats
  getStats: () => apiGet<SocialStats>('/social/stats'),

  // Integrations
  listIntegrations: () =>
    apiGet<{ integrations: SocialIntegration[] }>('/social/integrations'),
  saveIntegration: (data: Partial<SocialIntegration> & { platform: string }) =>
    apiPost<{ status: string; platform: string }>('/social/integrations/save', data),
  testIntegration: (platform: string) =>
    apiPost<{ connected: boolean; error?: string }>('/social/integrations/test', { platform }),
  enableIntegration: (platform: string) =>
    apiPost<{ status: string }>('/social/integrations/enable', { platform }),
  disableIntegration: (platform: string) =>
    apiPost<{ status: string }>('/social/integrations/disable', { platform }),
  integrationStatus: () =>
    apiGet<IntegrationStatus>('/social/integration/status'),

  // WhatsApp
  whatsappSend: (to: string, message: string, autoReply = false) =>
    apiPost<{ status: string }>('/social/whatsapp/send', { to, message, auto_reply: autoReply }),
  whatsappSchedule: (data: { to: string; message: string; scheduled_at: string }) =>
    apiPost<{ status: string }>('/social/whatsapp/schedule', data),
  whatsappBroadcast: (data: { contacts: string[]; message: string; name?: string }) =>
    apiPost<{ status: string; campaign_id: string }>('/social/whatsapp/broadcast', data),
  whatsappMessages: (limit = 50) =>
    apiGet<{ messages: SocialMessage[] }>(`/social/whatsapp/messages?limit=${limit}`),
  whatsappScheduled: () =>
    apiGet<{ scheduled: ScheduledItem[] }>('/social/whatsapp/scheduled'),

  // Facebook
  facebookPost: (data: { content?: string; prompt?: string; ai_generate?: boolean; image_url?: string; schedule_at?: string }) =>
    apiPost<{ status: string; id: string; content: string }>('/social/facebook/post', data),
  facebookComment: (data: { post_id?: string; comment_id?: string; message?: string; auto_reply?: boolean; original_comment?: string }) =>
    apiPost<{ status: string }>('/social/facebook/comment', data),
  facebookReact: (targetId: string, reactionType = 'LIKE') =>
    apiPost<{ status: string }>('/social/facebook/react', { target_id: targetId, reaction_type: reactionType }),
  facebookPosts: (limit = 50) =>
    apiGet<{ posts: SocialPost[] }>(`/social/facebook/posts?limit=${limit}`),
  facebookScheduled: () =>
    apiGet<{ scheduled: ScheduledItem[] }>('/social/facebook/scheduled'),

  // Contacts
  listContacts: (platform?: string) =>
    apiGet<{ contacts: SocialContact[] }>(`/social/contacts${platform ? `?platform=${platform}` : ''}`),
  addContact: (data: { name: string; platform: string; identifier: string }) =>
    apiPost<{ status: string; contact: SocialContact }>('/social/contacts', data),

  // Campaigns
  listCampaigns: () => apiGet<{ campaigns: Campaign[] }>('/social/campaigns'),
  createCampaign: (data: { name: string; platform: string; campaign_type: string; config?: Record<string, unknown> }) =>
    apiPost<{ status: string; campaign: Campaign }>('/social/campaigns', data),
};
