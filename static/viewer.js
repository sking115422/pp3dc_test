const imageEl = document.getElementById("image");
const imageNameEl = document.getElementById("image-name");
const delayInput = document.getElementById("delay-input");
const startBtn = document.getElementById("start");
const stopBtn = document.getElementById("stop");
const resetBtn = document.getElementById("reset");
const statusEl = document.getElementById("status");
const controls = document.getElementById("controls");
const controlsToggle = document.getElementById("controls-toggle");

let lastImageUrl = null;
let lastImageName = null;

const updateViewerUrl = (name, index) => {
  const basePath = window.location.pathname || "/";
  const nextUrl = `${basePath}?image=${encodeURIComponent(name)}&index=${index + 1}`;
  if (window.location.pathname + window.location.search !== nextUrl) {
    window.history.replaceState({}, "", nextUrl);
  }
};

const postJson = async (url, body) => {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
};

const refreshState = async () => {
  try {
    const response = await fetch("/api/state");
    const data = await response.json();

    statusEl.textContent = data.status || "Ready.";

    const activeEl = document.activeElement;
    if (activeEl !== delayInput && Number.isFinite(data.delay_ms)) {
      delayInput.value = (data.delay_ms / 1000).toString();
    }

    startBtn.disabled = data.images_count === 0 || data.is_playing;
    stopBtn.disabled = !data.is_playing;

    if (!data.current_image) {
      imageEl.removeAttribute("src");
      imageEl.alt = "";
      imageNameEl.textContent = data.status || "No images loaded.";
      lastImageUrl = null;
      lastImageName = null;
      return;
    }

    const { url, name, index } = data.current_image;
    if (url !== lastImageUrl) {
      imageEl.src = url;
      lastImageUrl = url;
    }

    if (name !== lastImageName) {
      imageEl.alt = name;
      imageNameEl.textContent = name;
      lastImageName = name;
    }

    updateViewerUrl(name, index);
  } catch (error) {
    statusEl.textContent = error.message;
  }
};

const updateDelay = async () => {
  const seconds = Number.parseFloat(delayInput.value);
  const delayMs =
    Number.isFinite(seconds) && seconds > 0
      ? Math.round(seconds * 1000)
      : 3000;

  try {
    await postJson("/api/set_delay", { delay_ms: delayMs });
  } catch (error) {
    statusEl.textContent = error.message;
  }
  await refreshState();
};

startBtn.addEventListener("click", async () => {
  try {
    await postJson("/api/start", {});
  } catch (error) {
    statusEl.textContent = error.message;
  }
  await refreshState();
});

stopBtn.addEventListener("click", async () => {
  try {
    await postJson("/api/stop", {});
  } catch (error) {
    statusEl.textContent = error.message;
  }
  await refreshState();
});

resetBtn.addEventListener("click", async () => {
  try {
    await postJson("/api/reset", {});
  } catch (error) {
    statusEl.textContent = error.message;
  }
  await refreshState();
});

delayInput.addEventListener("change", updateDelay);

controlsToggle.addEventListener("click", () => {
  const isOpen = controls.classList.toggle("open");
  controlsToggle.textContent = isOpen ? "▶" : "◀";
  controlsToggle.setAttribute("aria-expanded", String(isOpen));
  controls.setAttribute("aria-hidden", String(!isOpen));
});

refreshState();
setInterval(refreshState, 500);
