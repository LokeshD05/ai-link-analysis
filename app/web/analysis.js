const form = document.querySelector("#analysis-form");
const input = document.querySelector("#website-url");
const submit = document.querySelector("#analyze");
const status = document.querySelector("#status");
const error = document.querySelector("#error");
const results = document.querySelector("#results");
const report = document.querySelector("#report");
let analysisResult;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function heading(key) {
  const label = key.replaceAll("_", " ");
  return label[0].toUpperCase() + label.slice(1);
}

function fields(values) {
  const list = element("dl");
  for (const [key, value] of Object.entries(values)) {
    if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) continue;
    const entry = element("div");
    const detail = element("dd");
    if (Array.isArray(value)) {
      const items = element("ul");
      for (const item of value) items.append(element("li", item));
      detail.append(items);
    } else {
      detail.textContent = value;
    }
    entry.append(element("dt", heading(key)), detail);
    list.append(entry);
  }
  return list;
}

function card(title) {
  const section = element("section", undefined, "card");
  section.append(element("h3", title));
  report.append(section);
  return section;
}

function records(section, items, titleKey, emptyMessage, sources = {}) {
  if (!items.length) section.append(element("p", emptyMessage));
  for (const item of items) {
    const {
      [titleKey]: title, basis, evidence_id: sourceId, evidence_excerpt: excerpt, ...details
    } = item;
    const row = element("article", undefined, "item");
    row.append(element("h4", title));
    if (basis) details.basis = basis === "website" ? "Website evidence" : "Inferred recommendation";
    if (excerpt) details.evidence = excerpt;
    row.append(fields(details));
    if (sources[sourceId]) {
      const link = element("a", "View source page");
      link.href = sources[sourceId];
      row.append(link);
    }
    section.append(row);
  }
}

function render(data) {
  report.replaceChildren();
  const { name, ...brand } = data.brand;
  card(name).append(fields({ website: data.website, ...brand }));
  const {
    competitor_analysis: comparison, target_search_queries: queries, seo_improvements: seo,
    top_services: services, target_audience: audience,
  } = data.analysis;
  const { competitors, ...positioning } = comparison;
  const competitorCard = card("Competitor comparison");
  competitorCard.append(fields(positioning));
  if (competitors.length) competitorCard.append(element("p", "AI-generated competitor suggestions"));
  records(competitorCard, competitors, "name", "No reliable competitor suggestions.");
  records(card("Target search queries"), queries, "query", "No search queries returned.");
  card("SEO recommendations").append(fields(seo));
  records(card("Top services"), services, "name", "No services identified.", data.sources);
  const audienceFields = fields(audience);
  card("Target audience").append(
    audienceFields.childElementCount ? audienceFields : element("p", "No audience identified.")
  );
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.hidden = true;
  const rawUrl = input.value.trim();
  let url;
  try {
    url = new URL(/^[a-z][a-z\d+.-]*:\/\//i.test(rawUrl) ? rawUrl : `https://${rawUrl}`);
    if (!["http:", "https:"].includes(url.protocol) || !url.hostname || url.username || url.password) {
      throw new Error();
    }
    if (!url.hostname.includes(".") && !url.hostname.startsWith("[")) throw new Error();
  } catch {
    error.textContent = "Enter a valid public website URL, such as https://example.com.";
    error.hidden = false;
    input.focus();
    return;
  }

  analysisResult = undefined;
  results.hidden = true;
  submit.disabled = true;
  submit.textContent = "Analyzing…";
  status.textContent = "Reading the website and generating your report. This can take a minute.";
  status.hidden = false;

  try {
    const response = await fetch("/link-analysis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url.href }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || `Analysis failed (HTTP ${response.status}).`);
    }
    render(data);
    analysisResult = data;
    results.hidden = false;
    document.querySelector("#results-title").focus();
  } catch (failure) {
    error.textContent = failure instanceof TypeError || failure instanceof SyntaxError
      ? "The analysis service could not be reached. Try again shortly."
      : failure.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
    submit.textContent = "Analyze website";
    status.hidden = true;
  }
});

document.querySelector("#download").addEventListener("click", () => {
  if (!analysisResult) return;
  const file = new Blob([JSON.stringify(analysisResult, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(file);
  const link = element("a");
  link.href = url;
  link.download = "website-analysis.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
