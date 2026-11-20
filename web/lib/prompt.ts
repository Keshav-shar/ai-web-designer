import { z } from "zod";

/** The studio prompt limit: the textarea, this schema and the jobs.prompt check constraint all use 200. */
export const MAX_PROMPT = 200;

/**
 * Same cleaning as worker/split.py `normalize`: NFKC, drop control / zero-width / format characters,
 * collapse whitespace (newlines included) and trim.
 */
export function normalizePrompt(raw: string): string {
  return raw
    .normalize("NFKC")
    .replace(/[\p{Cc}\p{Cf}]/gu, (c) => (/\s/.test(c) ? " " : ""))
    .replace(/\s+/g, " ")
    .trim();
}

export const Prompt = z
  .string()
  .transform(normalizePrompt)
  .pipe(
    z
      .string()
      .min(3, "Say a little more: what it is and how it should feel.")
      .max(MAX_PROMPT, `Keep it under ${MAX_PROMPT} characters.`)
      .refine((s) => (s.match(/[\p{L}\p{N}]/gu) ?? []).length >= 2, "Describe the site in a few words."),
  );
