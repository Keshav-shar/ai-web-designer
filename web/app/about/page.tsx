import Link from "next/link";
import { Poster, Strip, TapePiece, Texture } from "@/components/cosmos";
import { BARS, Card } from "@/components/ui";
import { ABOUT } from "@/content/about";

export const metadata = { title: "About" };

export default function AboutPage() {
  const { hero, how, showcase, faq, cta } = ABOUT;
  return (
    <>
      {/* hero: the retro web kit's split, lockup left, framed print right */}
      <section className="container-x pb-16 pt-12 md:pb-24 md:pt-16">
        <div className="grid items-center gap-12 md:grid-cols-[1.35fr_1fr] md:gap-0">
          <div className="rise md:pr-14">
            <span className="badge">{hero.eyebrow}</span>
            <h1 className="display display-1 stacked mt-9 max-w-[13ch]">{hero.title}</h1>
            <p className="lede mt-9">{hero.sub}</p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Link className="btn btn-primary" href="/">Open the studio</Link>
              <a className="btn btn-ghost" href="#how">How it works</a>
            </div>
          </div>
          <div className="rise-2 hide-sm md:border-l-2 md:border-ink md:pl-14">
            <Poster name="rings" caption="Plate 02 · Rings" artClassName="aspect-[4/5]" position="30% center" />
          </div>
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="section band-sand border-y-2 border-ink">
        <div className="container-x">
          <div className="mb-12 max-w-[40rem]">
            <p className="eyebrow">the method</p>
            <h2 className="title">{how.title}</h2>
          </div>
          <ol className="grid gap-8 md:grid-cols-3">
            {how.steps.map((s, i) => (
              <li key={s.n}>
                <Card bar={BARS[i % BARS.length]} lift className="h-full">
                  <div className="flex h-full flex-col p-7 pb-8">
                    <span className="inline-caps text-[1rem] tracking-[.2em] text-rust">Step {s.n}</span>
                    <h3 className="display stacked-sm mt-3 text-[2.4rem]">{s.name}</h3>
                    <p className="mt-4">{s.body}</p>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* showcase */}
      <section className="section overflow-hidden">
        <div className="container-x">
          <div className="mb-14 grid items-end gap-10 md:grid-cols-[1.6fr_1fr]">
            <div>
              <p className="eyebrow">the corpus</p>
              <h2 className="display display-2">{showcase.title}</h2>
              <p className="lede mt-5">{showcase.sub}</p>
            </div>
            <Texture name="tiles" className="hide-sm h-[180px] border-2 border-ink" position="center 30%" />
          </div>
          <ul className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            {showcase.images.map((im) => (
              <li key={im.src} className="relative" style={{ transform: `rotate(${im.tilt * 0.5}deg)` }}>
                <TapePiece style={{ top: -12, left: "50%", marginLeft: -52, transform: `rotate(${-im.tilt}deg)` }} />
                <figure className="card m-0 p-3 pb-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={im.src} alt={`${im.caption} from the reference corpus`} loading="lazy"
                    className="aspect-[4/5] w-full border-2 border-ink object-cover" />
                  <figcaption className="meta mt-3 text-center">{im.caption}</figcaption>
                </figure>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <Strip />

      {/* faq */}
      <section className="section">
        <div className="container-narrow">
          <div className="mb-8">
            <p className="eyebrow">answers</p>
            <h2 className="title">{faq.title}</h2>
          </div>
          <div className="border-t-2 border-ink">
            {faq.items.map(([q, a]) => (
              <details key={q} className="faq">
                <summary>
                  <span className="font-display text-[1.35rem] font-bold text-forest">{q}</span>
                  <svg className="plus h-6 w-6" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v16M4 12h16" stroke="var(--cta)" strokeWidth="2.5" strokeLinecap="round" /></svg>
                </summary>
                <p className="pb-6 pr-10">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* cta: a forest panel beside a print, text never on the image. Senku peeks in at the bottom-right corner: cut
          by the window's right edge, his lower edge tucked behind the footer's top border (main and the footer are both
          z-10, and the footer paints later). On wide screens he overlaps only the card's stripes panel. */}
      <div className="relative pb-12 md:pb-0" style={{ overflowX: "clip" }}>
        <section className="container-x">
          <div className="card grid overflow-hidden md:grid-cols-[1.5fr_1fr]">
            <div className="band-forest px-7 py-14 md:px-12 md:py-16">
              <h2 className="display display-2" style={{ color: "var(--cream)" }}>{cta.title}</h2>
              <p className="lede mt-4" style={{ color: "rgba(251,245,239,.9)" }}>{cta.sub}</p>
              <Link className="btn btn-primary mt-8" href="/">Start in the studio</Link>
            </div>
            <Texture name="stripes" className="hide-sm border-l-2 border-ink" position="70% center" />
          </div>
          <p className="mt-8 text-center text-[0.9rem] text-muted">
            <Link className="underline hover:text-cta" href="/evidence">See the measured evidence →</Link>
          </p>
        </section>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/about/senku-peek.webp" alt="" aria-hidden="true" width={773} height={765} loading="lazy"
          className="pointer-events-none absolute right-0 z-20 h-auto w-[clamp(150px,22vw,330px)] translate-x-[22%] select-none"
          style={{ bottom: "-110px", WebkitMaskImage: "linear-gradient(to bottom, transparent 0, #000 16%)",
            maskImage: "linear-gradient(to bottom, transparent 0, #000 16%)" }} />
      </div>
    </>
  );
}
