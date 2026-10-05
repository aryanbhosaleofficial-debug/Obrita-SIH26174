# Piper native dependency — policy-owner review packet

Verified 2026-10-05. **ADMIN/POLICY OWNER APPROVAL REQUIRED.**
This document requests trust/runtime review, not disabling security. No policy was changed.

## Binary requiring review

- File: espeakbridge.pyd (500,224 bytes).
- Absolute path: C:\Users\lalit\OneDrive\Desktop\Aryan\Project\SIH26174\Obrita-SIH26174\.venv\Lib\site-packages\piper\espeakbridge.pyd
- Full-file/flat SHA-256: 29631a68cf69727df76071561c9d839dfd05ae326e7f4ed01ae4a69d03f63429
- Package: piper-tts 1.8.0, installed by pip.
- Authenticode inspection: NotSigned, no signer certificate.
- Required by: Piper English eSpeak phonemization before local ONNX synthesis. PiperVoice.load succeeds; synthesis imports this native extension and is rejected by Windows.
- Approved project interpreter: C:\Users\lalit\OneDrive\Desktop\Aryan\Project\SIH26174\Obrita-SIH26174\.venv\Scripts\python.exe
- Interpreter version/architecture: Python 3.11.16, x64. Code Integrity records its underlying uv CPython executable at C:\Users\lalit\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none\python.exe. Global Python 3.14 was not used.

## Package integrity

Official [PyPI release](https://pypi.org/project/piper-tts/1.8.0/):
piper_tts-1.8.0-cp39-abi3-win_amd64.whl.

- Wheel SHA-256: 5da9bfdb05dfe15da3536859d422e605483ffa6d2b3ec2c5b9593bae6b5aa6a4.
- Downloaded wheel digest matches PyPI release metadata.
- espeakbridge.pyd extracted statically from that wheel matches the installed file byte-for-byte and has the same flat SHA-256 above.
- WHEEL metadata: skbuild 0.19.1, cp39-abi3-win_amd64, non-pure platform wheel.
- INSTALLER: pip; direct_url.json is absent, so the original installation index is not recorded by package metadata. Current official-wheel comparison independently verifies the installed native contents.
- No binaries were patched, signed locally, renamed, injected or copied between runtimes to evade trust checks.

## Policy evidence

Code Integrity Operational:
- Event 3077: blocked espeakbridge.pyd under PolicyGUID {0283AC0F-FFF1-49AE-ADA1-8A933130CAD6}.
- Companion event 3033: did not meet Enterprise signing level requirements.
- Event XML policy name: VerifiedAndReputableDesktop.
- Policy version/ID string: 27555.1000.240208.
- Requested signing level: 2; validated signing level: 1.
- Status: 0xc0e90002.
- Event 3099: this policy activated successfully at 2026-10-04 19:27:59 +05:30.
- Registry READ ONLY: VerifiedAndReputablePolicyState = 1 before/after diagnostics.
- The event's SHA256 Flat Hash matches Get-FileHash. Its separate PE/authenticode SHA256 Hash is 41a3b7e563e25f39678202f4c91e4b71a8103005afaa0351d1db81ef1342c536; do not confuse these digests.

Classification: built-in **Smart App Control**, using Code Integrity/App Control enforcement. No matching Piper block was found in the last 200 entries of either AppLocker EXE/DLL or MSI/Script logs.

Machine checks: WORKGROUP, not domain-joined; AzureAdJoined, EnterpriseJoined, DomainJoined and WorkplaceJoined all NO. These observations do not prove the absence of every possible management channel. No organization-managed custom blocking policy was identified. Policy enumeration using CiTool -lp -json was denied (access denied); administrative ownership cannot be confirmed by this session.

## Resolution boundary

Microsoft's [Smart App Control FAQ](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) documents no exception mechanism for individual apps. **A generic administrator hash allowlist cannot be assumed to override this built-in SAC policy.**

The policy owner should review a publisher-provided, properly trusted/signed Piper build or arrange testing on another approved machine where this dependency is permitted normally. Microsoft's [publisher signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control) explains trusted-provider signing. No publisher certificate or approved alternate runtime was available here. This packet does not authorize registry/security changes or invent a supported SAC exception.

The local .venv/Scripts/piper.exe is a pip console launcher calling piper.__main__.main, not an independent native implementation; it reaches the same blocked phonemizer. Searches in the project, Downloads, Python/uv installations, ORBITA assets, Program Files and LocalAppData/Programs found no separate approved Piper runtime.

One clean environment was attempted with project Python under a temporary directory. Smart App Control rejected that environment's Python launcher with WinError 4551 before dependency installation. The clean Piper test therefore did not complete; this is not evidence of a second Piper installation failing synthesis. No alternative launcher/copy mode was tried. Reinstallation attempts stopped. WSL is not installed; no other approved machine was supplied.

## Intended network behavior

Production speech uses local English eSpeak, local en_US-lessac-medium ONNX/config and local sounddevice/PortAudio playback. The speech path has no cloud endpoint and does not download assets. Optional Qwen uses localhost Ollama separately. Explicit setup/integrity verification contacted official PyPI; this is distinct from normal application operation.

Model: C:\Users\lalit\AppData\Local\ORBITA\voices\en_US-lessac-medium.onnx
Configuration: same path plus .json; sample rate 22,050 Hz.

Defender antivirus, real-time protection, service and tamper protection were all reported enabled. Smart App Control remains enforced. No security settings changed.

## Evidence and retest

Diagnostic evidence is outside the repository:
C:\Users\lalit\AppData\Local\Temp\orbita-piper-runtime-_1jvphq3
Contains block-event.xml, code-integrity.json, policy-activation.json, package-integrity.json, procedure-native-failure.json and smoke/latency JSONL.

After a permitted runtime is available, use project .venv to run:
- 02_yolo/tools/benchmark_alert_latency.py --piper-model <local voice> --smoke-only
- 02_yolo/tools/benchmark_alert_latency.py --piper-model <local voice> --samples 10 --cold-samples 0 --dynamic-samples 3 --jsonl <outside-repo output>

For the requested fresh-process cold measurements, launch three separate project-Python processes with --cold-samples 1 --samples 1 --dynamic-samples 0, each writing a separate external JSONL. The tool's multiple cold-samples in a single process recreate the assistant/voice/cache; they are not fresh-process measurements. No cold timing was successfully recorded in this diagnosis.

Real synthesis, playback, cache reuse and audio latency are currently NOT VERIFIED. Substitute PCM was not used.

