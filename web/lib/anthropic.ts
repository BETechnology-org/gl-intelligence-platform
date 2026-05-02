/**
 * Claude client — supports both Anthropic direct API and AWS Bedrock.
 *
 * Bedrock is preferred when AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY are
 * set (no Anthropic API costs — routed via Truffles' AWS infrastructure,
 * matching the legacy gl-intelligence service). Falls back to direct
 * Anthropic API when only ANTHROPIC_API_KEY is set.
 */

import Anthropic from "@anthropic-ai/sdk";
import { AnthropicBedrock } from "@anthropic-ai/bedrock-sdk";

const awsAccessKeyId = process.env.AWS_ACCESS_KEY_ID;
const awsSecretAccessKey = process.env.AWS_SECRET_ACCESS_KEY;
const awsRegion = process.env.AWS_BEDROCK_REGION ?? "ap-south-1";
const anthropicApiKey = process.env.ANTHROPIC_API_KEY;

const useBedrock = !!(awsAccessKeyId && awsSecretAccessKey);

// Bedrock model IDs are different from direct API. Default matches the
// legacy CLAUDE_MODEL=apac.anthropic.claude-sonnet-4-5-20250929-v1:0 used
// by gl_intelligence/api/server.py.
const bedrockModel =
  process.env.CLAUDE_MODEL ?? "apac.anthropic.claude-sonnet-4-5-20250929-v1:0";
const directModel =
  process.env.ANTHROPIC_MODEL ?? "claude-sonnet-4-5-20250929";

export const ANTHROPIC_MODEL = useBedrock ? bedrockModel : directModel;

let _client: Anthropic | AnthropicBedrock | null = null;

export function getClaude(): Anthropic | AnthropicBedrock {
  if (_client) return _client;
  if (useBedrock) {
    _client = new AnthropicBedrock({
      awsAccessKey: awsAccessKeyId!,
      awsSecretKey: awsSecretAccessKey!,
      awsRegion,
    });
  } else {
    if (!anthropicApiKey) {
      throw new Error("Neither AWS Bedrock creds nor ANTHROPIC_API_KEY set");
    }
    _client = new Anthropic({ apiKey: anthropicApiKey });
  }
  return _client;
}

export interface ClassifyJSONOptions {
  system: string;
  prompt: string;
  maxTokens?: number;
}

export async function classifyJSON<T>(opts: ClassifyJSONOptions): Promise<T | null> {
  const client = getClaude();
  const res = await client.messages.create({
    model: ANTHROPIC_MODEL,
    max_tokens: opts.maxTokens ?? 800,
    system: opts.system,
    messages: [{ role: "user", content: opts.prompt }],
  });
  const text = res.content
    .filter((b) => b.type === "text")
    .map((b) => (b.type === "text" ? b.text : ""))
    .join("\n")
    .trim();

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
  const client = getClaude();
  const res = await client.messages.create({
    model: ANTHROPIC_MODEL,
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
