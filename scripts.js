// ✅ MODIFIED: imageData.product is now an array
const imageData = { person: null, product: [] }; 
let currentApiMode = 'single'; // To track which API to call

const API_BASE_URL = "http://127.0.0.1:8000";
// const API_BASE_URL = "https://tryon-3zcg.onrender.com";

/**
 * Main function to submit the try-on request.
 * Now handles both single and multi-image modes.
 */
async function submitTryOn() {
  if (!imageData.person || imageData.product.length === 0) {
    alert("Please provide a person image and at least one product image!");
    return;
  }

  // Common details for both payloads
  const commonDetails = {
    productName: document.getElementById("productName").value,
    productSize: document.getElementById("productSize").value,
    productDesc: document.getElementById("productDesc").value,
    tone: document.getElementById("tone").value,
    style: document.getElementById("style").value
  };

  let endpoint = '';
  let payload = {};

  // ✅ Build payload and select endpoint based on the current mode
  if (currentApiMode === 'single') {
    endpoint = `${API_BASE_URL}/generate`;
    payload = {
      personImage: imageData.person,
      productImage: imageData.product[0], // Use the first product image
      ...commonDetails
    };
  } else { // 'multi' mode
    endpoint = `${API_BASE_URL}/generate_multi_image`;
    payload = {
      personImage: imageData.person,
      productImages: imageData.product, // Use the entire array of images
      ...commonDetails
    };
  }
  
  console.log(`Submitting to ${endpoint} with mode: ${currentApiMode}`);

  toggleLoading(true);
  try {
    const res = await fetch(endpoint, {
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

/**
 * Renders product image thumbnails in the preview container.
 */
function renderProductThumbnails() {
  const container = document.getElementById('product-preview-container');
  container.innerHTML = ''; // Clear existing thumbnails

  if (imageData.product.length === 0) {
      container.innerHTML = '<span>Previews of product angles will appear here</span>';
      return;
  }

  imageData.product.forEach((base64, index) => {
    const thumbnailDiv = document.createElement('div');
    thumbnailDiv.className = 'thumbnail';
    
    // Create image from base64 data
    const img = document.createElement('img');
    img.src = `data:image/jpeg;base64,${base64}`;
    
    // Create remove button
    const removeBtn = document.createElement('button');
    removeBtn.className = 'remove-btn';
    removeBtn.innerHTML = '&times;';
    removeBtn.dataset.index = index; // Store index to know which image to remove
    removeBtn.onclick = (event) => {
      const indexToRemove = parseInt(event.target.dataset.index, 10);
      imageData.product.splice(indexToRemove, 1); // Remove from array
      renderProductThumbnails(); // Re-render the thumbnails
    };

    thumbnailDiv.appendChild(img);
    thumbnailDiv.appendChild(removeBtn);
    container.appendChild(thumbnailDiv);
  });
}

function setupImageInputs() {
  document.querySelectorAll('.image-input').forEach(container => {
    const inputId = container.dataset.inputId;
    const fileInput = container.querySelector('.file-input');
    const urlInput = container.querySelector('.url-input');
    const preview = container.querySelector('.image-preview'); // For person
    
    // File input handling (for both person and product)
    fileInput.addEventListener('change', async (event) => {
      const files = event.target.files;
      if (!files) return;

      if (inputId === 'person') {
        const file = files[0];
        imageData.person = await fileToBase64(file);
        preview.innerHTML = `<img src="${URL.createObjectURL(file)}" alt="Preview">`;
      } else { // product
        for (const file of files) {
          const base64 = await fileToBase64(file);
          imageData.product.push(base64);
        }
        renderProductThumbnails();
      }
    });

    // URL input handling
    const handleUrlInput = async () => {
        const url = urlInput.value.trim();
        if (!url) return;
        
        const loaderSpan = (inputId === 'person') ? preview : document.getElementById('product-preview-container');
        loaderSpan.innerHTML = '<span>Loading...</span>';

        const base64 = await urlToBase64(url);
        if (base64) {
            if (inputId === 'person') {
                imageData.person = base64;
                preview.innerHTML = `<img src="${url}" alt="Preview">`;
            } else { // product
                imageData.product.push(base64);
                renderProductThumbnails();
                urlInput.value = ''; // Clear input for next URL
            }
        } else {
            if (inputId === 'person') {
                preview.innerHTML = `<span>Failed to load. Is it a direct link?</span>`;
                imageData.person = null;
            } else {
                renderProductThumbnails(); // Restore previous state
                alert('Failed to load image from URL.');
            }
        }
    };
    
    // Use 'keydown' for Enter key on URL input
    urlInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            handleUrlInput();
        }
    });
    // And 'blur' for when user clicks away
    urlInput.addEventListener('blur', handleUrlInput);


    // Tab switching logic
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

// --- Lifecycle and Helper Functions (Unchanged below this line, except DOMContentLoaded) ---

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('submitBtn').addEventListener('click', submitTryOn);
  setupImageInputs();
  setupDownloadButton();

  // ✅ Add event listeners for the new mode selector
  document.querySelectorAll('.mode-selector .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelector('.mode-selector .tab.active').classList.remove('active');
      tab.classList.add('active');
      currentApiMode = tab.dataset.mode;
      console.log(`API Mode switched to: ${currentApiMode}`);
    });
  });
});

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