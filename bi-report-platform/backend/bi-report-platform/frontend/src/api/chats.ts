import { api } from "./client";
import type { ChatResult } from "./types";

/** A saved chat, as listed in the chat history. */
export interface ChatSummary {
  id: number;
  title: string;
  /** null is the built-in sample data. */
  source_id: number | null;
  source_name: string;
  model_id: number | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface SavedMessage {
  id: number;
  question: string;
  status: "ok" | "error";
  result: ChatResult | null;
  error: string;
  model_name: string;
  created_at: string;
}

export interface SavedChat extends ChatSummary {
  messages: SavedMessage[];
}

/** Saved chat conversations; each person sees only their own. AI answers can be slow. */
export const chatsApi = {
  list: () => api.get<ChatSummary[]>("/api/chats").then((r) => r.data),
  get: (id: number) => api.get<SavedChat>(`/api/chats/${id}`).then((r) => r.data),
  start: (body: { source_id: number | null; model_id: number | null }) =>
    api.post<SavedChat>("/api/chats", body).then((r) => r.data),
  update: (id: number, body: { title?: string; model_id?: number | null }) =>
    api.patch<ChatSummary>(`/api/chats/${id}`, body).then((r) => r.data),
  remove: (id: number) => api.delete(`/api/chats/${id}`),
  /** Asks the AI model and saves the turn. A failed answer comes back with status "error". */
  send: (id: number, question: string, modelId: number | null) =>
    api.post<SavedMessage>(`/api/chats/${id}/messages`, { question, model_id: modelId }, { timeout: 240000 }).then((r) => r.data),
};
