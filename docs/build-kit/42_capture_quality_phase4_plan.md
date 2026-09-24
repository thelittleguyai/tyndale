# 42 · Capture quality: the Phase 4 (A9) plan, costed

**Status: PLAN.** Docs only; no code in this item (guided Phase 2, item I). It implements
Brock's decision 3 (2026-09-21):

- A9 supersedes N1 and B2.
- It is "the real capability": live edge detection plus glare/blur feedback in the viewfinder,
  tied to actual capture quality.
- It is Phase 4, costed as its own phase.
- Native capture stays parked on DL-44.

Spec: doc 40 §A9, priorities (1) to (7).

## Where capture stands today

| A9 priority | status |
|---|---|
| 1 · live gating: edges, glare/blur/skew feedback, auto-capture | **Phase 4.** Today the guide frame is static, and quality is measured after the shutter, not live |
| 2 · per-page quality score + retake; multi-page; native-PDF path | **Partly.** Multi-page capture and retake exist; there is no score and no native-PDF text path. Phase 4 builds both |
| 3 · document-type classification with confidence | exists: the upload classifier and the four `wrongdoc.*` branches |
| 4 · itemized-vs-summary detection | exists: `bill_heuristics.detect_summary_bill` leads to the planner's `bill_itemized` coaching |
| 5 · confidence-gated extraction | exists: low-confidence card reads arrive pre-filled on the insurer screen, never silent; the fabrication guard covers codes |
| 6 · PHI: on-device pre-processing | partly: downscale to 1600 px and EXIF stripping run on the device. Phase 4 keeps every live frame on it |
| 7 · a capture test corpus tracked in evals | **Phase 4** (sections 4–5) |

What Phase 4 builds on:

- **Web**, the member surface (`app.tyndaleapp.net`). `apps/mobile/components/upload/CameraCapture.tsx`
  runs a getUserMedia viewfinder with a static guide frame. After the shutter it takes two
  measurements from `apps/mobile/lib/capture.ts`:
  - the resolution floor: `MIN_OCR_EDGE` = 900 px;
  - variance-of-Laplacian sharpness at 640 px: `BLUR_VARIANCE_FLOOR` = 45.

  Then review, keep or retake, multi-page with ordered names, and a 1600 px JPEG. **The honesty
  rule** (header of `lib/capture.ts`): only a warning backed by a measurement is shown, and
  there is never a "readable" badge.
- **Native.** `CameraCapture.native.tsx` runs on expo-camera. It landed on 2026-08-17, when
  DL-44's blocker was removed (8fd6b91, 41b7734). The flow is the same, but only the resolution
  floor is measured: expo-camera gives no pixel access, so blur is "not measured" and never
  "sharp".
- **Housekeeping for S2.** The header of `CameraCapture.tsx` still says expo-camera cannot be
  installed because of DL-44. That was true until 2026-08-17.

## 1 · Live capture gating on web (A9-1)

**Per analyzed frame, on the device only:**

- **Loop.** `requestVideoFrameCallback` where available, else rAF. About 6–8 analyzed fps on a
  320–480 px sample, in a Web Worker (OffscreenCanvas / a transferred ImageBitmap), so the
  viewfinder never stutters.
- **Sharpness.** The existing variance-of-Laplacian, already written and tested, run live.
- **Glare.** The share of near-saturated pixels inside the page, plus the largest saturated
  patch. The hint names what it measured ("Glare on the page. Tilt it away from the light.").
- **Edges → coverage, skew, cut-off.** Find the page's four corners. The quad gives:
  - coverage: quad area over frame area;
  - skew: the corners' departure from a rectangle;
  - cut-off: a corner on the frame edge.
- **Auto-capture.** The shutter fires, with a visible pulse, when all of these hold:
  - the quad is stable (corners move less than ~2% of frame width over ~600 ms);
  - sharpness is above the floor;
  - glare is below the ceiling;
  - coverage is at least ~50%.

  The concept's "Snap automatically" is right. The manual shutter always works.
- **On keep.** Optional perspective crop to the quad, behind a flag. The evals decide whether it
  raises Document Intelligence accuracy.

**The honesty rule carries over unchanged.** The overlay draws the DETECTED quad, which is a
measurement. Nothing animates when nothing is detected: no fake "locking on", which was N1's
objection. Hints name their measurement. There is still no "readable" badge (B2's objection).

**Candidate libraries.** Only edge detection needs one; blur and glare are a few dozen lines of
the existing pure-function pattern. Sizes are the npm registry's `dist.unpackedSize` on
2026-09-24. That counts every build, map and type file, so it is an upper bound, not shipped
bytes. Measuring shipped gzip bytes is step 1 of the spike (S1).

| option | how | license | npm unpacked | notes |
|---|---|---|---|---|
| **Hand-rolled** | downscale → Sobel / Canny-lite → largest convex quad (contour + polygon approximation), in plain TS | ours | ~0 | Zero bundle, and testable like `lib/capture.ts`. Weaker on busy backgrounds; the corpus says how much weaker |
| **OpenCV.js** (`@techstark/opencv-js` 5.0.0-release.1) | Canny + findContours + approxPolyDP (+ warpPerspective for the crop) | Apache-2.0 | 14.7 MB | Robust and heavy. Lazy-load only; a custom imgproc-only build cuts it |
| **jscanify** 1.4.3 | document detection and extraction on top of OpenCV.js | MIT | 30.4 MB (includes Node-side canvas / jsdom) | A convenience wrapper; the same OpenCV payload in the browser |
| **ML corner model** on `onnxruntime-web` 1.30.0 or TF.js 4.22 (`tfjs-core` + wasm backend) | a small document-corner / segmentation model | MIT / Apache-2.0 | 144.6 MB (all execution providers) / 37.1 + 13.2 MB | Best on clutter. The open questions are sourcing the model and its license, and the payload once trimmed to one wasm backend |
| **Commercial SDKs**: Dynamsoft Document Normalizer 2.6.11, Scanbot Web SDK 9.0.0 | edge detection + auto-capture + crop, polished | commercial | 1.1 MB loader (wasm fetched at runtime) / 138.4 MB | Fastest to ship; per-scan or per-seat fees. **A vendor that ever sees a frame joins the PHI boundary** (the DL-49 BAA list has five names), so it must be proven that only license pings leave the device |

**Recommendation.** Build blur and glare hand-rolled; they are half built. Spike edge detection
two ways, hand-rolled quad against a custom OpenCV.js build, on the corpus seed. Pick on three
measures:

- detection rate on the bad-light set;
- shipped gzip bytes;
- frame time on a mid-range Android phone.

A commercial SDK comes in only if both fail the bar, because it adds a vendor to the PHI
question.

**Budget and fallback.**

- The detector never enters the main bundle: a dynamic import when the camera opens.
- Proposed budget: ≤ 1.5 MB gzip, lazy; ≤ 30 ms per analyzed frame on a mid-range Android
  phone in Chrome.
- Analysis pauses when the tab is hidden.
- If the detector has not loaded in ~3 s, or frames run over budget, the loop stays off and
  capture works exactly as it does today (static guide, measured warnings after the shutter).
  Nobody waits on it.
- iOS Safari supports getUserMedia. Its worker-side OffscreenCanvas is recent, so older iOS
  analyzes on the main thread at a lower rate. Confirm on the target devices in S1.

**On-device only: no frames leave the device.** Frames live in the worker's memory. They are
never uploaded, logged or sent to analytics. The page the member KEEPS is uploaded, exactly as
today. Capture analytics stay enum/number (`capture_auto_fired`, `capture_hint{kind}`), per the
PHI-free rule. A guard test pins that the worker module uses no network API (no `fetch`,
`XMLHttpRequest`, `WebSocket` or `sendBeacon`).

## 2 · Per-page quality score + retake prompt (A9-2)

- **Client, per page.** Each kept page carries its measurements: longest edge, sharpness,
  glare share, coverage, skew, and whether it was auto-captured. The verdict is a list of
  measured problems, never a pass.
  - The thumbnail strip marks pages with a problem.
  - Retake replaces the page in place.
- **Server, tied to actual capture quality.** After OCR, Document Intelligence's per-word
  confidence on each page, and whether the fields the planner needs came out, become a per-page
  `read_quality` on the document entry. When it is low, the planner's capture screen says so at
  once, through the existing `note` slot ("I couldn't read page 2 well. Retake it?"). The member
  is still on that screen: the page is replaced, not added as a new document.

  This half covers native uploads and picked files too. It reads the OCR, not the camera.
- **Calibrated, not guessed.** The thresholds come from the corpus (section 4), including a
  second look at `BLUR_VARIANCE_FLOOR` = 45.
- **Native-PDF path** (A9-2's last clause). A digital PDF, such as a portal download, carries a
  text layer. When that layer covers every page, use it and skip OCR: it is exact, cheaper and
  faster. The document records `ocr_skipped: text_layer`.
- **Copy.** Live hints, the auto-capture cue and retake prompts are new `intake.*` keys: graded
  ≤ 5.9 and PROPOSED for Brock in the v2 DRAFT.

## 3 · Native: parked on DL-44, and the unblock path

**What is actually parked.** DL-44's blocker was `react-native-worklets`' peer range against
our React Native 0.79.6. It was removed on 2026-08-17, so native **capture** exists. What
remains parked is **live frame analysis** on native:

- expo-camera gives no per-frame pixel access;
- VisionCamera's frame processors run on a worklet runtime, which brings back exactly the
  DL-44 conflict class.

That peer range moves with every release: 0.9.1 peered RN 0.83–0.86, and 0.13.0 peers RN
0.86–0.88 today. Pinning an old worklets is therefore not a path. DL-48 matters too: V1-Lite is
web-only, and native distribution is deferred.

**Unblock path, in order:**

1. **When native becomes a product priority (DL-48 revisited), use the platform document
   scanners.** iOS VisionKit's document camera and Android ML Kit's document scanner, through a
   small native module. One candidate is `react-native-document-scanner-plugin` 2.0.4 (MIT,
   54 KB unpacked); which platform APIs it wraps is to be confirmed in S1. The OS provides
   edge detection, auto-capture and perspective correction on the device. There is no JS frame
   loop and no worklets, so this route is **not blocked by DL-44**. It needs a dev build
   (prebuild / EAS), not Expo Go.
2. **Only if a Tyndale-drawn overlay is required on native: an Expo SDK upgrade** (we are on
   53; npm shows `expo` 57.0.25 today). The upgrade must put React Native inside the
   then-current worklets peer range; VisionCamera (5.2.3) frame processors then run web's
   detector. That is its own project. `apps/mobile/babel.config.js` inlines the NativeWind
   preset minus its worklets plugin, and has to be revisited with it, and only a clean-install
   `expo export` proves that path.
3. **Either way, the server half of section 2 already covers native uploads.**

## 4 · The capture test corpus (A9-7) — and its PHI

**What.** About 100 captures to start:

- **8 document types:** itemized bill, summary bill, EOB, card front/back, SBC page, MSN, portal
  screenshot, not-a-document.
- **7 conditions:** good light, dim, glare from a window or lamp, 15–30° skew, a corner cut off,
  folded or crumpled, and small print at arm's length.
- **At least 3 phones,** one of them an older Android.

**Where the documents come from, PHI-free first:**

1. **Synthetic, the bulk.** The e2e generator (`runtime/scripts/e2e_scenarios/generate_docs.py`)
   renders bills, EOBs, cards and SBCs with known values. Print them and photograph them under
   each condition. That gives exact labels and zero PHI.
2. **Public samples.** The CMS sample SBC / MSN and the sources in
   `docs/research/example_documents_sources_2026-09-17.md`, printed and photographed.
3. **Real documents,** for the one thing synthetic cannot give: real provider and payer layouts.
   Every one of these conditions must hold:
   - written consent from the document's owner (team members first), under the two-consent
     model's improvement consent;
   - **de-identified before storage**: names, member IDs, account numbers, addresses and DOB
     covered on the paper before the photo, or pixel-redacted;
   - stored in a restricted, access-logged Azure Blob container under the Azure BAA;
   - never in git, and never on a laptop outside an eval run;
   - a documented purge date, in the spirit of doc 43.

**In the repo:** a manifest only. It holds IDs, document type, condition, phone, synthetic
ground-truth labels and content hashes. No image, no PHI.

## 5 · The evals hook

A deterministic runner beside the golden harness:
`intelligence-layer/evals/capture/run_capture_evals.py`. It uses no LLM judge, because a capture
score is a measurement. It changes no judge rubric.

- **Offline** (CI, in `evals.yml`'s existing job): validates the manifest against its schema,
  like the golden runner's offline mode.
- **Live** (dev, `TYNDALE_EVALS_LIVE=1`, under the Azure BAA): per capture, it runs
  - (a) the client scorer: the same pure TS functions the app runs, executed in Node;
  - (b) the server pipeline: upload → classifier → Document Intelligence OCR → extraction.

  It scores each field against ground truth: payer, member ID, date of service, codes,
  billed / allowed amounts, account number.
- **Tracked:**
  - extraction accuracy per document type and per condition;
  - classifier accuracy;
  - how well the quality score predicts an extraction failure (the ROC that picks the retake
    threshold);
  - the **false-retake rate** (good photos flagged, the honesty rule's cost);
  - the **miss rate** (bad photos passed).
- **Proposed Phase 4 ship gate:**
  - auto-capture never lowers extraction accuracy vs manual on the corpus;
  - false-retake ≤ 10%;
  - the bad-light miss rate is half of today's.
- Reports carry numbers only, never OCR text, so they can live in the repo.

## 6 · Session estimate

| session | scope | notes |
|---|---|---|
| S1 · spike | shipped gzip bytes + frame time: hand-rolled quad vs an OpenCV.js custom build on 3 phones; confirm the platform-scanner module's APIs; corpus seed (~20 synthetic captures) | 1 session; decides the library |
| S2 · live loop | worker frame loop; live sharpness + glare hints in the viewfinder; lazy-load + fallback; the stale header fix | 1 session; jest on the pure functions |
| S3 · edges + auto-capture | quad detection + overlay, skew / cut-off, stability → auto-shutter, perspective crop behind a flag | 1–2 sessions |
| S4 · per-page score + server read quality | per-page verdict + thumbnail strip; Document Intelligence confidence → `read_quality`; the planner's retake note; the native-PDF text path; new copy PROPOSED | 1 session |
| S5 · corpus + evals | manifest schema, runner (offline + live), threshold calibration | 1–2 sessions, plus human time: about half a day photographing the synthetic / public set; consent and de-identification for any real documents |
| native | nothing now. If unparked via the platform scanners: the module + a dev-build pipeline | 1–2 sessions, excluding Apple enrollment (DL-48) |

**Web + corpus + evals: 5–7 sessions.** Phase 4 follows Phase 3 (coverage branches), per the
confirmed sequencing.

## Open for Brock

1. The ship-gate numbers in section 5.
2. Whether real-document captures are collected at all before launch, or synthetic + public only
   until beta.
3. Auto-capture on by default? The concept says yes; manual always stays.
4. Copy for the live hints and retake prompts (PROPOSED keys in S2 / S4).
