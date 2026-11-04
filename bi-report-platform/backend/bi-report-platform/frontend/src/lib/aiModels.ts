import type { AIProvider } from "../api/types";

export const PROVIDER_INFO: Record<AIProvider, {
  short: string; color: string; title: string; blurb: string; baseUrlHint: string; modelHint: string; keyHint: string;
}> = {
  ollama: {
    short: "OL", color: "#1A2332", title: "Ollama (local or cloud)",
    blurb: "Local models run on your own server, so questions never leave your network. Models ending in :cloud run on ollama.com.",
    baseUrlHint: "Where Ollama runs. On the same machine: http://localhost:11434",
    modelHint: "e.g. qwen2.5-coder:14b. Pull it first with: ollama pull <model>",
    keyHint: "",
  },
  anthropic: {
    short: "AI", color: "#C15F3C", title: "Claude (Anthropic API)",
    blurb: "Hosted by Anthropic. Needs an API key from console.anthropic.com; usage is billed to that account.",
    baseUrlHint: "",
    modelHint: "claude-opus-5-5 is the most capable; claude-haiku-5-5 is the fastest and cheapest.",
    keyHint: "Starts with sk-ant-. Stored encrypted and never shown again.",
  },
  openai_compatible: {
    short: "API", color: "#2A9D8F", title: "OpenAI-compatible server",
    blurb: "LM Studio, vLLM, llama.cpp server, LocalAI, or any hosted service with the same API.",
    baseUrlHint: "The address ending in /v1, e.g. http://localhost:1234/v1 for LM Studio",
    modelHint: "The model name the server uses",
    keyHint: "Only if the server asks for one. Stored encrypted and never shown again.",
  },
};

/** The model chosen in the Ask box, passed to the question page. */
export interface AskModel {
  id: number;
  name: string;
}

/** The model picked in the Ask box last time, remembered in this browser only. */
const PICK_KEY = "bi_ai_model";

export function rememberedModel(): string | null {
  try { return localStorage.getItem(PICK_KEY); } catch { return null; }
}

export function rememberModel(value: string) {
  try { localStorage.setItem(PICK_KEY, value); } catch { /* storage unavailable: nothing to remember */ }
}
