import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // The "N" dev-tools indicator floats bottom-left and collides with
  // our CTAs/toasts — turn it off.
  devIndicators: false,
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
};

export default nextConfig;
