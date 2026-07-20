import type { AppLoadContext, EntryContext } from "react-router";
import { ServerRouter } from "react-router";
import { isbot } from "isbot";
import { renderToReadableStream } from "react-dom/server";

// Cloudflare Workers run on the web-streams React DOM server API
// (renderToReadableStream), not the Node pipeable-stream API. Providing this
// entry explicitly prevents React Router from selecting the @react-router/node
// default entry (renderToPipeableStream), which is undefined in the Workers
// runtime and returns HTTP 500.
export default async function handleRequest(
  request: Request,
  responseStatusCode: number,
  responseHeaders: Headers,
  routerContext: EntryContext,
  _loadContext: AppLoadContext,
) {
  let shellRendered = false;
  const userAgent = request.headers.get("user-agent");

  const body = await renderToReadableStream(
    <ServerRouter context={routerContext} url={request.url} />,
    {
      onError(error: unknown) {
        responseStatusCode = 500;
        // Log streaming rendering errors from inside the shell. Don't log
        // errors encountered during initial shell rendering since they'll
        // reject and get logged in handleDocumentRequest.
        if (shellRendered) {
          console.error(error);
        }
      },
    },
  );
  shellRendered = true;

  // Ensure requests from bots and SPA Mode renders wait for all content to load
  // before responding.
  if ((userAgent && isbot(userAgent)) || routerContext.isSpaMode) {
    await body.allReady;
  }

  responseHeaders.set("Content-Type", "text/html");
  // Google Identity Services opens a sign-in popup that posts the credential
  // back via window.postMessage. "same-origin-allow-popups" keeps the opener
  // relationship so that message is delivered (otherwise browsers may block it).
  responseHeaders.set("Cross-Origin-Opener-Policy", "same-origin-allow-popups");
  return new Response(body, {
    headers: responseHeaders,
    status: responseStatusCode,
  });
}
