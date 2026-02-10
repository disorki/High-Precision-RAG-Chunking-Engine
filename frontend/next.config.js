/** @type {import('next').NextConfig} */
const nextConfig = {
    // Required for react-pdf
    webpack: (config) => {
        config.resolve.alias.canvas = false;
        return config;
    },
    // API proxy to backend
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: process.env.API_URL
                    ? `${process.env.API_URL}/api/:path*`
                    : 'http://localhost:8000/api/:path*',
            },
        ];
    },
};

module.exports = nextConfig;
