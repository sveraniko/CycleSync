# Medical catalog validation summary

## Preset runs

| Scenario | Preset | Status | Alloc mode | Flatness | Inj/week | Max ml/event | Warnings |
|---|---|---:|---|---:|---:|---:|---|
| MED-U1 | unified_rhythm | success | guidance_weighted | 85.44 | 4 | 0.7368 | - |
| MED-L1 | layered_pulse | success_with_warnings | guidance_weighted | 92.48 | 5 | 0.7368 | injections_above_preference |
| MED-G1 | golden_pulse | success_with_warnings | guidance_weighted | 91.81 | 7 | 0.3684 | injections_above_preference |

## Search regressions

| Query | Expected hit | Actual hits | Matched |
|---|---|---|---|
| `sustanon` | SP Sustanon FORTE / yes | SP Sustanon FORTE | yes |
| `pharma sust 500` | SP Sustanon FORTE / yes | SP Sustanon FORTE | yes |
| `сустанон форте` | SP Sustanon FORTE / yes | SP Sustanon FORTE | yes |
| `parabolan` | SP Parabolan / yes | SP Parabolan | yes |
| `параболан` | SP Parabolan / yes | SP Parabolan | yes |
| `masteron enanthate` | Masteron Enanthate / yes | Masteron Enanthate | yes |
| `мастерон энантат` | Masteron Enanthate / yes | Masteron Enanthate | yes |
| `bolddenon 300` | PHARMA BOLD 300 / no | — | yes |
| `boldenone undecylenate` | PHARMA BOLD 300 / yes | PHARMA BOLD 300 | yes |
| `testosterone phenylpropionate 120 mg` | SP Sustanon FORTE / yes | SP Sustanon FORTE | yes |
| `фенилпропионат 60мг` | — / no | — | yes |