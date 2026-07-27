import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// React Fast Refresh와 TypeScript 변환을 사용하는 Vite 설정입니다.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
  },
});
