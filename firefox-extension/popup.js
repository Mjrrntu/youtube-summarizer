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


async function startAnalysis(endpoint, label) {
  const status = document.getElementById("status");
  status.textContent = `${label}: tehtävä käynnistetty`;

  const url = await getCurrentTabUrl();

  const resultUrl = browser.runtime.getURL(
    `result.html?endpoint=${encodeURIComponent(endpoint)}&label=${encodeURIComponent(label)}&url=${encodeURIComponent(url)}`
  );

  await browser.tabs.create({
    url: resultUrl
  });
}


document.getElementById("summarize").addEventListener("click", async () => {
  await startAnalysis("summarize", "AI-yhteenveto");
});


document.getElementById("tech-analysis").addEventListener("click", async () => {
  await startAnalysis("tech-analysis", "Tech Analysis");
});
