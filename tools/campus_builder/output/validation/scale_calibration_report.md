# Campus V0.2 scale calibration

SCALE: PARTIAL — INSUFFICIENT SCALE EVIDENCE

Model: uniform_scale; confidence: **LOW**; status: conditional
Scale X/Y: 1.268715272 / 1.268715272 m/px
Anchors: 4; independent source documents: 2; independent physical areas: 1; verified actual campus sources: 0
Weighted RMSE: 0.7978 m / 0.8794%; maximum residual: 1.2673%
Residual criterion: True; real-world evidence criterion: False
Simpler model first: uniform residuals do not justify extra degrees of freedom.

| Anchor | Pixels | Reference m | Predicted m | Absolute residual m | Signed relative residual % | Weight | Confidence | Source |
|---|---|---|---|---|---|---|---|---|
| TRACK_OUTER_LONG | 140.000 | 176.910 | 177.620 | 0.710 | 0.401 | 0.037 | low | [WORLD_ATHLETICS](https://worldathletics.org/download/download?filename=77c027b0-46b8-405d-9ffd-889fa28e3f6e.pdf&urlslug=IAAF%2BTrack%2Band%2BField%2BFacilities%2BManual%2B2008%2BEdition%2B-%2BChapters%2B1-3) — standard-dimension assumption |
| TRACK_OUTER_WIDTH | 72.000 | 92.520 | 91.347 | 1.173 | -1.267 | 0.037 | low | [WORLD_ATHLETICS](https://worldathletics.org/download/download?filename=77c027b0-46b8-405d-9ffd-889fa28e3f6e.pdf&urlslug=IAAF%2BTrack%2Band%2BField%2BFacilities%2BManual%2B2008%2BEdition%2B-%2BChapters%2B1-3) — standard-dimension assumption |
| PITCH_LONG | 83.000 | 105.000 | 105.303 | 0.303 | 0.289 | 0.037 | low | [FIFA](https://inside.fifa.com/innovation/stadium-guidelines/technical-guidelines/stadiums-guidelines/pitch-dimensions-and-surrounding-areas) — standard-dimension assumption |
| PITCH_WIDTH | 53.000 | 68.000 | 67.242 | 0.758 | -1.115 | 0.037 | low | [FIFA](https://inside.fifa.com/innovation/stadium-guidelines/technical-guidelines/stadiums-guidelines/pitch-dimensions-and-surrounding-areas) — standard-dimension assumption |

## Candidate models

```json
[
  {
    "model": "uniform_scale",
    "meters_per_pixel": 1.268715271735978,
    "rmse_m": 0.7977760553413227,
    "rmse_percent": 0.8794185088450946,
    "max_relative_error_percent": 1.2672940283285579,
    "relative_errors_percent": [
      0.40141204173699646,
      -1.2672940283285579,
      0.2889214800820755,
      -1.1148391146958445
    ]
  },
  {
    "model": "anisotropic_scale",
    "meters_per_pixel_x": 1.2843037657950707,
    "meters_per_pixel_y": 1.2640114764619277,
    "rmse_m": 0.06593740934617685,
    "rmse_percent": 0.071917864970866,
    "max_relative_error_percent": 0.1001464516746274,
    "relative_errors_percent": [
      0.029171163116762856,
      -0.05418165018904348,
      -0.08290233681905301,
      0.1001464516746274
    ]
  }
]
```

## Facts and assumptions

- FACT: standard reference dimensions are documented by their publishers. Source summaries, URLs, access date and SHA256 are saved.
- FACT: pixel endpoints are selected on the supplied planning map. The official school image has the same layout and no scale bar.
- ASSUMPTION: this campus track is an eight-lane standard track and its pitch uses FIFA recommended dimensions. Neither has been verified.
- Four lines are not four independent measurements: they share one sports complex and two normative documents; correlation-group weight is normalized.
- LOW confidence remains LOW even when conditional fit RMSE is small. No claim of surveyed campus dimensions is made.
- XY mapping is independent of Z building heights and all environment thicknesses.
- OSM raw-data requests timed out or returned HTTP 406. No unverified OSM coordinates or tertiary web size estimates entered the fit.

## Minimal additional information

Provide the measured north-to-south length in metres between the outer track boundary at these endpoints, or two independently measured long campus baselines for HIGH confidence.
A surveyed length between pixel [210,552] and [210,692] can replace TRACK_OUTER_LONG. For HIGH confidence, also provide an independent long baseline outside the sports complex, with clearly identified map endpoints.

Residuals quantify fit conditional on the reference dimensions. They do not bound actual campus-scale error when facility standard compliance is unknown.
