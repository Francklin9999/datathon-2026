// Exported separately so the exact CloudFront code is exercised by tests.
export const rewriteCode = `function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri.endsWith('/')) request.uri += 'index.html';
  else if (uri.split('/').pop().indexOf('.') === -1) request.uri += '/index.html';
  return request;
}`;
