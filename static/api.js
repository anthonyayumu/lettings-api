function describeError(detail) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => `${item.loc.slice(1).join(".")}: ${item.msg}`)
      .join("; ");
  }
  return String(detail);
}

async function request(path, options) {
  const response = await fetch(path, options);
  let body = null;
  try {
    body = await response.json();
  } catch {
    // the response had no JSON body
  }
  if (!response.ok) {
    const detail = body && body.detail ? describeError(body.detail) : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return body;
}

function getJSON(path) {
  return request(path);
}

function sendJSON(path, method, data) {
  return request(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}