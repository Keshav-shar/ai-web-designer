import { ImageResponse } from "next/og";

export const OG_SIZE = { width: 1200, height: 630 };

/** 1200x630 share card in the Cosmogon palette (Discover and social previews need a large image). */
export function ogCard(title: string, kicker: string) {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#FBF5EF", border: "18px solid #0F4A3E", padding: "64px 72px", color: "#13201B" }}>
        <div style={{ display: "flex", fontSize: 30, letterSpacing: 6, textTransform: "uppercase", color: "#C9361C" }}>{kicker}</div>
        <div style={{ display: "flex", fontSize: title.length > 70 ? 56 : 68, fontWeight: 700, lineHeight: 1.1, color: "#0F4A3E" }}>{title}</div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 28 }}>
          <span style={{ background: "#F2B632", padding: "8px 18px", border: "3px solid #13201B" }}>Cosmogon Labs</span>
          <span>founded by Keshav Sharma</span>
        </div>
      </div>
    ),
    OG_SIZE,
  );
}
