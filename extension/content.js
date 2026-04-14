// Procura o % de uso do plano no DOM do claude.ai e envia para o widget local
const WIDGET_URL = "http://localhost:9847/usage";
const POLL_INTERVAL_MS = 5000;

function extractUsage() {
  // Procura texto no formato "XX% used" em qualquer elemento da página
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent.trim();
    const match = text.match(/^(\d+)%\s*used$/i);
    if (match) {
      return parseInt(match[1], 10);
    }
  }

  // Fallback: procura "XX% used" em qualquer texto da página
  const bodyText = document.body.innerText;
  const match = bodyText.match(/(\d+)%\s*used/i);
  if (match) {
    return parseInt(match[1], 10);
  }

  return null;
}

function extractResetTime() {
  const bodyText = document.body.innerText;
  // Procura "Resets in X hr Y min" ou "Resets in X min"
  const match = bodyText.match(/Resets in\s+([\d\s\w]+)/i);
  return match ? match[1].trim() : null;
}

async function sendToWidget(pct, resetIn) {
  try {
    await fetch(WIDGET_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pct, resetIn }),
    });
  } catch (_) {
    // Widget pode não estar aberto, ignora silenciosamente
  }
}

function poll() {
  const pct = extractUsage();
  const resetIn = extractResetTime();
  if (pct !== null) {
    sendToWidget(pct, resetIn);
  }
}

// Inicia o polling
poll();
setInterval(poll, POLL_INTERVAL_MS);
