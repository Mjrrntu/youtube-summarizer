function stripFrontmatter(markdown) {
  return markdown.replace(/^---\s*[\s\S]*?\s*---\s*/, "");
}

function cleanTerminalArtifacts(text) {
  return String(text || "")
    .replace(/\S*\x1b\[\d+[A-Za-z]\x1b\[K\s*/g, "")
    .replace(/\S*\[\d+[A-Za-z]\[K\s*/g, "")
     .replace(/\[K/g, "");
}

function parseSimpleYaml(yamlText) {
  const metadata = {};

  for (const line of yamlText.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const idx = trimmed.indexOf(":");
    if (idx === -1) continue;

    const key = trimmed.slice(0, idx).trim();
    let value = trimmed.slice(idx + 1).trim();

    if (
      (value.startsWith("'") && value.endsWith("'")) ||
      (value.startsWith('"') && value.endsWith('"'))
    ) {
      value = value.slice(1, -1);
    }

    if (value === "[]") value = [];

    metadata[key] = value;
  }

  return metadata;
}

function parseFrontmatter(markdown) {
  const match = markdown.match(/^---\s*([\s\S]*?)\s*---\s*([\s\S]*)$/);

  if (!match) {
    return {
      metadata: {},
      content: markdown
    };
  }

  return {
    metadata: parseSimpleYaml(match[1]),
    content: match[2]
  };
}

function renderMetadata(meta) {
  const container = document.getElementById("meta");

  container.innerHTML = `
    <h3>Metadata</h3>
    <table>
      <tr><td>Source Type</td><td>${meta.source_type || ""}</td></tr>
      <tr><td>Video Title</td><td>${meta.video_title || ""}</td></tr>
      <tr><td>Channel</td><td>${meta.channel || ""}</td></tr>
      <tr><td>Published</td><td>${meta.published_at || ""}</td></tr>
      <tr><td>Model</td><td>${meta.summary_model || meta.analysis_model || ""}</td></tr>
      <tr><td>Verification</td><td>${meta.verification_status || ""}</td></tr>
      <tr>
        <td>Source URL</td>
        <td>
          ${meta.source_url ? `<a href="${meta.source_url}" target="_blank">${meta.source_url}</a>` : ""}
        </td>
      </tr>
    </table>
  `;
}

async function run() {
  const params = new URLSearchParams(window.location.search);

  const endpoint = params.get("endpoint");
  const label = params.get("label") || "AI Analysis";
  const url = params.get("url");

  const title = document.getElementById("title");
  const status = document.getElementById("status");
  const meta = document.getElementById("meta");
  const output = document.getElementById("output");

  title.textContent = label;
  status.textContent = `${label}: käsitellään...`;
  meta.textContent = url || "";

  try {
    const response = await fetch(`http://127.0.0.1:8765/${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        url: url
      })
    });

    const data = await response.json();

    if (!data.ok) {
      status.textContent = `${label}: virhe`;
      output.textContent =
        data.stderr ||
        data.stdout ||
        JSON.stringify(data, null, 2);
      return;
    }

    const rawContent =
      data.content ||
      data.summary ||
      data.analysis ||
      "";

    const content = cleanTerminalArtifacts(rawContent);

    status.textContent = `${label}: valmis`;

    const parsed = parseFrontmatter(content);

    renderMetadata(parsed.metadata);

    output.innerHTML = marked.parse(parsed.content);

  } catch (err) {
    status.textContent = `${label}: virhe`;
    output.textContent = String(err);
  }
}

run();
