/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy API calls to backend in development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.NEXT_PUBLIC_API_URL 
          ? `${process.env.NEXT_PUBLIC_API_URL}/:path*`
          : 'http://localhost:8000/:path*',
      },
    ];
  },
  
  // Allow images from various sources
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**.googleusercontent.com' },
      { protocol: 'https', hostname: '**.fbcdn.net' },
      { protocol: 'https', hostname: '**.s3.amazonaws.com' },
    ],
  },
};

module.exports = nextConfig;

