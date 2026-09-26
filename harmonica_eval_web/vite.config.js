import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // ★ 产物落在 dist/，★ serve_ui 只负责把那个目录当静态资源发出去
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    // ★ 开发时把 API 代理到 Python 侧；★ 生产构建后不需要它
    proxy: {
      "/view": "http://127.0.0.1:8721",
      "/dataset": "http://127.0.0.1:8721",
      "/command": "http://127.0.0.1:8721",
    },
  },
});
