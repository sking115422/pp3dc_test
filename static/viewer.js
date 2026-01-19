const imageEl = document.getElementById("image");
const imageNameEl = document.getElementById("image-name");

let lastImageUrl = null;
let lastImageName = null;

const updateViewerUrl = (name, index) => {
  const basePath = window.location.pathname || "/";
  const nextUrl = `${basePath}?image=${encodeURIComponent(name)}&index=${index + 1}`;
  if (window.location.pathname + window.location.search !== nextUrl) {
    window.history.replaceState({}, "", nextUrl);
  }
};

const refreshState = async () => {
  try {
    const response = await fetch("/api/state");
    const data = await response.json();

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
    imageNameEl.textContent = error.message;
  }
};

refreshState();
setInterval(refreshState, 500);
