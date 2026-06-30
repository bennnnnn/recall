import { WebPreviewCodeBlock } from "@/components/WebPreviewCodeBlock";

type Props = { content: string; title?: string };

/** @deprecated Prefer WebPreviewCodeBlock directly. */
export function HTMLBlock({ content }: Props) {
  return <WebPreviewCodeBlock code={content} lang="html" />;
}
