const imageData = { person: null, product: null };
const API_BASE_URL = "http://127.0.0.1:8000";

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
    const data = await res.json(); // Try to get JSON regardless of res.ok
    if (!res.ok) {
        throw new Error(data.detail || `Server error: ${res.status}`);
    }
    if (data.imageUrl) {
      document.getElementById("resultImage").src = data.imageUrl;
      await loadGallery();
    } else {
      throw new Error("API did not return an image URL.");
    }
  } catch (error) {
    console.error("Error during generation:", error);
    // alert(`Error: ${error.message}`);
  } finally {
    toggleLoading(false);
  }
}

async function loadGallery() {
  try {
    const res = await fetch(`${API_BASE_URL}/gallery`);
    if (!res.ok) throw new Error("Failed to fetch gallery from server.");
    const imageUrls = await res.json();
    const galleryDiv = document.getElementById('gallery');
    galleryDiv.innerHTML = '';
    imageUrls.forEach(url => {
      const img = document.createElement('img');
      img.src = url;
      img.alt = 'Generated image from gallery';
      img.onclick = () => handleGalleryImageClick(img, url);
      galleryDiv.appendChild(img);
    });
  } catch (error) {
    console.error("Could not load gallery:", error);
    document.getElementById('gallery').innerHTML = '<p>Error loading gallery.</p>';
  }
}

async function handleGalleryImageClick(imgElement, imageUrl) {
  document.querySelectorAll('#gallery img.selected').forEach(el => el.classList.remove('selected'));
  imgElement.classList.add('selected');
  const personPreview = document.querySelector('.image-input[data-input-id="person"] .image-preview');
  personPreview.innerHTML = `<span>Loading from gallery...</span>`;
  const base64Data = await urlToBase64(imageUrl);
  if (base64Data) {
    imageData.person = base64Data;
    personPreview.innerHTML = `<img src="${imageUrl}" alt="Selected from gallery">`;
    // alert('Image loaded and is now set as the Person Image.');
  } else {
    personPreview.innerHTML = `<span>Failed to load image</span>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupImageInputs();
  loadGallery();
});

// --- Helper Functions ---
async function urlToBase64(url) {
  try {
    // This correctly calls your robust backend proxy
    const proxyUrl = `${API_BASE_URL}/proxy-image?url=${encodeURIComponent(url)}`;
    const response = await fetch(proxyUrl);
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `Failed via proxy: ${response.statusText}`);
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
        preview.innerHTML = `<span>Loading from URL...</span>`;
        const base64 = await urlToBase64(url);
        if (base64) {
          imageData[inputId] = base64;
          // We use the original URL for the preview to avoid a long data URI
          preview.innerHTML = `<img src="${url}" alt="Preview">`;
        } else {
          preview.innerHTML = `<span>Failed to load. Is it a direct link to a JPG/PNG?</span>`;
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