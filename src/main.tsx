import React from "react";
import ReactDOM from "react-dom/client";
// Separate entry bundles keep the public app independent of workspace styles.
async function bootstrap() {
  const isPublic = /^\/public\/?$/.test(window.location.pathname);
  const { default: App } = isPublic
    ? await import("./public-app/PublicApp")
    : await import("./App");
  if (!isPublic) {
    await import("./styles.css");
    await import("./theme.css");
  }
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}
void bootstrap();
