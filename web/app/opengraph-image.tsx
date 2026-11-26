import { OG_SIZE, ogCard } from "@/lib/og";

export const alt = "Cosmogon Labs, a taste engine for the web";
export const size = OG_SIZE;
export const contentType = "image/png";

export default function Image() {
  return ogCard("Describe a site. Get its taste.", "a taste engine for the web");
}
