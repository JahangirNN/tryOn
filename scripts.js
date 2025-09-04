const imageData = { person: null, product: null };
// Ensure this URL is correct and the deployment is active
const API_BASE_URL = "https://tryon-3zcg.onrender.com";

async function submitTryOn() {
  if (!imageData.person || !imageData.product) {
    alert("Please provide both a person and a product image!");
    return;
  }
  const payload = {
    personImage: imageData.person,
    productImage: imageData.product,
    productName: document.getElementById("productName").value,
    productSize: document.getElementById("productSize").value,
    productDesc: document.getElementById("productDesc").value,
    tone: document.getElementById("tone").value,
    style: document.getElementById("style").value
  };
  toggleLoading(true);
  try {
    const res = await fetch(`${API_BASE_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
        // Try to get a specific error message from the server if available
        const errorData = await res.json().catch(() => ({ detail: "An unknown server error occurred." }));
        throw new Error(errorData.detail || `Server error: ${res.status}`);
    }

    const imageBlob = await res.blob();
    if (imageBlob.size > 0) {
      const imageUrl = URL.createObjectURL(imageBlob);
      document.getElementById("resultImage").src = imageUrl;
    } else {
      throw new Error("API did not return a valid image.");
    }

  } catch (error) {
    console.error("Error during generation:", error);
    // This custom function gives you the helpful alert you saw
    handleFetchError(error, "generating the image");
  } finally {
    toggleLoading(false);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupImageInputs();
});

// --- Helper Functions ---

function handleFetchError(error, action) {
    let alertMessage = `An error occurred while ${action}.\n\nReason: ${error.message}\n\n`;
    if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
        alertMessage += 'This is often a CORS issue or a server timeout on the free Vercel plan.\n\n';
        alertMessage += 'Debugging Steps:\n';
        alertMessage += '1. Go to your Vercel dashboard and check the "Logs" for your deployment. Look for a "TASK_TIMED_OUT" error.\n';
        alertMessage += '2. Open the Developer Console (F12) and check the "Network" tab for more details on the failed request.\n';
    }
    alert(alertMessage);
}

async function urlToBase64(url) {
  try {
    const proxyUrl = `${API_BASE_URL}/proxy-image?url=${encodeURIComponent(url)}`;
    const response = await fetch(proxyUrl);
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const detail = errorData?.detail || `Proxy server returned status: ${response.status}`;
      throw new Error(detail);
    }
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
  } catch (error) {
      console.error("URL to Base64 conversion failed:", error);
      handleFetchError(error, "loading the image from the URL");
      return null;
  }
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function setupImageInputs() {
  document.querySelectorAll('.image-input').forEach(container => {
    const inputId = container.dataset.inputId;
    const fileInput = container.querySelector('.file-input');
    const urlInput = container.querySelector('.url-input');
    const preview = container.querySelector('.image-preview');
    fileInput.addEventListener('change', async (event) => {
      const file = event.target.files[0];
      if (file) {
        imageData[inputId] = await fileToBase64(file);
        preview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="Preview">`;
      }
    });
    urlInput.addEventListener('blur', async () => {
      const url = urlInput.value.trim();
      if (url) {
        preview.innerHTML = `<span>Loading from URL...</span>`;
        const base64 = await urlToBase64(url);
        if (base64) {
          imageData[inputId] = base64;
          preview.innerHTML = `<img src="${url}" alt="Preview">`;
        } else {
          preview.innerHTML = `<span>Failed to load. Check console for errors.</span>`;
          imageData[inputId] = null;
        }
      }
    });
    container.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        container.querySelector('.tab.active').classList.remove('active');
        tab.classList.add('active');
        const tabName = tab.dataset.tab;
        container.querySelector('.tab-content.active').classList.remove('active');
        container.querySelector(`.tab-content[data-tab-content="${tabName}"]`).classList.add('active');
      });
    });
  });
}

function toggleLoading(isLoading) {
  const submitBtn = document.getElementById('submitBtn');
  const btnText = document.getElementById('btn-text');
  const btnSpinner = document.getElementById('btn-spinner');
  const resultLoader = document.getElementById('resultLoader');
  if (isLoading) {
    submitBtn.disabled = true;
    btnText.textContent = 'Generating...';
    btnSpinner.style.display = 'block';
    resultLoader.style.display = 'flex';
  } else {
    submitBtn.disabled = false;
    btnText.textContent = 'Generate Try-On';
    btnSpinner.style.display = 'none';
    resultLoader.style.display = 'none';
  }
}