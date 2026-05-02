const { createProxyMiddleware } = require('http-proxy-middleware');
const http = require('http');

module.exports = function(app) {
  const backendTarget = 'http://localhost:8000';

  // SSE endpoint: set headers and flush them immediately so the browser
  // opens the EventSource connection before any data arrives.
  app.get('/api/events/stream', (req, res) => {
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders(); // send 200 + headers to the browser immediately

    const proxyReq = http.request(
      { hostname: 'localhost', port: 8000, path: '/api/events/stream', method: 'GET',
        headers: { Accept: 'text/event-stream', 'Cache-Control': 'no-cache' } },
      (proxyRes) => {
        proxyRes.pipe(res, { end: true });
        req.on('close', () => proxyReq.destroy());
      }
    );
    proxyReq.on('error', () => res.end());
    proxyReq.end();
  });

  // All other API and backend routes
  const apiPaths = [
    '/api',
    '/pod_alert',
    '/buckeye',
    '/pto',
    '/healthz',
    '/test',
    '/get_active_events_data',
  ];

  app.use(
    apiPaths,
    createProxyMiddleware({
      target: backendTarget,
      changeOrigin: true,
    })
  );
};
