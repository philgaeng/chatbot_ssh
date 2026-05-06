import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for Docker production builds (copies minimal server runtime)
  output: "standalone",
  // API proxy is handled by app/api/v1/[...path]/route.ts (reads TICKETING_API_URL
  // at request time — works with Docker service names without baking into the image).
};

export default nextConfig;
