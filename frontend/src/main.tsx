import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";

// Vite가 제공하는 #root 요소에 React 애플리케이션을 연결합니다.
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("React root element was not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
