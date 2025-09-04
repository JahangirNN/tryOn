const imageData = { person: null, product: null };
// Ensure this URL is correct and points to your Render deployment
const API_BASE_URL = "https://tryon-3zcg.onrender.com";

async function submitTryOn() {
  if (!imageData.person || !imageData.product) {
    alert("Please provide both a person and a product image!");
    return;
  }
  
  // CORRECTED PAYLOAD: Now collects all fields from the updated HTML
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
        const errorData = await res.json().catch(() => ({ detail: "An unknown server error occurred." }));
        throw new Error(errorData.detail || `Server error: ${res.status}`);
    }

    const imageBlob = await res.blob();
    if (imageBlob.size > 0) {
      const imageUrl = URL.createObjectURL(imageBlob);
      document.getElementById("resultImage").src = imageUrl;

      // Show and enable the download button on success
      const downloadBtn = document.getElementById('downloadBtn');
      downloadBtn.style.display = 'flex';
      downloadBtn.disabled = false;
    } else {
      throw new Error("API did not return a valid image.");
    }

  } catch (error) {
    console.error("Error during generation:", error);
    alert(`An error occurred while generating the image.\n\nReason: ${error.message}`);
  } finally {
    toggleLoading(false);
  }
}

function setupDownloadButton() {
    const downloadBtn = document.getElementById('downloadBtn');
    const resultImage = document.getElementById('resultImage');

    downloadBtn.addEventListener('click', () => {
        const imageUrl = resultImage.src;
        if (!imageUrl || imageUrl.startsWith('https://via.placeholder.com')) {
            alert("No image to download yet!");
            return;
        }
        const link = document.createElement('a');
        link.href = imageUrl;
        link.download = 'virtual-try-on-result.png';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });
}

document.addEventListener('DOMContentLoaded', () => {
  setupImageInputs();
  setupDownloadButton();
});

// --- Helper Functions ---

async function urlToBase64(url) {
  try {
    const proxyUrl = `${API_BASE_URL}/proxy-image?url=${encodeURIComponent(url)}`;
    const response = await fetch(proxyUrl);
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(errorData?.detail || `Proxy server returned status: ${response.status}`);
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
      alert(`Failed to load image from URL. Reason: ${error.message}`);
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
        preview.innerHTML = `<span>Loading...</span>`;
        const base64 = await urlToBase64(url);
        if (base64) {
          imageData[inputId] = base64;
          preview.innerHTML = `<img src="${url}" alt="Preview">`;
        } else {
          preview.innerHTML = `<span>Failed to load. Is it a direct link?</span>`;
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
  const downloadBtn = document.getElementById('downloadBtn');

  if (isLoading) {
    submitBtn.disabled = true;
    btnText.textContent = 'Generating...';
    btnSpinner.style.display = 'block';
    resultLoader.style.display = 'flex';
    downloadBtn.style.display = 'none';
    downloadBtn.disabled = true;
  } else {
    submitBtn.disabled = false;
    btnText.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Generate Try-On';
    btnSpinner.style.display = 'none';
    resultLoader.style.display = 'none';
  }
}