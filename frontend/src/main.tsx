import React from "react";
import ReactDOM, { createRoot } from "react-dom/client";
import { unstableSetRender } from "antd/es/config-provider/UnstableContext";
import { ConfigProvider } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./app/App";
import "./styles.css";

// antd's static message/notification need this to render under React 19
unstableSetRender((node, container) => {
  const c = container as HTMLElement & { _reactRoot?: ReturnType<typeof createRoot> };
  c._reactRoot ||= createRoot(container);
  c._reactRoot.render(node);
  return async () => {
    await Promise.resolve();
    c._reactRoot?.unmount();
    delete c._reactRoot;
  };
});

const queryClient = new QueryClient({
  defaultOptions: {
    // Keep running while the browser reports offline, so orders reach the offline queue and cached menus load.
    mutations: { networkMode: "always" },
    queries: {
      networkMode: "always",
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => { void navigator.serviceWorker.register("/sw.js"); });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={{ token: { colorPrimary: "#ff6a00", colorInfo: "#06214a", fontFamily: '"Inter", "Segoe UI", sans-serif', borderRadius: 10 } }}>
        <App />
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
