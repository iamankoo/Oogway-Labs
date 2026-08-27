export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export type MessageRole = "user" | "assistant" | "system";

export interface Source {
  source_id: string;
  source_type: "podcast" | "newsletter";
  title: string;
  guest: string | null;
  published_at: string | null;
  source_url: string | null;
  excerpt: string;
  relevance: number;
}

export interface Message {
  id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  sources: Source[];
  grounded: boolean;
}

export interface GenerationError {
  code: string;
  message: string;
}

export interface MessageCreateResponse {
  message: Message;
  assistant_message: Message | null;
  session: Session;
  generation_error: GenerationError | null;
}

export interface RetryResponse {
  assistant_message: Message | null;
  session: Session;
  generation_error: GenerationError | null;
}

export type LlmProvider = "ollama" | "cloud";

export interface ProviderStatus {
  provider: LlmProvider;
  model: string;
}
