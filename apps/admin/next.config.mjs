/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Transpile the shared workspace package (it ships TypeScript source, not built JS).
  transpilePackages: ['@tyndale/shared'],
};

export default nextConfig;
