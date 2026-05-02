import type { NextConfig } from "next";

// `standalone` packs only the files needed to run `node server.js` into
// .next/standalone, which is what we copy into the Docker image. Cuts
// the image to ~150-200 MB vs. ~700 MB shipping all of node_modules.
const nextConfig: NextConfig = {
  output: "standalone",
  images: { unoptimized: true },
  poweredByHeader: false,
  reactStrictMode: true,
  compress: true,
  productionBrowserSourceMaps: false,
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
