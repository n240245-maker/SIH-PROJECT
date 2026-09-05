import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "8000", pathname: "/api/v2/geo-evidence/**" },
      { protocol: "http", hostname: "127.0.0.1", port: "8000", pathname: "/api/v2/geo-evidence/**" },
    ],
  },
};

export default nextConfig;
