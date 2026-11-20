// Prompt rules (lib/prompt.ts): normalization, the 200-character limit and the "a few words" check.
//   npm run check:prompt
import { MAX_PROMPT, Prompt, normalizePrompt } from "../lib/prompt.ts";

const ok = (s: string) => Prompt.safeParse(s).success;
const cases: [string, boolean, string][] = [
  ["heya", true, "a greeting is accepted (the engine still builds something)"],
  ["bakery", true, "a single domain word"],
  ["  a  natural wine bar\n\nin Lisbon,\thand-drawn  ", true, "whitespace and newlines collapse"],
  ["café à Paris, minimal", true, "accents"],
  ["東京の茶室, wabi-sabi", true, "non-Latin script"],
  ["🍕 pizza place, loud", true, "emoji + words"],
  ["<script>alert(1)</script> bakery", true, "HTML is just text here (escaped downstream)"],
  ["x".repeat(MAX_PROMPT), true, "exactly 200"],
  ["x".repeat(MAX_PROMPT + 1), false, "201 is refused"],
  ["ab", false, "too short"],
  ["🍕🍕🍕", false, "emoji only"],
  ["!!! ??? ...", false, "punctuation only"],
  ["​​​hi​", false, "zero-width padding does not count"],
];
let bad = 0;
for (const [input, expect, why] of cases) {
  const got = ok(input);
  if (got !== expect) bad++;
  console.log(`${got === expect ? "ok  " : "FAIL"} ${why}: ${JSON.stringify(normalizePrompt(input)).slice(0, 60)} -> ${got}`);
}
if (normalizePrompt("a\u0000b​c  d") !== "abc d") {
  bad++;
  console.log("FAIL control / zero-width characters are not stripped");
}
process.exit(bad ? 1 : 0);
