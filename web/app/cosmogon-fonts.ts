// Cosmogon Labs type system (hand-designed; self-hosted by next/font).
import { DM_Sans, Fraunces, Oswald } from "next/font/google";

/** Display: a soft, chunky 1970s serif ("Retro Brown" in the 70s-retro type specimens) for headlines and the wordmark. */
export const displayFont = Fraunces({ subsets: ["latin"], weight: "variable", style: ["normal", "italic"], axes: ["SOFT", "WONK", "opsz"], variable: "--nf-display", display: "swap" });
/** UI: a condensed grotesque in capitals for navigation, labels and buttons (the retro web kit's nav). */
export const uiFont = Oswald({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--nf-ui", display: "swap" });
/** Body: neutral humanist sans for running text. */
export const bodyFont = DM_Sans({ subsets: ["latin"], weight: ["400", "500", "700"], variable: "--nf-body", display: "swap" });

export const fontVars = [displayFont, uiFont, bodyFont].map((f) => f.variable).join(" ");
