import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
// In dev, the React app runs on Vite (default :1420 to match Tauri),
// and proxies WebSocket + HTTP fetches to the FastAPI server on :8000.
// In production (whether wrapped in Tauri or served by FastAPI), the
// bundled assets sit alongside server.py and the same-origin /ws path is
// hit directly.
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "./src"),
        },
    },
    server: {
        port: 1420,
        strictPort: true,
        proxy: {
            "/ws": {
                target: "ws://localhost:8000",
                ws: true,
                changeOrigin: true,
            },
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
            "/static": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
    // Tauri uses the dist/ directory.
    build: {
        target: "es2021",
        outDir: "dist",
        emptyOutDir: true,
        sourcemap: true,
    },
    clearScreen: false,
});
