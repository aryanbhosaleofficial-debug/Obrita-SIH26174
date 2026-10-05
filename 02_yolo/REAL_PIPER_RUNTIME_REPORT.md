# MODULE 02 REAL PIPER RUNTIME + LATENCY REPORT

## Overall Verdict

**BLOCKED BY WINDOWS POLICY**

Verified 2026-10-05. Diagnostics establish Smart App Control rejection of the official Piper wheel's native phonemizer. Architecture/runtime code unchanged. No supported approved alternate runtime was found. [Policy-owner packet](PIPER_POLICY_OWNER_REPORT.md) records the required binary/trust evidence.

## Original Blocker

- Error: ImportError: DLL load failed while importing espeakbridge: An Application Control policy has blocked this file.
- Blocked file: espeakbridge.pyd, 500,224 bytes, unsigned.
- Absolute path: C:\Users\lalit\OneDrive\Desktop\Aryan\Project\SIH26174\Obrita-SIH26174\.venv\Lib\site-packages\piper\espeakbridge.pyd
- SHA-256 (flat/full file): 29631a68cf69727df76071561c9d839dfd05ae326e7f4ed01ae4a69d03f63429
- Windows policy: Smart App Control, VerifiedAndReputableDesktop, GUID {0283AC0F-FFF1-49AE-ADA1-8A933130CAD6}, version 27555.1000.240208.
- Code Integrity evidence: events 3077/3033 explicitly identify the native file and signing rejection. XML requested/validated signing levels 2/1, status 0xc0e90002. Event 3099 identifies activated policy. Read-only SAC state = 1. No matching Piper block in inspected AppLocker logs.

The direct project API traceback goes through alerts/piper_tts.py:62 -> PiperVoice.synthesize_wav -> synthesize -> phonemize -> EspeakPhonemizer -> import espeakbridge, which raises the ImportError above. Top-level import piper succeeds.

## Solution

- Solution type: policy-owner/trusted-publisher runtime review required; runtime blocker unresolved.
- Environment changes: official PyPI wheel downloaded for static integrity comparison; one temporary clean venv attempt outside repository was blocked at its Python launcher before installing packages. Existing .venv packages unchanged.
- Piper changes: NONE.
- Module 02 source changes: NONE. Documentation only: README updated; this report and PIPER_POLICY_OWNER_REPORT.md added.
- Windows security disabled: NO. Defender antivirus, real-time protection, service and tamper protection all enabled; SAC state remains 1.
- ADMIN/POLICY OWNER APPROVAL REQUIRED. Built-in SAC has no individual-app exception according to the [Microsoft FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions); do not assume an admin hash allowlist will fix it. Obtain a properly trusted publisher runtime or use another approved machine. No bypass was attempted.
- Installed native binary matches the official PyPI 1.8.0 wheel byte-for-byte. Wheel digest matches PyPI metadata. Original pip metadata has no direct URL, so historic index is not recorded.
- Local piper.exe is a Python console launcher, not a separate approved synthesis runtime. No approved alternative found in searched installed locations. WSL is absent; no alternate approved machine was available.

## Runtime

- Python: project .venv, Python 3.11.16, x64, Windows build 26300.
- Piper package: piper-tts.
- Piper version: 1.8.0.
- ONNX Runtime: 1.30.0.
- SoundDevice: 0.5.6.
- Package locations: project .venv/Lib/site-packages.
- Global Python 3.14 was not used.

## Voice

- Voice: en_US-lessac-medium; English eSpeak en-us.
- ONNX: C:\Users\lalit\AppData\Local\ORBITA\voices\en_US-lessac-medium.onnx
- JSON: same path plus .json.
- Sample rate: 22,050 Hz.
- Model load: PASS; one direct load measured 1647.0247 ms. This is model loading, not warning-start latency.
- Model/config SHA-256: 5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f / efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0.

## Real Synthesis

- Piper load: PASS.
- Real synthesis: BLOCKED by native import policy.
- PCM generated: NO.
- Real speaker playback: NOT INVOKED.
- Offline: local speech design/assets intact; no runtime model download/cloud. Official PyPI was accessed only for source integrity verification.
- Actual production-manager instrumentation: voice loaded once; 21 planned procedure phrases; 1 synthesis attempt; 0 successful syntheses; 0 cache entries/bytes; VOICE_UNAVAILABLE. Pre-synthesis/cache reuse cannot be verified until synthesis succeeds.

## Real Procedure Warning

- Procedure: examples/red_yellow_procedure.md.
- Violation: injected PICK_RED -> PLACE_RED emits SKIPPED_STEP and leaves MANIPULATE_RED expected. After reset, injected PICK_YELLOW while PICK_RED expected emits WRONG_ORDER without advancement.
- Qwen required: NO for these deterministic injected checks.
- Piper audio: NONE, policy blocked.
- Speaker: NOT INVOKED.
- These are injected-event validator checks, not camera-observed physical actions or successful spoken demonstrations.

## Warm Cached Latency

- Samples: 0 valid (10 requested by benchmark).
- Min / median / p95 / max: NOT VERIFIED.
- <=1500 ms: NOT VERIFIED.

## Cold Latency

- Samples: 0 valid.
- Min / median / p95 / max: NOT VERIFIED.
- <=1500 ms: NOT VERIFIED.
- Existing tool was invoked with 3 cold assistant recreations but stopped on the first policy failure. No fresh-process cold audio sample completed. Retest instructions specify three separate approved project-Python processes to include startup/load/pre-synthesis cost.

## Dynamic Uncached Latency

- Samples: 0 valid (3 requested).
- Min / median / p95 / max: NOT VERIFIED.
- <=1500 ms: NOT VERIFIED.

No substitute PCM or fabricated numbers. Existing perf_counter/relative PortAudio delta/leading-silence architecture remains unchanged. No physical-action-to-confirmation or end-to-end acoustic timing was measured.

## Qwen Busy Test

- Qwen state: real concurrent speech test not started because Piper cannot synthesize.
- Fast violation: independent-of-blocked-Qwen unit regression PASS.
- Voice latency: NOT VERIFIED.
- Waited for Qwen: NO in mocked independence regression; real Piper concurrency NOT VERIFIED.

## Ollama Unavailable Test

- YOLO: PASS, real best.pt native CLI with localhost:1.
- Procedure: ACTIVE; injected skip/wrong-order logic separately PASS.
- Piper: VOICE_UNAVAILABLE due to native policy.
- Voice latency: NOT VERIFIED.

## Preemption

- Next-step playing: no actual speech started.
- Error triggered: unit preemption regression PASS.
- Preempted: real Piper playback NOT VERIFIED.
- Error warning latency: NOT VERIFIED.
- Duplicate suppression and reset/new-generation acceptance: mocked regression tests PASS; real audio tests blocked.

## Failure Isolation

- Voice failure: real blocked Piper native component isolated as VOICE_UNAVAILABLE.
- YOLO: real image/video processing continued, CLI returned success.
- Tracking: real ByteTrack ID 1 persisted across four repeated detected frames in native verification.
- Procedure: continues; injected skip/wrong-order remain correct.
- Renderer: annotated four-frame procedure MP4 produced despite voice/Ollama failures.
- Logging: actual reason/events recorded in external JSONL.
- Native full Module 01 -> Module 02 -> Module 03 and copied standalone with SIH imports/network forbidden: PASS.
- No simulated failure-after-success test with real Piper was possible because initial synthesis never succeeded.

## Module 01

Changes: NONE.

## Module 03

Changes: NONE.

## ObjectFrame

Changed: NO.

## Tests

- Module 02: 256 passed in 2.71 s.
- Full repository: 410 passed, 99 skipped in 6.07 s.
- Commands used project .venv:
  - -m pytest 02_yolo/tests --basetemp <scratch>/unit -q -p no:cacheprovider
  - -m pytest --basetemp <scratch>/full -q -p no:cacheprovider

## Static Checks

- Ruff: PASS.
- Format: PASS (102 files).
- Type: PASS (48 source files).
- Compileall: PASS.
- Git diff --check: PASS; CRLF notices are informational.
- Commands: -m ruff check 02_yolo; -m ruff format --check 02_yolo; -m yolo.tests.verify_types; -m compileall -q 02_yolo; git diff --check, invoked separately.

## Remaining Limitations

PIPER RUNTIME BLOCKED BY MACHINE POLICY. No valid real synthesis, playback or latency samples. The <=1.5 s target remains unverified, not measured as missed.

A policy owner/publisher must provide an approved runtime or approved alternate machine; disabling SAC/Defender/WDAC is prohibited and was not done. Ownership of every possible management channel could not be confirmed; workgroup and all inspected join indicators are NO, and CiTool policy listing was access denied.

Physical camera/operator-action accuracy, CUDA, FPS, rotation/microgravity and acoustic onset remain unverified. No procedure, detector, Qwen or alert code was changed. Previous uncommitted work preserved; no commit/tag created.

Scratch/evidence/partial clean venv and media are outside the repository at C:\Users\lalit\AppData\Local\Temp\orbita-piper-runtime-_1jvphq3. Only intentional Markdown documentation was added/updated in this pass.

REAL PIPER STILL BLOCKED BY WINDOWS APPLICATION CONTROL

