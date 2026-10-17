export function humanize(code) {
  const text = code.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function parse(iso) {
  if (!iso) return null;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(iso) {
  const date = parse(iso);
  return date ? `${date.toISOString().slice(0, 16).replace("T", " ")} UTC` : "–";
}

export function formatDate(iso) {
  const date = parse(iso);
  return date ? date.toISOString().slice(0, 10) : "–";
}

export function formatTime(iso) {
  const date = parse(iso);
  return date ? date.toISOString().slice(11, 19) : iso;
}

export function formatNumber(value) {
  return value.toLocaleString("en-GB");
}

export function formatDuration(seconds) {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

// Works on the decimal text from the API so large amounts are never rounded by a float.
export function formatMoney(amount, currency) {
  const [whole, fraction] = amount.split(".");
  const sign = whole.startsWith("-") ? "-" : "";
  const digits = whole.replace("-", "").replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const cents = fraction && /[1-9]/.test(fraction) ? `,${fraction}` : "";
  return `${sign}${digits}${cents} ${currency}`.trim();
}

export function score(value) {
  return Number(value).toFixed(2);
}

// Source URLs come from web pages, so only http and https become links.
export function safeHref(url) {
  try {
    const parsed = new URL(url ?? "");
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export function hostOf(url) {
  try {
    return new URL(url ?? "").hostname;
  } catch {
    return null;
  }
}
