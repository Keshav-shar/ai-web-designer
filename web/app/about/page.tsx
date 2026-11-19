import { ABOUT_HTML, ABOUT_META } from "@/content/about.generated";

export const metadata = { title: "About" };

/**
 * Composed by our own engine (tools/build_shell.py): the dreamy-ethereal family's layout decisions, palette,
 * type and folder imagery, with the app's copy from contracts/about_copy.json. The HTML passed worker/validate.py
 * (no scripts, no handlers, no external URLs) before it was written, so it is rendered as is.
 */
export default function AboutPage() {
  return (
    <>
      <div dangerouslySetInnerHTML={{ __html: ABOUT_HTML }} />
      <p className="container-x mt-6 text-[13px] text-muted">
        This page was composed by the engine from the {ABOUT_META.family} family ({ABOUT_META.fonts.join(" / ")},{" "}
        {ABOUT_META.images} folder images, {ABOUT_META.sections.length} sections).
      </p>
    </>
  );
}
