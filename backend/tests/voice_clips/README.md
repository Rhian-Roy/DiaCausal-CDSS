# Voice test clips

Five short recordings for `tests/test_voice.py`, made with macOS's built-in speech voices
(`say`, 16 kHz mono WAV) — three of them Indian-English voices. They are synthetic, not
real people, so they contain no one's voice or health data.

| File | Voice | Said |
|---|---|---|
| `1-hba1c-metformin.wav` | Tara (en-IN) | "HbA1c 8.4 percent on metformin, 1 gram twice daily." |
| `2-egfr-empagliflozin.wav` | Aman (en-IN) | "eGFR 45. Should I add empagliflozin 10 milligrams?" |
| `3-sitagliptin.wav` | Daniel (en-GB) | "Consider sitagliptin, 100 milligrams once daily." |
| `4-fasting-glucose.wav` | Samantha (en-US) | "Fasting glucose 180 milligrams per decilitre after lunch." |
| `5-gliclazide-dapagliflozin.wav` | Rishi (en-IN) | "Is gliclazide safe with dapagliflozin?" |

Recorded with, for example:
`say -v Tara -o 1-hba1c-metformin.wav --file-format=WAVE --data-format=LEI16@16000 "…"`
