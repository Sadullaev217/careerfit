import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

/** The origin of a configured address, or nothing when it isn't set or isn't a valid URL. */
function originOf(address: string | undefined): string[] {
  if (!address) return [];
  try {
    return [new URL(address).origin];
  } catch {
    return [];
  }
}

const supabase = originOf(process.env.NEXT_PUBLIC_SUPABASE_URL);
const posthog = process.env.NEXT_PUBLIC_POSTHOG_TOKEN
  ? originOf(process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com")
  : [];
// PostHog loads its optional extensions from a matching assets host (eu.i -> eu-assets.i).
const posthogAssets = posthog.map((origin) => origin.replace("://eu.i.", "://eu-assets.i.").replace("://us.i.", "://us-assets.i."));

// Where the browser may send requests: the API, Supabase sign-in, and the optional error and analytics
// services. Anything else, including a script injected into the page, is refused.
const connectSources = [
  "'self'",
  ...originOf(process.env.NEXT_PUBLIC_API_URL),
  ...supabase,
  ...originOf(process.env.NEXT_PUBLIC_SENTRY_DSN),
  ...posthog,
  ...posthogAssets,
  ...(isDev ? ["ws:", "http://localhost:*", "http://127.0.0.1:*"] : []),
];

// Without nonces, because Partial Prerendering serves a static shell that a per-request nonce can't reach
// (node_modules/next/dist/docs/01-app/02-guides/content-security-policy.md, "Without Nonces").
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} ${posthogAssets.join(" ")}`.trim(),
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  `connect-src ${connectSources.join(" ")}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  transpilePackages: ["@careerfit/shared"],
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
