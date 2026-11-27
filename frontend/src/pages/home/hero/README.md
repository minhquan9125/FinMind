# FinMind MacBook Pro hero

## Integration

Copy `public/` into the frontend public directory. Keep `LaptopHero.jsx`,
`Laptop3D.tsx`, `macbookModel.ts`, `rotationInput.js` and `laptopHero.css` together. Render
`<LaptopHero />` inside the existing hero section with `id="research"`.
No backend, API, account, router or business feature is required by this visual.

LaptopHero owns lazy loading, a pre-rendered MacBook poster, WebGL/capability
checks, an error boundary, passive pointer/scroll listeners and page visibility.
Laptop3D owns the R3F scene, frame loop, lighting and adaptive quality.
macbookModel owns model validation, geometry partition and material batching.

## Source and model contract

Model: "macbook pro M3 16 inch 2024" by jackbaeten, CC BY 4.0.
Original: https://sketchfab.com/3d-models/macbook-pro-m3-16-inch-2024-8e34fc2b303144f78490007d91ff57c4
Distribution: https://github.com/adrianhajdin/gsap_macbook_landing/blob/main/public/models/macbook-16-transformed.glb
Attribution, license link and changes: public/models/laptop.LICENSE.txt.
The same information remains in the GLB's asset.extras metadata.

The 629,720-byte GLB contains 19 flattened meshes, Draco geometry and embedded
WebP/PBR textures up to 1024 pixels. Mesh Object_123 is the notched display.
The original asset has no hinge node or animation clip. Several primitives mix
lid and chassis triangles. macbookModel bakes source matrices once, partitions
triangle indices above world Y=1.12, and reconstructs FinMindHinge at
[0,0.6,-12.75]. Closed X=1.92 radians; original open pose X=0.
All 112,502 triangles of this compressed distribution are retained.

Materials retain their normal, tangent, roughness/metalness and alpha maps.
Only equivalent opaque palette materials 001/003 are shared. Palette 002 is
separate because it uses BLEND alpha. Batches use 21 model draw calls; the full
transparent studio scene measured 25 calls after removing the ground plane.
Dashboard texture is sRGB, flipY=true, anisotropy <=8. Original screen UVs/notch
are preserved. The static product screen is an unsigned-in empty workspace;
there are no financial values, invented chart or fake account.

## Rendering and motion

React 18.3.1 / Fiber 8.18.0 / Drei 9.122.0 / Three 0.169.0 retained.
React TypeScript declarations are aligned to React 18.
Camera: 38-degree FOV, target [0,.65,0], automatically fit to the complete
rotation envelope. Bounds include only referenced geometry vertices. The model
rotates around its center, rather than swinging around the chassis origin.
Three local rectangular studio softboxes, a key light and a 256px environment
capture render once. No external HDR or CDN decoder is used by this hero.
A soft CSS ambient shadow replaces the floor plane, so an inverted laptop
cannot intersect a baked ground shadow. The WebGL canvas clears to alpha zero,
extends across the hero and shares its continuous background without a frame.

Animation mutates transforms in the R3F frame loop with power-out entrance
easing and delta-based damping. The reference's GSAP transform/timeline ideas
were studied; adding a second animation ticker or transparent crossfading
models was unnecessary here. No reference application source is copied.
Native scrolling is not pinned or intercepted. Mouse drags rotate freely in both
axes using normalized quaternion composition and frame-rate-independent slerp.
Vertical touch gestures scroll by default; an explicit free-rotation toggle
enables both touch axes. Finishing touch mode restores ordinary page gestures.
Four arrow buttons and arrow keys offer a non-drag alternative; Home and Reset
restore the initial pose. Manual rotation invalidates demand rendering, so it
also works when automatic motion is paused or reduced motion is enabled.
The optional motionPaused prop lets the landing pause all presentation motion.
The production landing now follows FinMind-Full-UI-Review.html, with this MacBook
replacing the original CSS illustration. Its screen and fallback poster show
an unsigned-in workspace without financial values. It is not a live market feed.
The integrating site must retain the model author, source, license and change
notice, e.g. in its footer asset credits.

Desktop targets the display refresh rate with `always` while active. DPR <=1.5
desktop /1.25 mobile. Offscreen, hidden tab, pause and reduced motion use demand
rendering. Reduced motion opens the laptop immediately in a frontal pose.
Low memory/CPU, Save-Data or insufficient WebGL uses the pre-rendered poster.
For sustained slow rendering, DPR first drops to 1; repeated <22 FPS windows
then replace the canvas with the poster. GLB failures and context loss do so too.

## Validation on this machine

Strict TypeScript checking and production Vite build are required.
Functional browser checks include hinge/texture, mouse/scroll, pause, offscreen,
reduced motion, six widths, context loss, missing GLB and weak-device fallback.
Desktop benchmark: Chrome/ANGLE D3D11, NVIDIA GTX 1050 Ti, 1440x1000 viewport,
six-second samples after warm-up: ~100.1 FPS at DPR 1 and ~100.1 FPS at DPR 1.5
with the full-width canvas (1440x780 CSS pixels).
These are measurements on this GPU, not a guarantee for other devices.
The separate mascot is minimized by default in the approved frontend layout.
