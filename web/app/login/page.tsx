import { Display, Eyebrow, GlassCard } from "@/components/ui";
import { LoginForm } from "./login-form";

export const metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string; error?: string }> }) {
  const sp = await searchParams;
  const next = sp.next?.startsWith("/") && !sp.next.startsWith("//") ? sp.next : "/studio";
  return (
    <section className="container-x grid min-h-[70dvh] place-items-center py-20">
      <GlassCard className="w-full max-w-md md:p-10">
        <Eyebrow>invite only</Eyebrow>
        <Display as="h1" step={6}>Sign in</Display>
        <p className="mt-3 text-muted">Use the email your invite was sent to.</p>
        {sp.error && <p role="alert" className="mt-4 rounded-2xl border border-line bg-surface px-4 py-3 text-ink">{sp.error}</p>}
        <LoginForm next={next} />
      </GlassCard>
    </section>
  );
}
