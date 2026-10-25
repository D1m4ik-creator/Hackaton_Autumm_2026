import { request } from './client'

export interface ShareLink {
  id: string
  label: string | null
  createdByLogin: string
  createdAt: string
  expiresAt: string
  revokedAt: string | null
  active: boolean
}

export interface ShareLinkCreated extends ShareLink {
  token: string
}

export const listShareLinks = () => request<ShareLink[]>('/share-links')
export const createShareLink = (data: { label?: string; expiresInDays?: number }) =>
  request<ShareLinkCreated>('/share-links', { method: 'POST', data })
export const revokeShareLink = (id: string) => request(`/share-links/${encodeURIComponent(id)}`, { method: 'DELETE' })
