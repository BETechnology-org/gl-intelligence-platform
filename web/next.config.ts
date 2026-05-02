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
  // Backward-compat for the legacy Flask service URL: /app served
  // GL_Intelligence_Platform_6.html. The new product lives at /dashboard;
  // 308-redirect keeps existing bookmarks + the deck CTA working.
  async redirects() {
    return [
      { source: "/app", destination: "/dashboard", permanent: true },
      { source: "/app/:path*", destination: "/dashboard/:path*", permanent: true },
    ];
  },
};

export default nextConfig;
