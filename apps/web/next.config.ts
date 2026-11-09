import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  poweredByHeader: false,
  experimental: { cpus: 2 },
};

export default function config(phase: string): NextConfig {
  if (phase !== PHASE_DEVELOPMENT_SERVER || process.env.APP_ENV !== "local") return nextConfig;
  return {
    ...nextConfig,
    // Embedded previews can deliver relative API requests to the web port.
    // Route them through the canonical gateway, retaining its origin checks.
    rewrites: async () => [{ source: "/api/v1/:path*", destination: "http://127.0.0.1:3000/api/v1/:path*" }],
  };
}
