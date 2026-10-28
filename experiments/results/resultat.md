Fall: fmi_20160928, fmi_20170509, mch_20150515, mch_20170131

## Användarperspektiv (KNEP-proxyns fördröjning inom parentes)

### 15 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.45 | 0.20 | 0.62 | 0.33 | 0.79 | 0.52 | 1.06 | 1.16 |  |  |  |  |  |  | 0.17 |
| KNEP-proxy, momentan indata (5 min) | 0.44 | 0.20 | 0.61 | 0.34 | 0.80 | 0.55 | 1.05 | 1.30 |  |  |  |  |  |  | 0.17 |
| KNEP-proxy (10 min) | 0.42 | 0.17 | 0.59 | 0.29 | 0.76 | 0.46 | 1.06 | 1.16 |  |  |  |  |  |  | 0.18 |
| KNEP-proxy, momentan indata (10 min) | 0.41 | 0.17 | 0.58 | 0.30 | 0.77 | 0.50 | 1.05 | 1.31 |  |  |  |  |  |  | 0.18 |
| 5 min, LK 30 min | 0.54 | 0.29 | 0.70 | 0.45 | 0.86 | 0.65 | 1.00 | 1.02 |  |  |  |  |  |  | 0.13 |
| 5 min, filtrerad analys | 0.52 | 0.26 | 0.68 | 0.42 | 0.84 | 0.61 | 1.00 | 0.98 |  |  |  |  |  |  | 0.14 |
| 5 min, fördelningsmatchad | 0.54 | 0.29 | 0.70 | 0.45 | 0.86 | 0.65 | 0.99 | 1.08 |  |  |  |  |  |  | 0.13 |
| 5 min, platskorrigerad | 0.55 | 0.31 | 0.71 | 0.48 | 0.87 | 0.68 | 0.99 | 1.09 |  |  |  |  |  |  | 0.13 |
| 5 min, matchad och platskorrigerad | 0.55 | 0.31 | 0.71 | 0.47 | 0.87 | 0.67 | 0.99 | 1.15 |  |  |  |  |  |  | 0.13 |
| 5 min, medel av tre körningar | 0.53 | 0.29 | 0.69 | 0.44 | 0.85 | 0.64 | 0.99 | 1.06 |  |  |  |  |  |  | 0.14 |
| 5 min, S-PROG | 0.58 | 0.29 | 0.73 | 0.45 | 0.87 | 0.62 | 0.98 | 1.13 |  |  |  |  |  |  | 0.12 |
| 5 min, STEPS-ensemble |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.10 |

### 30 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.35 | 0.11 | 0.52 | 0.20 | 0.69 | 0.34 | 1.06 | 1.17 | -0.04 |  |  |  | 0.43 |  | 0.21 |
| KNEP-proxy, momentan indata (5 min) | 0.35 | 0.12 | 0.52 | 0.22 | 0.71 | 0.38 | 1.05 | 1.32 | 0.20 |  |  |  | 0.48 |  | 0.21 |
| KNEP-proxy (10 min) | 0.33 | 0.10 | 0.50 | 0.18 | 0.67 | 0.31 | 1.06 | 1.17 | -0.04 | 0.16 | 0.07 | 0.05 | 0.44 |  | 0.22 |
| KNEP-proxy, momentan indata (10 min) | 0.33 | 0.11 | 0.50 | 0.19 | 0.68 | 0.35 | 1.05 | 1.33 | 0.20 | 0.19 | 0.04 | 0.06 | 0.48 |  | 0.22 |
| 5 min, LK 30 min | 0.41 | 0.15 | 0.58 | 0.26 | 0.75 | 0.42 | 1.00 | 1.04 | -0.08 |  |  |  | 0.44 |  | 0.19 |
| 5 min, filtrerad analys | 0.40 | 0.14 | 0.57 | 0.24 | 0.73 | 0.39 | 0.99 | 1.00 | -0.19 |  |  |  | 0.41 |  | 0.19 |
| 5 min, fördelningsmatchad | 0.41 | 0.15 | 0.58 | 0.26 | 0.74 | 0.42 | 0.98 | 1.09 | -0.04 |  |  |  | 0.43 |  | 0.19 |
| 5 min, platskorrigerad | 0.42 | 0.17 | 0.59 | 0.29 | 0.76 | 0.46 | 0.98 | 1.02 | -0.06 | 0.18 | 0.05 | 0.03 | 0.45 |  | 0.18 |
| 5 min, matchad och platskorrigerad | 0.42 | 0.17 | 0.59 | 0.29 | 0.76 | 0.46 | 0.97 | 1.07 | -0.02 | 0.22 | 0.04 | 0.03 | 0.44 |  | 0.18 |
| 5 min, medel av tre körningar | 0.41 | 0.15 | 0.58 | 0.27 | 0.75 | 0.43 | 0.98 | 0.98 | -0.12 |  |  |  | 0.43 |  | 0.19 |
| 5 min, S-PROG | 0.46 | 0.16 | 0.63 | 0.28 | 0.77 | 0.40 | 0.99 | 1.21 | -0.64 | 0.15 | 0.07 | 0.06 | 0.39 |  | 0.18 |
| 5 min, STEPS-ensemble |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.13 |

### 45 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.29 | 0.06 | 0.45 | 0.12 | 0.62 | 0.22 | 1.05 | 1.15 | -0.01 |  |  |  | 0.44 | 0.09 | 0.24 |
| KNEP-proxy, momentan indata (5 min) | 0.29 | 0.08 | 0.45 | 0.15 | 0.63 | 0.27 | 1.04 | 1.31 | 0.23 |  |  |  | 0.48 | 0.11 | 0.25 |
| KNEP-proxy (10 min) | 0.28 | 0.06 | 0.44 | 0.11 | 0.60 | 0.21 | 1.05 | 1.15 | -0.01 |  |  |  | 0.45 | 0.09 | 0.25 |
| KNEP-proxy, momentan indata (10 min) | 0.28 | 0.07 | 0.44 | 0.13 | 0.61 | 0.25 | 1.05 | 1.32 | 0.23 |  |  |  | 0.49 | 0.12 | 0.25 |
| 5 min, LK 30 min | 0.32 | 0.08 | 0.49 | 0.15 | 0.65 | 0.27 | 0.99 | 1.04 | -0.05 |  |  |  | 0.45 | 0.09 | 0.23 |
| 5 min, filtrerad analys | 0.32 | 0.08 | 0.48 | 0.14 | 0.64 | 0.25 | 0.99 | 0.99 | -0.16 |  |  |  | 0.42 | 0.07 | 0.23 |
| 5 min, fördelningsmatchad | 0.32 | 0.08 | 0.49 | 0.15 | 0.65 | 0.27 | 0.97 | 1.08 | -0.007 |  |  |  | 0.44 | 0.09 | 0.23 |
| 5 min, platskorrigerad | 0.33 | 0.09 | 0.50 | 0.17 | 0.67 | 0.29 | 0.98 | 0.92 | -0.06 |  |  |  | 0.46 | 0.09 | 0.22 |
| 5 min, matchad och platskorrigerad | 0.33 | 0.09 | 0.50 | 0.17 | 0.67 | 0.29 | 0.96 | 0.96 | -0.03 |  |  |  | 0.46 | 0.09 | 0.22 |
| 5 min, medel av tre körningar | 0.33 | 0.08 | 0.49 | 0.15 | 0.65 | 0.27 | 0.98 | 0.88 | -0.13 |  |  |  | 0.44 | 0.08 | 0.22 |
| 5 min, S-PROG | 0.39 | 0.11 | 0.56 | 0.20 | 0.69 | 0.28 | 1.00 | 1.23 | -0.86 |  |  |  | 0.38 | 0.09 | 0.21 |
| 5 min, STEPS-ensemble |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.15 |

### 60 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.25 | 0.04 | 0.40 | 0.08 | 0.55 | 0.16 | 1.05 | 1.12 | 0.001 |  |  |  | 0.45 | 0.10 | 0.27 |
| KNEP-proxy, momentan indata (5 min) | 0.25 | 0.05 | 0.40 | 0.10 | 0.57 | 0.20 | 1.04 | 1.29 | 0.25 |  |  |  | 0.50 | 0.12 | 0.27 |
| KNEP-proxy (10 min) | 0.25 | 0.04 | 0.40 | 0.08 | 0.55 | 0.16 | 1.05 | 1.12 | 0.001 | 0.21 | 0.05 | 0.09 | 0.45 | 0.10 | 0.27 |
| KNEP-proxy, momentan indata (10 min) | 0.25 | 0.05 | 0.40 | 0.10 | 0.57 | 0.20 | 1.04 | 1.29 | 0.25 | 0.25 | 0.03 | 0.09 | 0.50 | 0.12 | 0.27 |
| 5 min, LK 30 min | 0.27 | 0.05 | 0.43 | 0.10 | 0.59 | 0.19 | 0.99 | 1.02 | -0.03 |  |  |  | 0.46 | 0.10 | 0.26 |
| 5 min, filtrerad analys | 0.27 | 0.05 | 0.42 | 0.09 | 0.58 | 0.18 | 0.99 | 0.97 | -0.14 |  |  |  | 0.42 | 0.07 | 0.26 |
| 5 min, fördelningsmatchad | 0.27 | 0.05 | 0.43 | 0.10 | 0.58 | 0.19 | 0.96 | 1.06 | 0.01 |  |  |  | 0.45 | 0.09 | 0.26 |
| 5 min, platskorrigerad | 0.28 | 0.05 | 0.44 | 0.10 | 0.60 | 0.19 | 0.97 | 0.88 | -0.08 | 0.20 | 0.05 | 0.07 | 0.47 | 0.10 | 0.25 |
| 5 min, matchad och platskorrigerad | 0.28 | 0.05 | 0.44 | 0.10 | 0.59 | 0.19 | 0.95 | 0.91 | -0.04 | 0.18 | 0.04 | 0.07 | 0.46 | 0.09 | 0.25 |
| 5 min, medel av tre körningar | 0.28 | 0.05 | 0.43 | 0.10 | 0.59 | 0.18 | 0.97 | 0.85 | -0.13 |  |  |  | 0.43 | 0.08 | 0.25 |
| 5 min, S-PROG | 0.34 | 0.08 | 0.51 | 0.16 | 0.64 | 0.23 | 1.01 | 1.23 | -1.02 | 0.16 | 0.07 | 0.08 | 0.38 | 0.09 | 0.24 |
| 5 min, STEPS-ensemble |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 0.16 |

Skillnad mot KNEP-proxy (5, 50, 95 percentil; andel bootstrap > 0):

| System | Mot | Horisont | Tröskel | Mått | 5 % | median | 95 % | P(>0) |
|---|---|---|---|---|---|---|---|---|
| 5 min, LK 30 min | KNEP-proxy (10 min) | 15 | 1.0 | ETS | +0.117 | +0.123 | +0.128 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 15 | 1.0 | MCC | +0.107 | +0.112 | +0.117 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 15 | 5.0 | ETS | +0.113 | +0.122 | +0.130 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 15 | 5.0 | MCC | +0.151 | +0.161 | +0.170 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 30 | 1.0 | ETS | +0.068 | +0.072 | +0.077 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 30 | 1.0 | MCC | +0.072 | +0.077 | +0.082 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 30 | 5.0 | ETS | +0.048 | +0.054 | +0.060 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 30 | 5.0 | MCC | +0.076 | +0.086 | +0.095 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 45 | 1.0 | ETS | +0.042 | +0.046 | +0.050 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 45 | 1.0 | MCC | +0.050 | +0.054 | +0.059 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 45 | 5.0 | ETS | +0.018 | +0.024 | +0.031 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 45 | 5.0 | MCC | +0.032 | +0.042 | +0.054 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 60 | 1.0 | ETS | +0.020 | +0.024 | +0.029 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 60 | 1.0 | MCC | +0.026 | +0.030 | +0.036 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 60 | 5.0 | ETS | +0.006 | +0.012 | +0.018 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (10 min) | 60 | 5.0 | MCC | +0.010 | +0.021 | +0.032 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 15 | 1.0 | ETS | +0.088 | +0.093 | +0.097 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 15 | 1.0 | MCC | +0.079 | +0.083 | +0.088 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 15 | 5.0 | ETS | +0.086 | +0.094 | +0.101 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 15 | 5.0 | MCC | +0.111 | +0.120 | +0.130 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 30 | 1.0 | ETS | +0.048 | +0.052 | +0.057 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 30 | 1.0 | MCC | +0.050 | +0.055 | +0.059 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 30 | 5.0 | ETS | +0.033 | +0.040 | +0.047 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 30 | 5.0 | MCC | +0.052 | +0.062 | +0.073 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 45 | 1.0 | ETS | +0.029 | +0.032 | +0.036 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 45 | 1.0 | MCC | +0.033 | +0.037 | +0.042 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 45 | 5.0 | ETS | +0.010 | +0.017 | +0.024 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 45 | 5.0 | MCC | +0.017 | +0.030 | +0.042 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 60 | 1.0 | ETS | +0.020 | +0.024 | +0.029 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 60 | 1.0 | MCC | +0.026 | +0.030 | +0.036 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 60 | 5.0 | ETS | +0.006 | +0.012 | +0.018 | 1.00 |
| 5 min, LK 30 min | KNEP-proxy (5 min) | 60 | 5.0 | MCC | +0.010 | +0.021 | +0.032 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 15 | 1.0 | ETS | +0.128 | +0.135 | +0.141 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 15 | 1.0 | MCC | +0.117 | +0.122 | +0.128 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 15 | 5.0 | ETS | +0.129 | +0.140 | +0.151 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 15 | 5.0 | MCC | +0.171 | +0.183 | +0.196 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 30 | 1.0 | ETS | +0.080 | +0.086 | +0.092 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 30 | 1.0 | MCC | +0.085 | +0.091 | +0.097 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 30 | 5.0 | ETS | +0.065 | +0.075 | +0.085 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 30 | 5.0 | MCC | +0.102 | +0.117 | +0.131 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 45 | 1.0 | ETS | +0.050 | +0.055 | +0.060 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 45 | 1.0 | MCC | +0.059 | +0.065 | +0.070 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 45 | 5.0 | ETS | +0.023 | +0.033 | +0.044 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 45 | 5.0 | MCC | +0.040 | +0.057 | +0.076 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 60 | 1.0 | ETS | +0.024 | +0.030 | +0.036 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 60 | 1.0 | MCC | +0.031 | +0.038 | +0.045 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 60 | 5.0 | ETS | +0.003 | +0.012 | +0.021 | 0.99 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (10 min) | 60 | 5.0 | MCC | +0.006 | +0.021 | +0.038 | 0.99 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 15 | 1.0 | ETS | +0.099 | +0.105 | +0.110 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 15 | 1.0 | MCC | +0.088 | +0.093 | +0.098 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 15 | 5.0 | ETS | +0.102 | +0.112 | +0.122 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 15 | 5.0 | MCC | +0.132 | +0.143 | +0.156 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 30 | 1.0 | ETS | +0.061 | +0.066 | +0.071 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 30 | 1.0 | MCC | +0.063 | +0.069 | +0.074 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 30 | 5.0 | ETS | +0.051 | +0.061 | +0.071 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 30 | 5.0 | MCC | +0.079 | +0.094 | +0.108 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 45 | 1.0 | ETS | +0.037 | +0.041 | +0.046 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 45 | 1.0 | MCC | +0.043 | +0.048 | +0.053 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 45 | 5.0 | ETS | +0.015 | +0.026 | +0.038 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 45 | 5.0 | MCC | +0.027 | +0.045 | +0.064 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 60 | 1.0 | ETS | +0.024 | +0.030 | +0.036 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 60 | 1.0 | MCC | +0.031 | +0.038 | +0.045 | 1.00 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 60 | 5.0 | ETS | +0.003 | +0.012 | +0.021 | 0.99 |
| 5 min, matchad och platskorrigerad | KNEP-proxy (5 min) | 60 | 5.0 | MCC | +0.006 | +0.021 | +0.038 | 0.99 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 15 | 1.0 | ETS | +0.128 | +0.135 | +0.141 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 15 | 1.0 | MCC | +0.116 | +0.122 | +0.128 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 15 | 5.0 | ETS | +0.131 | +0.142 | +0.153 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 15 | 5.0 | MCC | +0.173 | +0.185 | +0.198 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 30 | 1.0 | ETS | +0.080 | +0.086 | +0.092 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 30 | 1.0 | MCC | +0.084 | +0.091 | +0.097 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 30 | 5.0 | ETS | +0.064 | +0.074 | +0.084 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 30 | 5.0 | MCC | +0.100 | +0.115 | +0.130 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 45 | 1.0 | ETS | +0.050 | +0.056 | +0.060 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 45 | 1.0 | MCC | +0.059 | +0.065 | +0.071 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 45 | 5.0 | ETS | +0.021 | +0.032 | +0.044 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 45 | 5.0 | MCC | +0.039 | +0.056 | +0.075 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 60 | 1.0 | ETS | +0.025 | +0.031 | +0.036 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 60 | 1.0 | MCC | +0.032 | +0.038 | +0.045 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 60 | 5.0 | ETS | +0.003 | +0.012 | +0.021 | 0.98 |
| 5 min, platskorrigerad | KNEP-proxy (10 min) | 60 | 5.0 | MCC | +0.006 | +0.022 | +0.039 | 0.99 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 15 | 1.0 | ETS | +0.099 | +0.105 | +0.110 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 15 | 1.0 | MCC | +0.088 | +0.093 | +0.098 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 15 | 5.0 | ETS | +0.104 | +0.114 | +0.124 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 15 | 5.0 | MCC | +0.133 | +0.145 | +0.157 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 30 | 1.0 | ETS | +0.060 | +0.066 | +0.071 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 30 | 1.0 | MCC | +0.063 | +0.068 | +0.074 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 30 | 5.0 | ETS | +0.049 | +0.060 | +0.070 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 30 | 5.0 | MCC | +0.077 | +0.092 | +0.108 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 45 | 1.0 | ETS | +0.037 | +0.042 | +0.046 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 45 | 1.0 | MCC | +0.043 | +0.048 | +0.053 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 45 | 5.0 | ETS | +0.014 | +0.025 | +0.037 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 45 | 5.0 | MCC | +0.025 | +0.044 | +0.063 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 60 | 1.0 | ETS | +0.025 | +0.031 | +0.036 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 60 | 1.0 | MCC | +0.032 | +0.038 | +0.045 | 1.00 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 60 | 5.0 | ETS | +0.003 | +0.012 | +0.021 | 0.98 |
| 5 min, platskorrigerad | KNEP-proxy (5 min) | 60 | 5.0 | MCC | +0.006 | +0.022 | +0.039 | 0.99 |

## Användarperspektiv på 5-minutersupplösning (momentan radar som facit)

### 15 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.39 | 0.16 | 0.56 | 0.27 | 0.75 | 0.46 | 1.01 | 0.89 |  |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (5 min) | 0.39 | 0.17 | 0.56 | 0.29 | 0.77 | 0.51 | 1.00 | 1.01 |  |  |  |  |  |  |  |
| KNEP-proxy (10 min) | 0.36 | 0.13 | 0.53 | 0.23 | 0.72 | 0.41 | 1.01 | 0.90 |  |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (10 min) | 0.36 | 0.15 | 0.53 | 0.25 | 0.74 | 0.46 | 1.00 | 1.01 |  |  |  |  |  |  |  |
| 5 min, LK 30 min | 0.45 | 0.21 | 0.62 | 0.35 | 0.82 | 0.58 | 1.00 | 1.00 |  |  |  |  |  |  |  |
| 5 min, filtrerad analys | 0.44 | 0.20 | 0.61 | 0.33 | 0.80 | 0.54 | 1.00 | 0.95 |  |  |  |  |  |  |  |
| 5 min, fördelningsmatchad | 0.45 | 0.21 | 0.62 | 0.35 | 0.82 | 0.58 | 0.99 | 1.04 |  |  |  |  |  |  |  |
| 5 min, platskorrigerad | 0.45 | 0.23 | 0.62 | 0.37 | 0.83 | 0.61 | 0.95 | 0.96 |  |  |  |  |  |  |  |
| 5 min, matchad och platskorrigerad | 0.45 | 0.23 | 0.62 | 0.37 | 0.83 | 0.61 | 0.94 | 1.00 |  |  |  |  |  |  |  |
| 5 min, medel av tre körningar | 0.44 | 0.21 | 0.61 | 0.35 | 0.81 | 0.58 | 0.94 | 0.90 |  |  |  |  |  |  |  |
| 5 min, S-PROG | 0.50 | 0.22 | 0.67 | 0.36 | 0.84 | 0.54 | 0.99 | 1.03 |  |  |  |  |  |  |  |

### 30 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.32 | 0.09 | 0.48 | 0.17 | 0.67 | 0.32 | 1.01 | 0.90 | -0.32 |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (5 min) | 0.32 | 0.11 | 0.48 | 0.19 | 0.69 | 0.36 | 1.00 | 1.02 | -0.08 |  |  |  |  |  |  |
| KNEP-proxy (10 min) | 0.30 | 0.08 | 0.46 | 0.15 | 0.64 | 0.28 | 1.01 | 0.90 | -0.32 |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (10 min) | 0.30 | 0.09 | 0.46 | 0.17 | 0.66 | 0.33 | 1.00 | 1.02 | -0.07 |  |  |  |  |  |  |
| 5 min, LK 30 min | 0.35 | 0.12 | 0.51 | 0.21 | 0.72 | 0.38 | 1.00 | 1.02 | -0.09 |  |  |  |  |  |  |
| 5 min, filtrerad analys | 0.34 | 0.11 | 0.51 | 0.20 | 0.70 | 0.36 | 1.00 | 0.96 | -0.22 |  |  |  |  |  |  |
| 5 min, fördelningsmatchad | 0.35 | 0.12 | 0.52 | 0.21 | 0.72 | 0.38 | 0.98 | 1.05 | -0.05 |  |  |  |  |  |  |
| 5 min, platskorrigerad | 0.35 | 0.13 | 0.52 | 0.23 | 0.73 | 0.41 | 0.94 | 0.89 | -0.08 |  |  |  |  |  |  |
| 5 min, matchad och platskorrigerad | 0.35 | 0.13 | 0.52 | 0.23 | 0.73 | 0.41 | 0.93 | 0.91 | -0.05 |  |  |  |  |  |  |
| 5 min, medel av tre körningar | 0.34 | 0.12 | 0.51 | 0.21 | 0.71 | 0.39 | 0.94 | 0.82 | -0.17 |  |  |  |  |  |  |
| 5 min, S-PROG | 0.41 | 0.14 | 0.58 | 0.24 | 0.75 | 0.36 | 1.00 | 1.06 | -0.77 |  |  |  |  |  |  |

### 45 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.27 | 0.06 | 0.42 | 0.11 | 0.60 | 0.22 | 1.00 | 0.88 | -0.30 |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (5 min) | 0.27 | 0.07 | 0.42 | 0.14 | 0.62 | 0.27 | 0.99 | 1.01 | -0.05 |  |  |  |  |  |  |
| KNEP-proxy (10 min) | 0.25 | 0.05 | 0.40 | 0.10 | 0.58 | 0.20 | 1.00 | 0.88 | -0.30 |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (10 min) | 0.25 | 0.07 | 0.41 | 0.12 | 0.60 | 0.24 | 1.00 | 1.01 | -0.05 |  |  |  |  |  |  |
| 5 min, LK 30 min | 0.28 | 0.07 | 0.44 | 0.13 | 0.63 | 0.26 | 1.00 | 1.01 | -0.06 |  |  |  |  |  |  |
| 5 min, filtrerad analys | 0.28 | 0.07 | 0.44 | 0.13 | 0.62 | 0.25 | 1.00 | 0.96 | -0.20 |  |  |  |  |  |  |
| 5 min, fördelningsmatchad | 0.28 | 0.07 | 0.44 | 0.14 | 0.63 | 0.26 | 0.97 | 1.04 | -0.03 |  |  |  |  |  |  |
| 5 min, platskorrigerad | 0.28 | 0.07 | 0.44 | 0.14 | 0.64 | 0.27 | 0.94 | 0.83 | -0.09 |  |  |  |  |  |  |
| 5 min, matchad och platskorrigerad | 0.28 | 0.07 | 0.44 | 0.14 | 0.64 | 0.27 | 0.92 | 0.85 | -0.06 |  |  |  |  |  |  |
| 5 min, medel av tre körningar | 0.28 | 0.07 | 0.44 | 0.13 | 0.63 | 0.25 | 0.93 | 0.76 | -0.18 |  |  |  |  |  |  |
| 5 min, S-PROG | 0.35 | 0.10 | 0.52 | 0.17 | 0.67 | 0.27 | 1.00 | 1.07 | -0.92 |  |  |  |  |  |  |

### 60 min framåt

| System | ETS 1 | ETS 5 | MCC 1 | MCC 5 | FSS 1/10km | FSS 5/10km | Bias 1 | Bias 5 | Textur | SAL S | SAL A | SAL L | Hopp | Fram och tillbaka | CRPS/MAE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KNEP-proxy (5 min) | 0.24 | 0.04 | 0.38 | 0.08 | 0.55 | 0.17 | 1.00 | 0.86 | -0.29 |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (5 min) | 0.24 | 0.06 | 0.38 | 0.10 | 0.57 | 0.21 | 0.99 | 0.99 | -0.04 |  |  |  |  |  |  |
| KNEP-proxy (10 min) | 0.23 | 0.04 | 0.37 | 0.08 | 0.54 | 0.16 | 1.00 | 0.87 | -0.28 |  |  |  |  |  |  |
| KNEP-proxy, momentan indata (10 min) | 0.22 | 0.05 | 0.37 | 0.10 | 0.55 | 0.20 | 0.99 | 1.00 | -0.04 |  |  |  |  |  |  |
| 5 min, LK 30 min | 0.24 | 0.05 | 0.39 | 0.10 | 0.58 | 0.20 | 0.99 | 0.99 | -0.05 |  |  |  |  |  |  |
| 5 min, filtrerad analys | 0.24 | 0.05 | 0.39 | 0.10 | 0.57 | 0.19 | 0.99 | 0.93 | -0.19 |  |  |  |  |  |  |
| 5 min, fördelningsmatchad | 0.24 | 0.05 | 0.39 | 0.10 | 0.57 | 0.20 | 0.96 | 1.01 | -0.02 |  |  |  |  |  |  |
| 5 min, platskorrigerad | 0.24 | 0.05 | 0.39 | 0.09 | 0.58 | 0.19 | 0.94 | 0.80 | -0.10 |  |  |  |  |  |  |
| 5 min, matchad och platskorrigerad | 0.24 | 0.05 | 0.39 | 0.09 | 0.58 | 0.19 | 0.91 | 0.81 | -0.07 |  |  |  |  |  |  |
| 5 min, medel av tre körningar | 0.24 | 0.05 | 0.39 | 0.09 | 0.58 | 0.19 | 0.93 | 0.78 | -0.16 |  |  |  |  |  |  |
| 5 min, S-PROG | 0.32 | 0.08 | 0.48 | 0.15 | 0.62 | 0.23 | 1.01 | 1.05 | -1.02 |  |  |  |  |  |  |

## Per fall, ETS och MCC vid 1 och 5 mm/h, 30 min framåt

| Fall | System | ETS 1 | ETS 5 | MCC 1 | MCC 5 |
|---|---|---|---|---|---|
| fmi_20160928 | KNEP-proxy (5 min) | 0.36 | 0.07 | 0.54 | 0.13 |
| fmi_20160928 | KNEP-proxy (10 min) | 0.35 | 0.06 | 0.51 | 0.11 |
| fmi_20160928 | 5 min, LK 30 min | 0.42 | 0.10 | 0.59 | 0.18 |
| fmi_20160928 | 5 min, platskorrigerad | 0.44 | 0.10 | 0.61 | 0.18 |
| fmi_20160928 | 5 min, matchad och platskorrigerad | 0.44 | 0.11 | 0.61 | 0.20 |
| fmi_20160928 | 5 min, S-PROG | 0.47 | 0.09 | 0.64 | 0.16 |
| fmi_20170509 | KNEP-proxy (5 min) | 0.13 | -0.00 | 0.23 | -0.00 |
| fmi_20170509 | KNEP-proxy (10 min) | 0.11 | -0.00 | 0.20 | -0.00 |
| fmi_20170509 | 5 min, LK 30 min | 0.17 | 0.002 | 0.29 | 0.004 |
| fmi_20170509 | 5 min, platskorrigerad | 0.17 | 0.002 | 0.29 | 0.004 |
| fmi_20170509 | 5 min, matchad och platskorrigerad | 0.18 | 0.003 | 0.30 | 0.005 |
| fmi_20170509 | 5 min, S-PROG | 0.19 | 0.002 | 0.32 | 0.005 |
| mch_20150515 | KNEP-proxy (5 min) | 0.40 | 0.11 | 0.57 | 0.21 |
| mch_20150515 | KNEP-proxy (10 min) | 0.37 | 0.10 | 0.54 | 0.18 |
| mch_20150515 | 5 min, LK 30 min | 0.45 | 0.15 | 0.62 | 0.26 |
| mch_20150515 | 5 min, platskorrigerad | 0.45 | 0.17 | 0.62 | 0.29 |
| mch_20150515 | 5 min, matchad och platskorrigerad | 0.45 | 0.17 | 0.62 | 0.29 |
| mch_20150515 | 5 min, S-PROG | 0.52 | 0.21 | 0.68 | 0.35 |
| mch_20170131 | KNEP-proxy (5 min) | 0.33 | 0.12 | 0.50 | 0.22 |
| mch_20170131 | KNEP-proxy (10 min) | 0.31 | 0.11 | 0.47 | 0.20 |
| mch_20170131 | 5 min, LK 30 min | 0.39 | 0.18 | 0.56 | 0.30 |
| mch_20170131 | 5 min, platskorrigerad | 0.41 | 0.21 | 0.58 | 0.35 |
| mch_20170131 | 5 min, matchad och platskorrigerad | 0.41 | 0.21 | 0.58 | 0.35 |
| mch_20170131 | 5 min, S-PROG | 0.45 | 0.11 | 0.62 | 0.20 |

## Per fall, ETS och MCC vid 1 och 5 mm/h, 60 min framåt

| Fall | System | ETS 1 | ETS 5 | MCC 1 | MCC 5 |
|---|---|---|---|---|---|
| fmi_20160928 | KNEP-proxy (5 min) | 0.26 | 0.02 | 0.41 | 0.04 |
| fmi_20160928 | KNEP-proxy (10 min) | 0.26 | 0.02 | 0.41 | 0.04 |
| fmi_20160928 | 5 min, LK 30 min | 0.29 | 0.02 | 0.44 | 0.04 |
| fmi_20160928 | 5 min, platskorrigerad | 0.30 | 0.02 | 0.46 | 0.04 |
| fmi_20160928 | 5 min, matchad och platskorrigerad | 0.30 | 0.02 | 0.46 | 0.05 |
| fmi_20160928 | 5 min, S-PROG | 0.35 | 0.02 | 0.52 | 0.03 |
| fmi_20170509 | KNEP-proxy (5 min) | 0.05 | -0.00 | 0.09 | -0.00 |
| fmi_20170509 | KNEP-proxy (10 min) | 0.05 | -0.00 | 0.09 | -0.00 |
| fmi_20170509 | 5 min, LK 30 min | 0.07 | -0.00 | 0.13 | -0.00 |
| fmi_20170509 | 5 min, platskorrigerad | 0.07 | -0.00 | 0.13 | -0.00 |
| fmi_20170509 | 5 min, matchad och platskorrigerad | 0.07 | -0.00 | 0.14 | -0.000 |
| fmi_20170509 | 5 min, S-PROG | 0.08 | -0.00 | 0.15 | -0.000 |
| mch_20150515 | KNEP-proxy (5 min) | 0.27 | 0.05 | 0.43 | 0.09 |
| mch_20150515 | KNEP-proxy (10 min) | 0.27 | 0.05 | 0.43 | 0.09 |
| mch_20150515 | 5 min, LK 30 min | 0.30 | 0.05 | 0.46 | 0.09 |
| mch_20150515 | 5 min, platskorrigerad | 0.29 | 0.05 | 0.45 | 0.09 |
| mch_20150515 | 5 min, matchad och platskorrigerad | 0.30 | 0.05 | 0.46 | 0.09 |
| mch_20150515 | 5 min, S-PROG | 0.41 | 0.13 | 0.58 | 0.23 |
| mch_20170131 | KNEP-proxy (5 min) | 0.23 | 0.04 | 0.37 | 0.08 |
| mch_20170131 | KNEP-proxy (10 min) | 0.23 | 0.04 | 0.37 | 0.08 |
| mch_20170131 | 5 min, LK 30 min | 0.25 | 0.08 | 0.40 | 0.14 |
| mch_20170131 | 5 min, platskorrigerad | 0.26 | 0.09 | 0.41 | 0.16 |
| mch_20170131 | 5 min, matchad och platskorrigerad | 0.25 | 0.09 | 0.40 | 0.16 |
| mch_20170131 | 5 min, S-PROG | 0.32 | 0.04 | 0.48 | 0.07 |

