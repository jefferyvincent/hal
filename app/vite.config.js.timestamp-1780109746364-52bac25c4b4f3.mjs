// vite.config.js
import { defineConfig } from "file:///sessions/funny-cool-fermat/mnt/app/node_modules/vite/dist/node/index.js";
import react from "file:///sessions/funny-cool-fermat/mnt/app/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "node:path";
var __vite_injected_original_dirname = "/sessions/funny-cool-fermat/mnt/app";
var vite_config_default = defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__vite_injected_original_dirname, "./src")
    }
  },
  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/static": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  },
  // Tauri uses the dist/ directory.
  build: {
    target: "es2021",
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true
  },
  clearScreen: false
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvc2Vzc2lvbnMvZnVubnktY29vbC1mZXJtYXQvbW50L2FwcFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiL3Nlc3Npb25zL2Z1bm55LWNvb2wtZmVybWF0L21udC9hcHAvdml0ZS5jb25maWcuanNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL3Nlc3Npb25zL2Z1bm55LWNvb2wtZmVybWF0L21udC9hcHAvdml0ZS5jb25maWcuanNcIjtpbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tIFwidml0ZVwiO1xuaW1wb3J0IHJlYWN0IGZyb20gXCJAdml0ZWpzL3BsdWdpbi1yZWFjdFwiO1xuaW1wb3J0IHBhdGggZnJvbSBcIm5vZGU6cGF0aFwiO1xuLy8gSW4gZGV2LCB0aGUgUmVhY3QgYXBwIHJ1bnMgb24gVml0ZSAoZGVmYXVsdCA6MTQyMCB0byBtYXRjaCBUYXVyaSksXG4vLyBhbmQgcHJveGllcyBXZWJTb2NrZXQgKyBIVFRQIGZldGNoZXMgdG8gdGhlIEZhc3RBUEkgc2VydmVyIG9uIDo4MDAwLlxuLy8gSW4gcHJvZHVjdGlvbiAod2hldGhlciB3cmFwcGVkIGluIFRhdXJpIG9yIHNlcnZlZCBieSBGYXN0QVBJKSwgdGhlXG4vLyBidW5kbGVkIGFzc2V0cyBzaXQgYWxvbmdzaWRlIHNlcnZlci5weSBhbmQgdGhlIHNhbWUtb3JpZ2luIC93cyBwYXRoIGlzXG4vLyBoaXQgZGlyZWN0bHkuXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoe1xuICAgIHBsdWdpbnM6IFtyZWFjdCgpXSxcbiAgICByZXNvbHZlOiB7XG4gICAgICAgIGFsaWFzOiB7XG4gICAgICAgICAgICBcIkBcIjogcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgXCIuL3NyY1wiKSxcbiAgICAgICAgfSxcbiAgICB9LFxuICAgIHNlcnZlcjoge1xuICAgICAgICBwb3J0OiAxNDIwLFxuICAgICAgICBzdHJpY3RQb3J0OiB0cnVlLFxuICAgICAgICBwcm94eToge1xuICAgICAgICAgICAgXCIvd3NcIjoge1xuICAgICAgICAgICAgICAgIHRhcmdldDogXCJ3czovL2xvY2FsaG9zdDo4MDAwXCIsXG4gICAgICAgICAgICAgICAgd3M6IHRydWUsXG4gICAgICAgICAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIFwiL2FwaVwiOiB7XG4gICAgICAgICAgICAgICAgdGFyZ2V0OiBcImh0dHA6Ly9sb2NhbGhvc3Q6ODAwMFwiLFxuICAgICAgICAgICAgICAgIGNoYW5nZU9yaWdpbjogdHJ1ZSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBcIi9zdGF0aWNcIjoge1xuICAgICAgICAgICAgICAgIHRhcmdldDogXCJodHRwOi8vbG9jYWxob3N0OjgwMDBcIixcbiAgICAgICAgICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgIH0sXG4gICAgLy8gVGF1cmkgdXNlcyB0aGUgZGlzdC8gZGlyZWN0b3J5LlxuICAgIGJ1aWxkOiB7XG4gICAgICAgIHRhcmdldDogXCJlczIwMjFcIixcbiAgICAgICAgb3V0RGlyOiBcImRpc3RcIixcbiAgICAgICAgZW1wdHlPdXREaXI6IHRydWUsXG4gICAgICAgIHNvdXJjZW1hcDogdHJ1ZSxcbiAgICB9LFxuICAgIGNsZWFyU2NyZWVuOiBmYWxzZSxcbn0pO1xuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUEyUixTQUFTLG9CQUFvQjtBQUN4VCxPQUFPLFdBQVc7QUFDbEIsT0FBTyxVQUFVO0FBRmpCLElBQU0sbUNBQW1DO0FBUXpDLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQ3hCLFNBQVMsQ0FBQyxNQUFNLENBQUM7QUFBQSxFQUNqQixTQUFTO0FBQUEsSUFDTCxPQUFPO0FBQUEsTUFDSCxLQUFLLEtBQUssUUFBUSxrQ0FBVyxPQUFPO0FBQUEsSUFDeEM7QUFBQSxFQUNKO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDSixNQUFNO0FBQUEsSUFDTixZQUFZO0FBQUEsSUFDWixPQUFPO0FBQUEsTUFDSCxPQUFPO0FBQUEsUUFDSCxRQUFRO0FBQUEsUUFDUixJQUFJO0FBQUEsUUFDSixjQUFjO0FBQUEsTUFDbEI7QUFBQSxNQUNBLFFBQVE7QUFBQSxRQUNKLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxNQUNsQjtBQUFBLE1BQ0EsV0FBVztBQUFBLFFBQ1AsUUFBUTtBQUFBLFFBQ1IsY0FBYztBQUFBLE1BQ2xCO0FBQUEsSUFDSjtBQUFBLEVBQ0o7QUFBQTtBQUFBLEVBRUEsT0FBTztBQUFBLElBQ0gsUUFBUTtBQUFBLElBQ1IsUUFBUTtBQUFBLElBQ1IsYUFBYTtBQUFBLElBQ2IsV0FBVztBQUFBLEVBQ2Y7QUFBQSxFQUNBLGFBQWE7QUFDakIsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
