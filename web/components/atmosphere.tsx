/** L0 + L3 of the app itself, straight from the dreamy family's cues: pastel mesh gradients, blur, film grain,
 *  slow floating motion. Colours are the lab's decorative swatches (--visual-*), never hard-coded. */

export function MeshBackground() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-bg">
      <div
        className="absolute -left-[20%] -top-[25%] h-[75vmax] w-[75vmax] rounded-full opacity-80 blur-[90px]"
        style={{ background: "radial-gradient(circle at 40% 40%, var(--visual-1), transparent 62%)", animation: "drift-a 46s ease-in-out infinite alternate" }}
      />
      <div
        className="absolute -right-[25%] top-[5%] h-[70vmax] w-[70vmax] rounded-full opacity-75 blur-[100px]"
        style={{ background: "radial-gradient(circle at 50% 50%, var(--visual-2), transparent 60%)", animation: "drift-b 58s ease-in-out infinite alternate" }}
      />
      <div
        className="absolute bottom-[-35%] left-[15%] h-[70vmax] w-[70vmax] rounded-full opacity-70 blur-[110px]"
        style={{ background: "radial-gradient(circle at 50% 50%, var(--visual-4), transparent 62%)", animation: "drift-a 64s ease-in-out infinite alternate-reverse" }}
      />
      <div className="absolute inset-0 bg-[radial-gradient(120%_80%_at_50%_0%,transparent_40%,var(--bg)_100%)] opacity-60" />
    </div>
  );
}

const NOISE =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.6'/></svg>\")";

export function Grain() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-50 opacity-[0.07] mix-blend-multiply"
      style={{ backgroundImage: NOISE }}
    />
  );
}
