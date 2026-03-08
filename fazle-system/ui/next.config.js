/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/fazle/:path*",
        destination: `${process.env.FAZLE_API_URL || "http://fazle-api:8100"}/fazle/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
