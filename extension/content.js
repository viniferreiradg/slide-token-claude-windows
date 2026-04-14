// Claude Token Slide — content.js
// Estratégia 1: intercepta respostas da API do claude.ai (mais confiável)
// Estratégia 2: lê barras de progresso do DOM (fallback)
// Envia { pct, resetIn } para o widget local na porta 9847

const WIDGET_URL    = "http://localhost:9847/usage";
const POLL_INTERVAL = 5000;

// ── Estratégia 1: interceptar fetch ──────────────────────────────────────────
(function interceptFetch() {
  const _fetch = window.fetch;
  window.fetch = async function (...args) {
    const response = await _fetch(...args);
    try {
      const url = typeof args[0] === "string" ? args[0] : args[0]?.url ?? "";
      // Endpoints que costumam retornar dados de uso
      if (/account|usage|limits|organization|bootstrap/i.test(url)) {
        const clone = response.clone();
        clone.json().then((data) => {
          const result = extractFromApiResponse(data);
          if (result) sendToWidget(result.pct, result.resetIn);
        }).catch(() => {});
      }
    } catch (_) {}
    return response;
  };
})();

function extractFromApiResponse(data, depth = 0) {
  if (depth > 6 || !data || typeof data !== "object") return null;

  // Procura campos com nome relacionado a uso/limite
  const keys = Object.keys(data);
  for (const key of keys) {
    if (/usage|limit|percent|quota|remaining|reset/i.test(key)) {
      const val = data[key];
      // Se for número entre 0 e 100, provavelmente é porcentagem
      if (typeof val === "number" && val >= 0 && val <= 100) {
        return { pct: Math.round(val), resetIn: findResetIn(data) };
      }
      // Se tiver numerator/denominator, calcula %
      if (typeof val === "object" && val !== null) {
        const num = val.used ?? val.numerator ?? val.current ?? val.value;
        const den = val.limit ?? val.denominator ?? val.total ?? val.max;
        if (typeof num === "number" && typeof den === "number" && den > 0) {
          return { pct: Math.round((num / den) * 100), resetIn: findResetIn(data) };
        }
      }
    }
    // Recursão em objetos aninhados
    if (typeof data[key] === "object") {
      const result = extractFromApiResponse(data[key], depth + 1);
      if (result) return result;
    }
  }
  return null;
}

function findResetIn(data) {
  const str = JSON.stringify(data);
  const m = str.match(/"reset(?:s|At|Time|In)?"\s*:\s*"?([^",}]+)"?/i);
  return m ? m[1].trim() : null;
}

// ── Estratégia 2: ler barras de progresso do DOM ──────────────────────────────
function readProgressBars() {
  // <progress> nativo
  const progressEls = document.querySelectorAll("progress");
  for (const el of progressEls) {
    const max = parseFloat(el.getAttribute("max") || el.max || 1);
    const val = parseFloat(el.getAttribute("value") || el.value || 0);
    if (max > 0) return { pct: Math.round((val / max) * 100), resetIn: readResetText() };
  }

  // Divs estilizadas como progress bar (estilo width: XX%)
  const allDivs = document.querySelectorAll("div[style*='width']");
  for (const div of allDivs) {
    const w = div.style.width;
    if (w && w.endsWith("%")) {
      const pct = parseFloat(w);
      if (pct > 0 && pct <= 100) {
        return { pct: Math.round(pct), resetIn: readResetText() };
      }
    }
  }

  // Procura texto com padrão de porcentagem (PT e EN)
  const bodyText = document.body?.innerText ?? "";
  const patterns = [
    /(\d+)%\s*(?:used|usado|utilizado)/i,
    /(?:used|usado|utilizado)[:\s]+(\d+)%/i,
    /(\d+)\s*\/\s*100/,
  ];
  for (const re of patterns) {
    const m = bodyText.match(re);
    if (m) return { pct: parseInt(m[1], 10), resetIn: readResetText() };
  }

  return null;
}

function readResetText() {
  const bodyText = document.body?.innerText ?? "";
  const m = bodyText.match(/[Rr]enova(?:\s+em)?\s+([\d\w\s]+)/i)
         || bodyText.match(/[Rr]esets?\s+in\s+([\d\w\s]+)/i);
  return m ? m[1].trim().split("\n")[0] : null;
}

// ── Envio ────────────────────────────────────────────────────────────────────
async function sendToWidget(pct, resetIn) {
  try {
    await fetch(WIDGET_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pct, resetIn }),
    });
  } catch (_) {}
}

// ── Loop principal ────────────────────────────────────────────────────────────
function poll() {
  const result = readProgressBars();
  if (result) sendToWidget(result.pct, result.resetIn);
}

poll();
setInterval(poll, POLL_INTERVAL);
