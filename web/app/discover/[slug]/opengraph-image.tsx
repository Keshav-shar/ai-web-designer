import { POSTS, postBySlug } from "@/content/discover";
import { OG_SIZE, ogCard } from "@/lib/og";

export const alt = "Cosmogon Labs update";
export const size = OG_SIZE;
export const contentType = "image/png";
export const generateStaticParams = () => POSTS.map((p) => ({ slug: p.slug }));

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const post = postBySlug((await params).slug);
  return ogCard(post?.title ?? "Cosmogon Labs", post ? `update · ${post.date}` : "update");
}
