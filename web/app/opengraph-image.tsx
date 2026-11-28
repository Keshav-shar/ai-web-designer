import { OG_SIZE, ogCard } from "@/lib/og";

export const alt = "Cosmogon Labs: beyond generation, towards visual intelligence";
export const size = OG_SIZE;
export const contentType = "image/png";

export default function Image() {
  return ogCard("Beyond generation. Towards visual intelligence.", "independent R&D · visual intelligence");
}
