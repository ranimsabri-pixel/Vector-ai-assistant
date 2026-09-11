"use client";

import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

import "highlight.js/styles/github-dark.css";

// Schema de sanitization enrichi (autorise className pour syntax highlight)
const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code || []), "className"],
    span: [...(defaultSchema.attributes?.span || []), "className"],
    a: [
      ...(defaultSchema.attributes?.a || []),
      ["target", "_blank"],
      ["rel", "noopener noreferrer"],
    ],
  },
};

// Composants personnalises (types Components de react-markdown v10)
const markdownComponents: Components = {
  h1({ children, ...props }) {
    return (
      <h1 className="text-xl font-bold text-foreground mt-4 mb-2" {...props}>
        {children}
      </h1>
    );
  },
  h2({ children, ...props }) {
    return (
      <h2 className="text-lg font-bold text-foreground mt-3 mb-2" {...props}>
        {children}
      </h2>
    );
  },
  h3({ children, ...props }) {
    return (
      <h3 className="text-base font-semibold text-foreground mt-3 mb-1.5" {...props}>
        {children}
      </h3>
    );
  },
  p({ children, ...props }) {
    return (
      <p className="text-foreground leading-relaxed mb-2 last:mb-0" {...props}>
        {children}
      </p>
    );
  },
  strong({ children, ...props }) {
    return (
      <strong className="font-semibold text-foreground" {...props}>
        {children}
      </strong>
    );
  },
  em({ children, ...props }) {
    return (
      <em className="italic text-foreground" {...props}>
        {children}
      </em>
    );
  },
  ul({ children, ...props }) {
    return (
      <ul className="list-disc pl-5 space-y-1 my-2 text-foreground" {...props}>
        {children}
      </ul>
    );
  },
  ol({ children, ...props }) {
    return (
      <ol className="list-decimal pl-5 space-y-1 my-2 text-foreground" {...props}>
        {children}
      </ol>
    );
  },
  li({ children, ...props }) {
    return (
      <li className="leading-relaxed" {...props}>
        {children}
      </li>
    );
  },
  a({ href, children, ...props }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2 transition-colors"
        {...props}
      >
        {children}
      </a>
    );
  },
  blockquote({ children, ...props }) {
    return (
      <blockquote
        className="border-l-2 border-emerald-600/50 pl-4 my-3 italic text-muted-foreground"
        {...props}
      >
        {children}
      </blockquote>
    );
  },
  code(props: ComponentPropsWithoutRef<"code">) {
    const { className, children, ...rest } = props;
    const isInline = !className;

    if (isInline) {
      return (
        <code
          className="px-1.5 py-0.5 rounded bg-muted text-emerald-300 text-[0.85em] font-mono"
          {...rest}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...rest}>
        {children}
      </code>
    );
  },
  pre({ children, ...props }) {
    return (
      <pre
        className="my-3 p-3 rounded-lg bg-background border border-border overflow-x-auto text-xs"
        {...props}
      >
        {children}
      </pre>
    );
  },
  table({ children, ...props }) {
    return (
      <div className="my-3 overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm" {...props}>
          {children}
        </table>
      </div>
    );
  },
  thead({ children, ...props }) {
    return (
      <thead className="bg-card border-b border-border" {...props}>
        {children}
      </thead>
    );
  },
  th({ children, ...props }) {
    return (
      <th
        className="px-3 py-2 text-left text-xs font-semibold text-foreground uppercase tracking-wider"
        {...props}
      >
        {children}
      </th>
    );
  },
  td({ children, ...props }) {
    return (
      <td
        className="px-3 py-2 text-sm text-foreground border-t border-border/60"
        {...props}
      >
        {children}
      </td>
    );
  },
  hr(props) {
    return <hr className="my-4 border-border" {...props} />;
  },
};

// Composant principal
type MarkdownRendererProps = {
  content: string;
  className?: string;
};

export function MarkdownRenderer({
  content,
  className = "",
}: MarkdownRendererProps) {
  const wrapperClassName = "prose prose-invert prose-sm max-w-none " + className;

  return (
    <div className={wrapperClassName}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight, [rehypeSanitize, sanitizeSchema]]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}