import Link from "next/link";
import { HeroCosmos, RingedPlanet, Sparkle, Sticker, SunArch, Tape, TapePiece } from "@/components/cosmos";
import { Card } from "@/components/ui";
import { ABOUT } from "@/content/about";

export const metadata = { title: "About" };

export default function AboutPage() {
  const { hero, how, showcase, faq, cta } = ABOUT;
  return (
    <>
      {/* hero */}
      <section className="relative overflow-hidden pb-20 pt-6 text-center md:pt-10">
        <HeroCosmos planet={false} />
        <div className="container-x relative z-10">
          <SunArch className="rise relative mx-auto -mb-9 block h-[150px] w-[300px] max-w-[80vw] sm:-mb-11 sm:h-[170px] sm:w-[340px]" />
          <h1 className="display display-1 rise relative mx-auto max-w-[13ch]">{hero.title}</h1>
          <div className="rise-2 mt-6"><span className="badge">{hero.eyebrow}</span></div>
          <p className="lede rise-3 mx-auto mt-7">{hero.sub}</p>
          <div className="rise-3 mt-10 flex flex-wrap justify-center gap-4">
            <Link className="btn btn-primary" href="/">Open the studio</Link>
            <a className="btn btn-ghost" href="#how">How it works</a>
          </div>
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="section">
        <div className="container-x">
          <div className="mx-auto mb-12 max-w-[40rem] text-center">
            <p className="eyebrow">the method</p>
            <h2 className="title">{how.title}</h2>
          </div>
          <ol className="grid gap-8 md:grid-cols-3">
            {how.steps.map((s) => (
              <li key={s.n}>
                <Card bar={s.bar} lift className="h-full">
                  <div className="flex h-full flex-col p-7 pb-8">
                    <span className="display text-[3.25rem] leading-none" style={{ color: "var(--peach)" }}>{s.n}</span>
                    <h3 className="mt-4 font-display text-[1.6rem] font-black text-charcoal">{s.name}</h3>
                    <p className="mt-3 text-espresso">{s.body}</p>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <Tape />

      {/* showcase */}
      <section className="section band-parch overflow-hidden">
        <RingedPlanet className="bob hide-sm right-[4%] top-10 w-[132px]" />
        <Sparkle className="drift hide-sm left-[6%] top-16 w-6" color="var(--rust)" />
        <div className="container-x relative z-10">
          <div className="mb-14 max-w-[42rem]">
            <p className="eyebrow">the corpus</p>
            <h2 className="display display-2">{showcase.title}</h2>
            <p className="lede mt-5">{showcase.sub}</p>
          </div>
          <ul className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            {showcase.images.map((im) => (
              <li key={im.src} className="relative" style={{ transform: `rotate(${im.tilt}deg)` }}>
                <TapePiece style={{ top: -12, left: "50%", marginLeft: -56, transform: `rotate(${-im.tilt * 1.5}deg)` }} />
                <figure className="card m-0 p-3 pb-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={im.src} alt={`${im.caption} from the reference corpus`} loading="lazy"
                    className="aspect-[4/5] w-full rounded-[6px] object-cover" />
                  <figcaption className="meta mt-3 text-center">{im.caption}</figcaption>
                </figure>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* faq */}
      <section className="section">
        <div className="container-narrow">
          <div className="mb-8 text-center">
            <p className="eyebrow">answers</p>
            <h2 className="title">{faq.title}</h2>
          </div>
          <div className="border-t border-dashed" style={{ borderColor: "var(--rule)" }}>
            {faq.items.map(([q, a]) => (
              <details key={q} className="faq">
                <summary>
                  <span className="font-display text-[1.3rem] font-bold text-charcoal">{q}</span>
                  <svg className="plus h-6 w-6" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v16M4 12h16" stroke="var(--cta)" strokeWidth="2.5" strokeLinecap="round" /></svg>
                </summary>
                <p className="pb-6 pr-10 text-espresso">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* cta */}
      <section className="container-x">
        <div className="card relative overflow-hidden px-6 py-14 text-center md:py-16" style={{ background: "var(--parch)" }}>
          <Sticker top="COSMOGON" script="Labs" big="Mk I" className="drift hide-sm right-8 top-6 w-[112px]" />
          <Sparkle className="bob left-10 top-10 w-6" color="var(--teal)" />
          <h2 className="display display-2 relative z-10">{cta.title}</h2>
          <p className="lede relative z-10 mx-auto mt-4">{cta.sub}</p>
          <Link className="btn btn-primary relative z-10 mt-8" href="/">Start in the studio</Link>
        </div>
        <p className="mt-6 text-center text-[0.85rem] text-muted">
          <Link className="underline hover:text-sienna" href="/evidence">See the measured evidence →</Link>
        </p>
      </section>
    </>
  );
}
