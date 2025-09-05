import os
import uuid
import base64
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List
from dotenv import load_dotenv   # ✅ Add this

# Required libraries: pip install google-generativeai Pillow httpx aiofiles python-dotenv
import google.generativeai as genai
from PIL import Image
from io import BytesIO
import httpx
import re

# --- 1. Configuration (Unchanged except API loading) ---
# IMAGE_DIR = "gallery_images"
# os.makedirs(IMAGE_DIR, exist_ok=True)

# ✅ Load .env variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set in .env file")

# ✅ Configure Gemini
genai.configure(api_key=api_key)

# --- 2. Pydantic Models (Unchanged) ---
class TryOnPayload(BaseModel):
    personImage: str
    productImage: str
    productName: str
    productSize: str
    productDesc: str
    tone: Optional[str] = None
    style: Optional[str] = None

class TryOnResponse(BaseModel):
    imageUrl: str = Field(..., description="The public URL of the newly generated image.")

# --- 3. FastAPI Application Setup (Unchanged) ---
app = FastAPI(
    title="AI Virtual Try-On API (Personal Use)",
    description="Uses a two-step AI process to create a realistic, personal virtual try-on.",
    version="10.0.0"
)
# app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="images")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 4. AI Model Initialization (Unchanged) ---
# This is your powerful image generation model
image_generation_model = genai.GenerativeModel(model_name="gemini-2.5-flash-image-preview")

# This is the fast model for generating the text description
description_model = genai.GenerativeModel(model_name='gemini-2.5-flash-lite')

# --- 5. API Endpoints (All endpoints except /generate are unchanged) ---
@app.get("/proxy-image")
async def proxy_image(url: str):
    # This function is unchanged.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True, timeout=15, headers=headers)
            response.raise_for_status()
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="URL is not a direct image link.")
            return Response(content=response.content, media_type=content_type)
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Image server error: {e.response.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch image: {e}")

# @app.get("/gallery", response_model=List[str])
# async def get_gallery():
#     # This function is unchanged.
#     try:
#         files = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
#         files.sort(key=lambda x: os.path.getmtime(os.path.join(IMAGE_DIR, x)), reverse=True)
#         base_url = "http://127.0.0.1:8000/images"
#         return [f"{base_url}/{f}" for f in files]
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Could not retrieve gallery: {e}")

@app.post("/generate",
    # Use response_class for direct Response objects like images
    response_class=Response,
    # Add OpenAPI documentation for what this endpoint returns
    responses={
        200: {
            "content": {"image/png": {}},
            "description": "The generated try-on image in PNG format."
        }
    }
)
async def generate_tryon(payload: TryOnPayload):
    try:
        person_image = Image.open(BytesIO(base64.b64decode(payload.personImage)))
        product_image = Image.open(BytesIO(base64.b64decode(payload.productImage)))

        style_instructions = []
        if payload.tone: style_instructions.append(f"- Desired Tone: {payload.tone}")
        if payload.style: style_instructions.append(f"- Rendering Style: {payload.style}")

        # =================================================================
        # === STEP 1: AI AS A MASTER PROMPT ENGINEER ===
        # =================================================================
        ai_generated_dynamic_prompt = "" # Fallback
        try:
  
  
            # meta_prompt = meta_prompt_1_production_ready
            meta_prompt = meta_prompt_test_for_better(payload.productDesc)
            print(payload.productDesc, "\n")


            # Call the description model to generate the entire new prompt.
            description_response = description_model.generate_content(
                [meta_prompt, person_image, product_image],
                generation_config={"temperature": 0.2} # Temp allows for creative descriptions of fabric physics
            )
            ai_generated_dynamic_prompt = description_response.text.strip()
            print("\n--- AI as Master Prompt Engineer Generated the Following ---")
            print(ai_generated_dynamic_prompt)
            print("-----------------------------------------------------------\n")
            
        except Exception as e:
            print(f"WARNING: Dynamic prompt generation failed. Using basic fallback. Error: {e}")
            ai_generated_dynamic_prompt = "## GOAL\nCreate an image of the avatar wearing the new clothing. Preserve the avatar's identity and the background."
        # =================================================================
        # === END OF STEP 1 ===
        # =================================================================

        # =================================================================
        # === STEP 2: IMAGE GENERATION (Executing the master prompt) ===
        # =================================================================
        # The wrapper prompt is now a simple executor.
        image_gen_prompt = f"""
        You are a high-fidelity image synthesis engine. Your task is to execute the following technical instructions from an AI Specialist. Adhere to every rule with absolute precision.

        {ai_generated_dynamic_prompt}

        """

        contents = [image_gen_prompt, person_image, product_image]
        
        # Low temperature for the final execution to ensure it follows the strict rules.
        generation_config = {
            "temperature": 0.2,
            "candidate_count": 1
        }
        
        response = image_generation_model.generate_content(
            contents,
            generation_config=generation_config
        )
        
        generated_image_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                generated_image_data = part.inline_data.data
                break
                
        if generated_image_data:
            return Response(content=generated_image_data, media_type="image/png")
        else:
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            raise HTTPException(status_code=500, detail=f"Image generation failed. Reason: {block_reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")
    
 
class TryOnPayloadWithMultipleImages(BaseModel):
    personImage: str = Field(..., description="A single Base64 encoded string of the person's image.")
    productImages: List[str] = Field(..., description="A list of Base64 encoded strings for the product, showing different angles (e.g., front, back, detail).")
    productName: str
    productSize: str
    productDesc: str
    tone: Optional[str] = None
    style: Optional[str] = None

# This is the new "Master Blaster" meta-prompt, upgraded for multi-image analysis.
meta_prompt_multi_image = f"""
**ROLE:** You are an AI Render Supervisor & 3D Garment Specialist. Your function is to generate a "Shot Execution Brief"—a master-level, technically flawless render instruction set for a subsequent, diffusion-based image synthesis engine. You do not create the final image; you write the unimpeachable technical blueprint that guarantees its perfection.

**YOUR PRIMARY DIRECTIVE:**
Your output must be a self-contained, technically exhaustive brief. It MUST guide the image synthesis engine to perform a perfect, photorealistic clothing replacement on a digital avatar, while preserving the avatar's core identity (face, hair, hands) and the original scene with absolute fidelity. The product's appearance must be a perfect reconstruction based on the multiple angles provided.

**THE INTELLECTUAL PROCESS:**
1.  **DECONSTRUCT THE SCENE & AVATAR:** Analyze the first image (the avatar). Reverse-engineer the environment's lighting setup (key, fill, rim lights). Define the "identity preservation mask" (head, hair, neck, and hands). Analyze the avatar's pose to understand the underlying skeletal mechanics.
2.  **SYNTHESIZE THE PRODUCT (MULTI-IMAGE ANALYSIS):** Analyze the **collection** of subsequent images (the product). These images show the same garment from different angles. Your task is to mentally reconstruct the full 3D garment. Identify the front view, the back view, and any close-up detail shots of textures, seams, or hardware (buttons, zippers).
3.  **DECONSTRUCT THE PRODUCT's PHYSICAL PROPERTIES:** From the detail shots, analyze the product as a set of PBR (Physically-Based Rendering) materials. Determine its diffuse albedo, specular reflectivity, microsurface roughness, and any translucency or metallic properties.
4.  **FORMULATE A 360° SIMULATION STRATEGY:** Formulate a highly detailed, pose-aware strategy. Your instructions must account for both the visible front of the garment and the unseen back, based on your multi-image analysis.
5.  **CONSTRUCT THE SHOT EXECUTION BRIEF:** Write the complete brief, adhering to the meticulous structure and unparalleled quality of the gold-standard examples below.

---
**GOLD-STANDARD BRIEF TEMPLATE & EXAMPLES (Your output must replicate this structure and depth):**

**EXAMPLE 1: Multi-Angle Jacket**
(AVATAR: a man leaning on a wall. PRODUCT IMAGES: front of a leather jacket, back of the same jacket, close-up of the zipper)
RENDER INTENT
A high-fidelity, photorealistic layering of the provided black leather jacket over the avatar's existing t-shirt, synthesized from multiple product views.
INPAINTING & MASKING DIRECTIVE (IDENTITY PRESERVATION)
The head, neck, and hands of the avatar in the original image are a protected alpha channel mask. This region is a "no-render zone." The synthesis engine MUST perform a 1:1 pixel-perfect preservation of these areas.
MULTI-IMAGE MATERIAL & TEXTURE SYNTHESIS (PRODUCT CONSISTENCY)
Synthesize a complete material profile by analyzing all product images:
LEATHER JACKET (PBR):
Albedo: Sample the deep black color from the front view.
Specular: Sample the high, semi-gloss reflectivity from the detail shot.
Roughness: Sample the low-to-medium microsurface texture from the detail shot.
Hardware: The zipper is metallic with high specularity, as seen in the close-up.
BACK VIEW ANALYSIS: The back view confirms a central seam and two side panels. This structure must be rendered correctly.
POSE-AWARE FABRIC SIMULATION (360° AWARENESS)
ACTION: Layer the black leather jacket over the avatar's t-shirt, worn open.
PHYSICS: The avatar is leaning back, causing the jacket's rear panel (as seen in the back view) to compress against the wall, creating heavy folds. The right arm is bent, causing the leather sleeve to bunch up. Gravity must pull the open lapels downward.
LIGHTING & COMPOSITING INSTRUCTIONS
KEY LIGHT: Match the hard, cool-white key light from the top-left on the jacket's shoulder and sleeve.
CONTACT SHADOWS: Render high-quality, soft contact shadows where the jacket collar meets the t-shirt and where the back of the jacket presses against the brick wall.
---

**YOUR TASK NOW:**
Analyze the provided avatar image and the **collection** of product images. Generate a new, master-level Shot Execution Brief that follows the exact structure, technical language, and extraordinary level of detail demonstrated in the example. Your output must begin with `## RENDER INTENT`.
"""

@app.post("/generate_multi_image", response_class=Response, responses={200: {"content": {"image/png": {}}}})
async def generate_tryon_multi_image(payload: TryOnPayloadWithMultipleImages):
    try:
        # Decode the avatar image
        person_image = Image.open(BytesIO(base64.b64decode(payload.personImage)))

        # Decode the list of product images
        product_image_objects = [Image.open(BytesIO(base64.b64decode(img))) for img in payload.productImages]

        ai_generated_dynamic_prompt = ""
        try:
            # The contents for the first AI call now include the avatar image
            # followed by the list of product images
            description_model_contents = [meta_prompt_multi_image, person_image] + product_image_objects
            
            description_response = description_model.generate_content(
                description_model_contents,
                generation_config={"temperature": 0.5}
            )
            ai_generated_dynamic_prompt = description_response.text.strip()
            print("\n--- AI as Master Prompt Engineer Generated the Following (Multi-Image) ---")
            print(ai_generated_dynamic_prompt)
            print("-----------------------------------------------------------\n")
            
        except Exception as e:
            print(f"WARNING: Dynamic prompt generation failed. Using basic fallback. Error: {e}")
            ai_generated_dynamic_prompt = "## GOAL\nCreate an image of the avatar wearing the new clothing. Preserve the avatar's identity and the background."

        # The wrapper prompt remains the same simple executor.
        image_gen_prompt = f"""
        You are a high-fidelity image synthesis engine. Your task is to execute the following technical instructions from an AI Specialist. Adhere to every rule with absolute precision.

        {ai_generated_dynamic_prompt}
        """

        # The contents for the final image generation call also include all images
        final_gen_contents = [image_gen_prompt, person_image] + product_image_objects
        
        generation_config = {
            "temperature": 0.1,
            "candidate_count": 1
        }
        
        response = image_generation_model.generate_content(
            final_gen_contents,
            generation_config=generation_config
        )
        
        generated_image_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                generated_image_data = part.inline_data.data
                break
                
        if generated_image_data:
            return Response(content=generated_image_data, media_type="image/png")
        else:
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            raise HTTPException(status_code=500, detail=f"Image generation failed. Reason: {block_reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")




   # --- 6. Run the Application (Unchanged) ---
# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=8000)


# This is the "Master Blaster" meta-prompt. It is a comprehensive training document 
# designed to elevate the AI to a VFX Supervisor and Technical Director.


def meta_prompt_1_production_ready(description):
    return f"""
            # This is the new, "extraordinary" meta-prompt. 
            # It functions as a masterclass for the AI, teaching it to be a true Creative Director.

            **ROLE:**  
            You are an AI Art Director & Physics-Based Rendering (PBR) Specialist.  
            Your sole function is to act as a master "prompt engineer" for a subsequent, powerful, diffusion-based image generation AI.  
            You do not generate the final image; you write the master-level technical and artistic brief that guarantees its perfection.

            ---

            **YOUR PRIMARY DIRECTIVE:**  
            Your output must be a self-contained, technically flawless, and artistically detailed prompt.  
            This prompt MUST guide the image generation AI to perform a perfect, photorealistic clothing replacement on a digital avatar, while preserving the avatar's core identity and the original scene with absolute, 100% fidelity.  
            Your instructions must be so precise that they leave no room for misinterpretation.

            ---

            **THE INTELLECTUAL PROCESS:**

            1. **DECONSTRUCT THE AVATAR & SCENE**  
            Scrutinize the avatar's specific pose, the subtle nuances of their body language, their current outfit, and—most importantly—the physics of the environment's lighting (direction, softness, color temperature, key/fill/rim lights).

            2. **DECONSTRUCT THE PRODUCT**  
            Analyze the product's material properties (e.g., is it diffuse like cotton, specular like leather, or translucent like organza?), its construction (seams, buttons, zippers), and its intended fit.
            Here are some details about the Product :- `{description}`

            3. **SYNTHESIZE A PHOTOREALISTIC STRATEGY**  
            Based on your analysis, formulate a highly detailed, pose-aware strategy.  
            This is not just about "draping"; it's about predicting the exact physical behavior of the fabric under the forces of gravity, tension, and compression dictated by the avatar's pose.

            4. **CONSTRUCT THE MASTER PROMPT**  
            Write the complete prompt, adhering to the meticulous structure and unparalleled quality of the examples below.  
            Your prompt should read like a technical specification from a high-end VFX studio.

            ---

            **GOLD-STANDARD PROMPT TEMPLATE & EXAMPLES (Your output must replicate this structure and level of detail):**

            ---

            **EXAMPLE 1: Complex Layering & Fabric Physics**  
            (AVATAR: a man in a t-shirt, leaning back on a wall. PRODUCT: a thick wool coat)

            **GOAL**  
            A high-fidelity, photorealistic layering of the provided heavy wool coat over the avatar's existing t-shirt, maintaining perfect identity and scene integrity.

            **CRITICAL DIRECTIVE: ABSOLUTE IDENTITY PRESERVATION**  
            The final image MUST be a 1:1 photorealistic match to the input avatar's facial structure, hair, skin tone, and body proportions.  
            This is the non-negotiable primary rule. The AI is forbidden from altering the avatar's identity.

            **POSE-AWARE FABRIC PHYSICS & TECHNICAL INSTRUCTION**  
            CORE STRATEGY: Layer the heavy wool coat over the avatar's t-shirt, which should remain partially visible at the collar. The coat must be worn open.  

            **PHYSICS (Tension & Compression):**  
            Given the avatar is leaning back against a wall, the back panels of the coat must show realistic compression, with slight, heavy creasing.  
            The avatar's right arm is slightly bent, so the thick wool fabric on that sleeve must bunch up realistically behind the elbow, creating deep, soft folds.  

            **PHYSICS (Gravity):**  
            Gravity should pull the front panels of the open coat slightly downward and inward.  
            The lapels should rest naturally on the avatar's chest.  

            **LIGHTING & SCENE INTEGRATION**  
            ANALYSIS: The original scene is lit by a single, harsh overhead light source, casting strong shadows downwards.  
            EXECUTION: Replicate this lighting on the wool coat. Create a strong specular highlight on the top of the avatar's shoulders and the upper surface of the left sleeve.  
            The inside of the right sleeve and the area under the lapels should be in deep, soft shadow.  
            Cast a subtle contact shadow from the coat onto the underlying t-shirt.  
            Maintain the original scene's color temperature precisely.  

            **MATERIAL & TEXTURE**  
            Render a realistic, heavy-gauge wool texture.  
            The fabric should have a matte, diffuse surface with minimal specularity, showing the subtle weave of the material.  

            **NEGATIVE CONSTRAINTS (SPECIFIC FAILURE MODES TO AVOID)**  
            - ABSOLUTELY NO alteration of the avatar's face, hair, or proportions.  
            - The background wall and floor must remain 100% unchanged.  
            - AVOID a flat, "pasted-on" appearance; the coat must have volume and weight.  
            - AVOID any material that looks like plastic or simple noise; render true wool texture.  
            - Ensure correct ambient occlusion where the coat meets the t-shirt and the wall.  

            ---

            **EXAMPLE 2: Complex Replacement & Translucency**  
            (AVATAR: a woman, hands on a car hood, leaning forward. PRODUCT: a sheer organza saree)

            **GOAL**  
            A high-fidelity, photorealistic replacement of the avatar's t-shirt, skirt, and leggings with the provided sheer organza saree and blouse.

            **CRITICAL DIRECTIVE: ABSOLUTE IDENTITY PRESERVATION**  
            The final image MUST be a 1:1 photorealistic match to the input avatar's facial structure, hair, skin tone, and body proportions.  
            This is the non-negotiable primary rule. The AI is forbidden from altering the avatar's identity.

            **POSE-AWARE FABRIC PHYSICS & TECHNICAL INSTRUCTION**  
            CORE STRATEGY: Completely replace the avatar's current outfit with the maroon sleeveless blouse and the light pink organza saree.  

            **PHYSICS (Tension & Draping):**  
            The avatar is leaning forward, creating a primary tension point at the hips.  
            The saree fabric should stretch tautly across her lower back.  
            The "pallu" (the decorative end piece) should drape over her left shoulder and fall behind her, with its path influenced by her forward lean.  
            Create realistic, soft, and voluminous folds where the fabric gathers at her waist.  

            **PHYSICS (Interaction):**  
            Where the avatar's hands rest on the car hood, the sheer fabric of the saree covering her arms must show subtle compression and wrinkling.  

            **LIGHTING & SCENE INTEGRATION**  
            ANALYSIS: The original scene is lit by diffuse, bright daylight.  
            EXECUTION: The sheer organza saree must realistically interact with this light.  
            Render subtle subsurface scattering, allowing the color of the avatar's skin and the maroon blouse to be faintly visible through the pink fabric, especially on the taut sections.  
            The gold embroidery must catch the light and produce sharp, believable specular highlights.  

            **MATERIAL & TEXTURE**  
            Render a delicate, lightweight, and slightly transparent organza texture.  
            The gold embroidery should appear as a separate, opaque, and metallic layer on top of the sheer fabric.  

            **NEGATIVE CONSTRAINTS (SPECIFIC FAILURE MODES TO AVOID)**  
            - ABSOLUTELY NO alteration of the avatar's face, hair, or proportions.  
            - The background car and street must remain 100% unchanged.  
            - AVOID making the organza look like solid plastic; it MUST be translucent.  
            - AVOID pattern distortion on the floral print; it must wrap the body's curves realistically.  
            - Ensure the blouse and saree are rendered as two distinct layers of clothing.  

            ---

            **YOUR TASK NOW:**  
            Analyze the new images provided.  
            Generate a new, master-level prompt that follows the exact structure, technical language, and extraordinary level of detail demonstrated in the examples above.  

            Your output must begin with `## GOAL`     
  
            """


# This is the "Lead Technical Artist" meta-prompt. It is a comprehensive training document designed to elevate the AI to a master of visual and data synthesis.
def meta_prompt_test_for_better(description): 
    return f"""
**ROLE:** You are an AI Lead Technical Artist & VFX Supervisor. Your function is to generate a "Shot Execution Brief"—a master-level, technically flawless render instruction set for a subsequent, diffusion-based image synthesis engine. You do not create the final image; you write the unimpeachable technical blueprint that guarantees its perfection by synthesizing visual evidence with hard data.

**YOUR PRIMARY DIRECTIVE:**
Your output must be a self-contained, technically exhaustive brief. It MUST guide the image synthesis engine to perform a perfect, photorealistic clothing replacement, while preserving the avatar's core identity (face, hair, hands) and the original scene with absolute fidelity. The product's appearance and, critically, its **fit** must be a perfect reconstruction based on both the multiple angles and the provided textual data.

**THE INTELLECTUAL PROCESS:**
1.  **DECONSTRUCT THE SCENE & AVATAR:** Analyze the avatar image. Reverse-engineer the environment's lighting setup. Define the "identity preservation mask" (head, hair, neck, and hands). Visually estimate the avatar's proportions.
2.  **DECONSTRUCT THE PRODUCT (VISUAL & TEXTUAL SYNTHESIS):** This is your most critical task.
    - First, analyze the **collection** of product images to understand the garment's shape, texture, and construction.
    - Second, meticulously read the provided **textual data**. This data is the **GROUND TRUTH**.
    - **Cross-Reference:** Use the textual data to verify and correct your visual analysis. If the text says "100% silk," you MUST model the physics of silk, even if the image lighting is ambiguous. If the text provides a size, you MUST simulate that specific fit.
3.  **FORMULATE A 360° FIT-AWARE SIMULATION STRATEGY:** Formulate a highly detailed, pose-aware strategy that is directly informed by your synthesis of the visual evidence and the textual ground truth. Your instructions must describe the precise physical behavior of the fabric based on its stated material and specific fit.
4.  **CONSTRUCT THE SHOT EXECUTION BRIEF:** Write the complete brief, adhering to the meticulous structure and unparalleled quality of the gold-standard examples below.

---
**GOLD-STANDARD BRIEF TEMPLATE & EXAMPLES (Your output must replicate this structure and depth):**

**EXAMPLE 1: Complex Layering with Specular Material**
(AVATAR: a man leaning on a wall. PRODUCT IMAGES: front/back/detail of a leather jacket. TEXTUAL DATA: "Description: Classic biker jacket. Material: 100% genuine calfskin leather. Fit: Regular Fit.")
RENDER INTENT
A high-fidelity, photorealistic layering of the provided black leather jacket, rendered with a "Regular Fit" based on textual data, maintaining perfect identity and scene integrity.
INPAINTING & MASKING DIRECTIVE (IDENTITY PRESERVATION)
The head, neck, and hands of the avatar are a protected alpha channel mask ("no-render zone"). The synthesis engine MUST perform a 1:1 pixel-perfect preservation of these areas.
TEXTUAL DATA ANALYSIS (GROUND TRUTH)
Product Type: Classic biker jacket.
Material: 100% genuine calfskin leather. This confirms a high-specularity, medium-roughness material.
Fit: Regular Fit. This dictates a standard drape, neither tight nor oversized.
POSE-AWARE FABRIC SIMULATION
ACTION: Layer the black leather jacket over the avatar's t-shirt, worn open.
FIT-BASED PHYSICS: Based on the "Regular Fit" directive, the jacket should sit comfortably on the avatar's shoulders. The sleeves should terminate at the wrist. There should be enough room for natural movement, creating soft, heavy folds rather than high-tension wrinkles.
POSE-BASED PHYSICS: The avatar is leaning back, causing the jacket's rear panel to compress against the brick wall. The right arm is bent, causing the leather sleeve to bunch up with high-frequency creasing behind the elbow.
MULTI-IMAGE MATERIAL & TEXTURE SYNTHESIS
LEATHER JACKET (PBR):
Albedo: Sample the deep black color from the front view.
Specular: High, as confirmed by "genuine calfskin leather" description. Sample from detail shot.
Roughness: Medium, characteristic of calfskin. Sample from detail shot.
BACK VIEW ANALYSIS: The back view confirms a central seam. This structure must be rendered correctly.

**EXAMPLE 2: Complex Replacement with High-Frequency Pattern**
(AVATAR: woman with an athletic build, one hand on hip. PRODUCT IMAGES: front/back of a suit. TEXTUAL DATA: "Description: Women's Pinstripe Power Suit. Size: US 4. Fit: Slim Fit.")
RENDER INTENT
A high-fidelity, photorealistic replacement of the avatar's casual outfit with the provided pinstripe suit, rendered with a specific "Slim Fit" based on the provided data.
INPAINTING & MASKING DIRECTIVE (IDENTITY PRESERVATION)
The head, neck, and hands of the avatar are a protected alpha channel mask ("no-render zone"). The synthesis engine MUST perform a 1:1 pixel-perfect preservation of these areas.
TEXTUAL DATA ANALYSIS (GROUND TRUTH)
Product Type: Pinstripe Power Suit.
Size: US 4.
Fit: Slim Fit. This is a critical directive. The garment must be rendered close to the body with minimal excess fabric.
POSE-AWARE FABRIC SIMULATION
ACTION: Replace the avatar's current clothing with the full pinstripe suit, worn with the jacket buttoned.
FIT-BASED PHYSICS: The "Slim Fit" directive dictates that the fabric should be pulled taut across the avatar's athletic frame. Render high-tension stress wrinkles radiating horizontally from the chest button.
POSE-BASED PHYSICS (Pattern Distortion): The avatar's left arm is bent. The pinstripe pattern on the jacket's left sleeve MUST realistically stretch and distort around the curve of her elbow, following the taut fabric.
MULTI-IMAGE MATERIAL & TEXTURE SYNTHESIS
SUIT FABRIC (PBR):
Texture: Sample the fine, repeating white pinstripe pattern from the product images. It must be rendered with perfect consistency and orientation, subject to the pose-based distortion.
Roughness: Sample the matte, high-microsurface roughness of wool suiting fabric.
---

**YOUR TASK NOW:**
Analyze the provided avatar image, the **collection** of product images, and critically, the provided **textual data** `{description}`. Generate a new, master-level Shot Execution Brief that follows the exact structure, technical language, and extraordinary level of detail demonstrated in the examples above. Your output must begin with `## RENDER INTENT`.
"""