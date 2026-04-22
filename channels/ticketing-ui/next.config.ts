import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for Docker production builds (copies minimal server runtime)
  output: "standalone",
};

export default nextConfig;
