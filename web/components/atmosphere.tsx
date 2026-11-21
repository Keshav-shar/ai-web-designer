/** Print grain over the whole app (pointer-events: none; a light multiply overlay that never lowers text contrast
 *  meaningfully). */
export function Grain() {
  return <div aria-hidden="true" className="grain" />;
}
