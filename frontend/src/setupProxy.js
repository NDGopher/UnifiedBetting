const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  const backendTarget = 'http://localhost:8000';

  // Proxy WebSocket connections (path avoids webpack HMR /ws conflict)
  app.use(
    '/api/ws',
    createProxyMiddleware({
      target: backendTarget,
      changeOrigin: true,
      ws: true,
    })
  );

  // Proxy all API and backend routes
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
