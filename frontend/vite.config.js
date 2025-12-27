import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
    plugins: [
        vue(),
        VitePWA({
            registerType: 'autoUpdate',
            manifest: {
                name: 'PikPak Swipe',
                short_name: 'Swipe',
                description: '影视资源筛选助手',
                theme_color: '#1989fa',
                background_color: '#f7f8fa',
                display: 'standalone',
                icons: [
                    {
                        src: '/icon-192.png',
                        sizes: '192x192',
                        type: 'image/png'
                    },
                    {
                        src: '/icon-512.png',
                        sizes: '512x512',
                        type: 'image/png'
                    }
                ]
            },
            workbox: {
                globPatterns: ['**/*.{js,css,html,png,svg,ico}']
            }
        })
    ],
    server: {
        host: '0.0.0.0',
        port: 3000,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true
            },
            '/previews': {
                target: 'http://localhost:8000',
                changeOrigin: true
            }
        }
    }
})
