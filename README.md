LUMINA VISUALS | Technical Overview
Lumina Visuals is a private AI-powered image generation dashboard. The application is designed to provide a seamless interface for creating high-quality visual content using advanced AI models, specifically optimized for speed and artistic precision.

🖥️ System Architecture
The project is split into two main components:

Client-Side (Frontend): A minimalist, dark-themed interface built with Tailwind CSS. It handles user inputs (prompts, styles, aspect ratios) and manages the session gallery.

Server-Side (Backend): A FastAPI server that acts as a secure bridge between the interface and the AI engine. It manages API authentication, image processing, and session-based archiving.

🗝️ Core Functionalities
1. High-Speed Generation
The studio uses the Z-Image-Turbo engine via Evolink.ai. This model is specifically chosen for its ability to generate high-fidelity images in a "Turbo" fashion, significantly reducing the wait time compared to standard diffusion models.

2. Intelligent Styling System
The backend includes pre-configured style anchors:

Photorealistic: Optimized for cinematic lighting and high skin detail.

Cyberpunk: Focused on neon aesthetics and volumetric fog.

Fantasy: Enhances textures and dramatic natural lighting.

Anime: Balances cel-shading and clean line art.

Oil Painting: Simulates traditional brushstrokes and canvas textures.

3. Smart Aspect Ratio Management
Users can toggle between different formats without distorting the final output:

1:1: Standard square format for social media.

16:9: Widescreen cinematic format.

9:16: Vertical format optimized for mobile devices and stories.

4. Advanced Session Management
Real-time Gallery: Every image generated in a session is stored in a horizontal scrollable gallery for quick comparison.

Bulk Export: A dedicated /zip endpoint allows the user to package all generated images into a single ZIP file for local storage.

Security: API credentials are never exposed to the client-side, being handled exclusively through server-side environment variables.
