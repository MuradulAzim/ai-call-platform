/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    const apiUrl = process.env.FAZLE_API_URL || "http://fazle-api:8100";
    return [
      {
        source: "/api/fazle/:path*",
        destination: `${apiUrl}/fazle/:path*`,
      },
      {
        source: "/api/setup-status",
        destination: `${apiUrl}/auth/setup-status`,
      },
      {
        source: "/api/setup",
        destination: `${apiUrl}/auth/setup`,
      },
      {
        source: "/api/admin/:path*",
        destination: `${apiUrl}/auth/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
