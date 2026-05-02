import Anthropic from "@anthropic-ai/sdk";

const apiKey = process.env.ANTHROPIC_API_KEY;
const model = process.env.ANTHROPIC_MODEL ?? "claude-sonnet-4-5-20250929";

let _client: Anthropic | null = null;

export function getAnthropic(): Anthropic {
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY not set");
  if (!_client) _client = new Anthropic({ apiKey });
  return _client;
}

export const ANTHROPIC_MODEL = model;

export interface ClassifyJSONOptions {
  system: string;
  prompt: string;
  maxTokens?: number;
}

export async function classifyJSON<T>(opts: ClassifyJSONOptions): Promise<T | null> {
  const res = await getAnthropic().messages.create({
    model,
    max_tokens: opts.maxTokens ?? 800,
    system: opts.system,
    messages: [{ role: "user", content: opts.prompt }],
  });
  const text = res.content
    .filter((b) => b.type === "text")
    .map((b) => (b.type === "text" ? b.text : ""))
    .join("\n")
    .trim();

  // Strip code fences if present
  let cleaned = text;
  if (cleaned.startsWith("```")) {
    const inner = cleaned.split("```");
    cleaned = inner[1] ?? cleaned;
    cleaned = cleaned.replace(/^[a-zA-Z]*\n?/, "");
    cleaned = cleaned.split("```")[0];
  }
  cleaned = cleaned.trim();

  try {
    return JSON.parse(cleaned) as T;
  } catch {
    return null;
  }
}

export async function generateText(opts: {
  system: string;
  prompt: string;
  maxTokens?: number;
}): Promise<string> {
  const res = await getAnthropic().messages.create({
    model,
    max_tokens: opts.maxTokens ?? 2000,
    system: opts.system,
    messages: [{ role: "user", content: opts.prompt }],
  });
  return res.content
    .filter((b) => b.type === "text")
    .map((b) => (b.type === "text" ? b.text : ""))
    .join("\n")
    .trim();
}
