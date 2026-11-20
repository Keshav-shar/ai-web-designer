/** The paper the whole app is printed on: a fixed linen dot weave under everything, film grain over everything
 *  (both pointer-events: none; the grain is a multiply overlay so it never lowers text contrast meaningfully). */

export function Linen() {
  return <div aria-hidden="true" className="linen" />;
}

export function Grain() {
  return <div aria-hidden="true" className="grain" />;
}
