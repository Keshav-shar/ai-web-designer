// Contract check: a brief produced by the Python worker must parse with the UI's zod schema.
//   npm run check:brief -- ../out/dew/brief.json ../fixtures/brief_dreamy.json
import { readFileSync } from "node:fs";
import { Brief } from "../lib/brief.ts";

const files = process.argv.slice(2);
if (!files.length) {
  console.error("usage: npm run check:brief -- <brief.json> [...]");
  process.exit(2);
}
let bad = 0;
for (const f of files) {
  const r = Brief.safeParse(JSON.parse(readFileSync(f, "utf8")));
  if (r.success) console.log(`ok    ${f}  (${r.data.meta.routed_family}, ${r.data.sections.length} sections, ${r.data.assets.length} assets)`);
  else {
    bad++;
    console.log(`FAIL  ${f}\n${r.error.issues.map((i) => `  ${i.path.join(".")}: ${i.message}`).join("\n")}`);
  }
}
process.exit(bad ? 1 : 0);
