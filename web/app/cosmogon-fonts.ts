// Cosmogon Labs type system (hand-designed; self-hosted by next/font).
import { DM_Sans, Fraunces, Montserrat, Shrikhand } from "next/font/google";

/** Display: a 1970s high-contrast soft serif for headlines (variable optical size, black weight). */
export const displayFont = Fraunces({ subsets: ["latin"], weight: ["600", "700", "900"], style: ["normal", "italic"], variable: "--nf-display", display: "swap" });
/** UI: geometric mid-century sans, set in wide-tracked capitals for navigation, labels and buttons. */
export const uiFont = Montserrat({ subsets: ["latin"], weight: ["600", "700", "800"], variable: "--nf-ui", display: "swap" });
/** Body: neutral humanist sans for running text. */
export const bodyFont = DM_Sans({ subsets: ["latin"], weight: ["400", "500", "700"], variable: "--nf-body", display: "swap" });
/** Script: the wordmark and badge lettering. */
export const scriptFont = Shrikhand({ subsets: ["latin"], weight: "400", variable: "--nf-script", display: "swap" });

export const fontVars = [displayFont, uiFont, bodyFont, scriptFont].map((f) => f.variable).join(" ");
