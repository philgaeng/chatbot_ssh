// SPDX-License-Identifier: Apache-2.0

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for Docker production builds (copies minimal server runtime)
  output: "standalone",
  // API proxy is handled by app/api/v1/[...path]/route.ts (reads TICKETING_API_URL
  // at request time — works with Docker service names without baking into the image).

  // GRM-115: the image optimizer is OFF. Nothing here uses `next/image`, and its endpoint
  // (`/_next/image`) is where next@16.2.6's unauthenticated RCE advisory lived — reachable through
  // nginx's `/_next/` proxy. With this set, Next answers 404 before the optimizer runs
  // (`next-server.js`, `handleNextImageRequest`), so the surface is gone whatever the version.
  // Adding `next/image` later means deciding this again, not silently re-opening the endpoint.
  images: { unoptimized: true },
};

export default nextConfig;
