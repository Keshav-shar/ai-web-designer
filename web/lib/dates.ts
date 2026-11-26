/** "26 November 2026" from "2026-11-26", fixed to UTC so server and build agree. */
export const fmtDate = (d: string) =>
  new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
