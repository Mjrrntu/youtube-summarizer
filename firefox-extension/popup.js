async function getCurrentTabUrl() {
  const tabs = await browser.tabs.query({
    active: true,
    currentWindow: true
  });

  if (!tabs.length) {
    throw new Error("Aktiivista välilehteä ei löytynyt");
  }

  return tabs[0].url;
}

document.getElementById("summarize").addEventListener("click", async () => {
  const status = document.getElementById("status");
  const output = document.getElementById("output");

  status.textContent = "Käsitellään...";
  output.textContent = "";

  try {
    const url = await getCurrentTabUrl();

    const response = await fetch("http://127.0.0.1:8765/summarize", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        url: url,
        whisper_model: "large-v3",
        ai_model: "gpt-oss:20b",
        device: "cuda",
        compute_type: "float16",
        cpu_threads: 24
      })
    });

    const data = await response.json();

    if (!data.ok) {
      status.textContent = "Virhe";
      output.textContent = data.stderr || data.stdout || JSON.stringify(data, null, 2);
      return;
    }

    status.textContent = "Valmis";
    // output.textContent = data.summary;
    output.innerHTML = marked.parse(data.summary);

  } catch (err) {
    status.textContent = "Virhe";
    output.textContent = String(err);
  }
});
